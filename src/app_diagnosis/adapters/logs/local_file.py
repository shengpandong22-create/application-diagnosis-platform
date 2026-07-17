import re
from pathlib import Path

from app_diagnosis.ports.log_reader import LogExcerpt


class InvalidLogRead(ValueError):
    """Raised when a local log read crosses a configured safety boundary."""


class LocalLogFileReader:
    ALLOWED_SUFFIXES = frozenset({".log"})
    _EVENT_START = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?")

    def __init__(
        self,
        root: Path,
        *,
        max_tail_bytes: int = 256 * 1024,
        max_excerpt_lines: int = 120,
    ) -> None:
        if max_tail_bytes < 1024 or max_tail_bytes > 1024 * 1024:
            raise ValueError("max_tail_bytes must be between 1024 and 1048576")
        if max_excerpt_lines < 1 or max_excerpt_lines > 200:
            raise ValueError("max_excerpt_lines must be between 1 and 200")
        self._root = root.resolve(strict=True)
        if not self._root.is_dir():
            raise ValueError("log root must be a directory")
        self._max_tail_bytes = max_tail_bytes
        self._max_excerpt_lines = max_excerpt_lines

    def read_latest(self, *, relative_path: str, keyword: str) -> LogExcerpt:
        if not keyword.strip():
            raise InvalidLogRead("keyword must not be blank")
        requested = Path(relative_path)
        if requested.is_absolute() or requested.suffix.casefold() not in self.ALLOWED_SUFFIXES:
            raise InvalidLogRead("only relative .log files are allowed")
        try:
            resolved = (self._root / requested).resolve(strict=True)
            resolved.relative_to(self._root)
        except (OSError, ValueError) as exc:
            raise InvalidLogRead("log path must remain inside the configured root") from exc
        if not resolved.is_file():
            raise InvalidLogRead("log path must identify a file")

        size = resolved.stat().st_size
        with resolved.open("rb") as stream:
            if size > self._max_tail_bytes:
                stream.seek(size - self._max_tail_bytes)
                stream.readline()  # discard a potentially partial first line
            raw = stream.read(self._max_tail_bytes)
        text = raw.decode("utf-8", errors="replace")
        lines = text.splitlines()
        matches = [
            index for index, line in enumerate(lines) if keyword.casefold() in line.casefold()
        ]
        if not matches:
            raise InvalidLogRead(f"keyword not found in the bounded log tail: {keyword}")

        match = matches[-1]
        start = self._event_start(lines, match)
        end = self._event_end(lines, start)
        end = min(end, start + self._max_excerpt_lines)
        content = "\n".join(lines[start:end]).strip()
        relative = resolved.relative_to(self._root).as_posix()
        first_line = start + 1
        last_line = end
        return LogExcerpt(
            content=content,
            source_reference=f"{relative}:{first_line}-{last_line}",
            matched_line=match + 1,
        )

    @classmethod
    def _event_start(cls, lines: list[str], match: int) -> int:
        for index in range(match, -1, -1):
            if cls._EVENT_START.match(lines[index]):
                return index
        return max(0, match - 8)

    @classmethod
    def _event_end(cls, lines: list[str], start: int) -> int:
        for index in range(start + 1, len(lines)):
            if cls._EVENT_START.match(lines[index]):
                return index
        return len(lines)
