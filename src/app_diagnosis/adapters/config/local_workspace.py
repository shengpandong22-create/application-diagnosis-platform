from pathlib import Path

from app_diagnosis.ports.config_repository import ConfigExcerpt


class LocalConfigRepository:
    ALLOWED_SUFFIXES = frozenset({".yml", ".yaml", ".properties", ".xml", ".json", ".toml"})
    MAX_FILE_BYTES = 256 * 1024
    MAX_READ_LINES = 120

    def __init__(self, root: Path) -> None:
        self._root = root.resolve(strict=True)
        if not self._root.is_dir():
            raise ValueError("config root must be a directory")

    async def read(self, path: str, *, start_line: int, end_line: int) -> ConfigExcerpt:
        requested = Path(path)
        if requested.is_absolute() or requested.suffix.casefold() not in self.ALLOWED_SUFFIXES:
            raise PermissionError("only relative supported config files are allowed")
        if start_line < 1 or end_line < start_line or end_line - start_line + 1 > 120:
            raise ValueError("invalid or excessive config line range")
        candidate = (self._root / requested).resolve(strict=True)
        try:
            relative = candidate.relative_to(self._root)
        except ValueError as error:
            raise PermissionError("config path escapes the authorized workspace") from error
        if not candidate.is_file() or candidate.stat().st_size > self.MAX_FILE_BYTES:
            raise PermissionError("config file is unavailable or exceeds the size limit")
        lines = candidate.read_text(encoding="utf-8").splitlines()
        selected = lines[start_line - 1 : end_line]
        if not selected:
            raise ValueError("requested config range is empty")
        return ConfigExcerpt(
            path=relative.as_posix(),
            start_line=start_line,
            end_line=start_line + len(selected) - 1,
            content="\n".join(
                f"{start_line + index}: {line}" for index, line in enumerate(selected)
            ),
        )
