from pathlib import Path

from app_diagnosis.ports.config_repository import ConfigExcerpt


class LocalConfigRepository:
    ALLOWED_SUFFIXES = frozenset({".yml", ".yaml", ".properties", ".xml", ".json", ".toml"})
    MAX_FILE_BYTES = 256 * 1024
    MAX_READ_LINES = 120
    _IGNORED_PARTS = frozenset({".git", ".idea", "target", "build", ".gradle", "__pycache__"})
    _COMMON_CONFIG_NAMES = (
        "application.yml",
        "application.yaml",
        "application.properties",
        "bootstrap.yml",
        "bootstrap.yaml",
        "bootstrap.properties",
    )

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

    def list_candidate_paths(self, *, limit: int = 20) -> tuple[str, ...]:
        if limit < 1 or limit > 100:
            raise ValueError("config candidate limit must be between 1 and 100")
        candidates: list[str] = []
        for path in sorted(self._root.rglob("*")):
            if not self._is_allowed_file(path):
                continue
            candidates.append(path.relative_to(self._root).as_posix())
        return tuple(sorted(candidates, key=_candidate_sort_key)[:limit])

    def _is_allowed_file(self, path: Path) -> bool:
        if not path.is_file() or path.suffix.casefold() not in self.ALLOWED_SUFFIXES:
            return False
        if any(part.casefold() in self._IGNORED_PARTS for part in path.parts):
            return False
        try:
            return path.stat().st_size <= self.MAX_FILE_BYTES
        except OSError:
            return False


def _candidate_sort_key(path: str) -> tuple[int, int, str]:
    name = Path(path).name.casefold()
    try:
        common_rank = LocalConfigRepository._COMMON_CONFIG_NAMES.index(name)
    except ValueError:
        common_rank = len(LocalConfigRepository._COMMON_CONFIG_NAMES)
    return common_rank, path.count("/"), path.casefold()
