from pathlib import Path

from app_diagnosis.domain.code_workspace import CodeWorkspace
from app_diagnosis.ports.code_repository import CodeExcerpt, CodeMatch


class LocalCodeRepository:
    _IGNORED_PARTS = frozenset({".git", ".idea", "target", "build", ".gradle"})
    _MAX_FILE_BYTES = 256 * 1024
    _MAX_READ_LINES = 120

    def __init__(self, workspace: CodeWorkspace) -> None:
        self._workspace = workspace

    async def search(self, query: str, *, limit: int) -> tuple[CodeMatch, ...]:
        needle = query.strip().casefold()
        if not needle:
            raise ValueError("code search query must not be blank")
        matches: list[CodeMatch] = []
        for path in sorted(self._workspace.root.rglob("*")):
            if len(matches) >= limit:
                break
            if not self._allowed(path):
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeError):
                continue
            relative = path.relative_to(self._workspace.root).as_posix()
            for number, line in enumerate(lines, 1):
                if needle in line.casefold() or needle in path.name.casefold():
                    matches.append(CodeMatch(relative, number, line.strip()[:300]))
                    if len(matches) >= limit:
                        break
        return tuple(matches)

    async def read(self, path: str, *, start_line: int, end_line: int) -> CodeExcerpt:
        if (
            start_line < 1
            or end_line < start_line
            or end_line - start_line + 1 > self._MAX_READ_LINES
        ):
            raise ValueError("invalid or excessive code line range")
        candidate = (self._workspace.root / Path(path)).resolve(strict=True)
        try:
            relative = candidate.relative_to(self._workspace.root)
        except ValueError as error:
            raise PermissionError("code path escapes the authorized workspace") from error
        if not self._allowed(candidate):
            raise PermissionError("code file type or location is not allowed")
        lines = candidate.read_text(encoding="utf-8").splitlines()
        selected = lines[start_line - 1 : end_line]
        if not selected:
            raise ValueError("requested code range is empty")
        return CodeExcerpt(
            workspace=self._workspace.name,
            revision=self._workspace.revision,
            path=relative.as_posix(),
            start_line=start_line,
            end_line=start_line + len(selected) - 1,
            content="\n".join(
                f"{start_line + index}: {line}" for index, line in enumerate(selected)
            ),
        )

    def _allowed(self, path: Path) -> bool:
        if not path.is_file() or path.suffix.casefold() not in self._workspace.allowed_extensions:
            return False
        if any(part.casefold() in self._IGNORED_PARTS for part in path.parts):
            return False
        try:
            return path.stat().st_size <= self._MAX_FILE_BYTES
        except OSError:
            return False
