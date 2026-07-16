import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from app_diagnosis.ports.knowledge_search import KnowledgeSearchMatch

_TOKEN = re.compile(r"[a-zA-Z0-9_.-]+|[\u4e00-\u9fff]+")


class _KnowledgeEntry(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=2000)
    error_types: list[str] = Field(default_factory=list, max_length=20)
    tags: list[str] = Field(default_factory=list, max_length=30)
    source: str = Field(min_length=1, max_length=100)
    status: Literal["confirmed"]


class JsonDirectoryKnowledgeSearch:
    def __init__(
        self,
        directory: Path,
        *,
        max_file_bytes: int = 1_048_576,
        max_entries: int = 1000,
    ) -> None:
        self._directory = directory.resolve()
        self._max_file_bytes = max_file_bytes
        self._max_entries = max_entries
        self._entries = self._load_entries()

    async def search(self, query: str, *, limit: int) -> tuple[KnowledgeSearchMatch, ...]:
        terms = self._tokenize(query)
        if not terms:
            return ()
        matches: list[KnowledgeSearchMatch] = []
        for entry in self._entries:
            title = entry.title.casefold()
            error_types = " ".join(entry.error_types).casefold()
            searchable = " ".join(
                [entry.title, entry.summary, *entry.error_types, *entry.tags]
            ).casefold()
            matched = tuple(term for term in terms if term in searchable)
            if not matched:
                continue
            weighted = sum(
                3 if term in title else 2 if term in error_types else 1 for term in matched
            )
            score = round(min(1.0, weighted / max(1, len(terms) * 3)), 4)
            matches.append(
                KnowledgeSearchMatch(
                    entry_id=entry.id,
                    title=entry.title,
                    summary=entry.summary,
                    matched_terms=matched,
                    score=score,
                    source=entry.source,
                )
            )
        matches.sort(key=lambda item: (-item.score, item.entry_id))
        return tuple(matches[:limit])

    def _load_entries(self) -> tuple[_KnowledgeEntry, ...]:
        if not self._directory.is_dir():
            raise ValueError(f"knowledge directory does not exist: {self._directory}")
        entries: list[_KnowledgeEntry] = []
        for path in sorted(self._directory.glob("*.json")):
            resolved = path.resolve()
            if path.is_symlink() or not resolved.is_relative_to(self._directory):
                raise ValueError(
                    f"knowledge file must stay inside configured directory: {path.name}"
                )
            if resolved.stat().st_size > self._max_file_bytes:
                raise ValueError(f"knowledge file exceeds size limit: {path.name}")
            try:
                raw = json.loads(resolved.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise ValueError(f"invalid knowledge file: {path.name}") from error
            if not isinstance(raw, list):
                raise ValueError(f"knowledge file root must be an array: {path.name}")
            try:
                entries.extend(_KnowledgeEntry.model_validate(item) for item in raw)
            except ValidationError as error:
                raise ValueError(f"invalid knowledge entry in: {path.name}") from error
            if len(entries) > self._max_entries:
                raise ValueError("knowledge entry count exceeds limit")
        ids = [entry.id for entry in entries]
        if len(ids) != len(set(ids)):
            raise ValueError("knowledge entry ids must be unique")
        return tuple(entries)

    @staticmethod
    def _tokenize(value: str) -> tuple[str, ...]:
        return tuple(dict.fromkeys(token.casefold() for token in _TOKEN.findall(value)))
