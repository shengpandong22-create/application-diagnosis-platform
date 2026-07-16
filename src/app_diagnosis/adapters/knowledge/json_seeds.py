import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from app_diagnosis.domain.knowledge import KnowledgeEntry, KnowledgeStatus


class _SeedEntry(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=4000)
    error_types: list[str] = Field(default_factory=list, max_length=20)
    tags: list[str] = Field(default_factory=list, max_length=30)
    source: str = Field(min_length=1, max_length=100)
    status: Literal["candidate", "confirmed", "retired"]


class JsonKnowledgeSeedLoader:
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

    def load(self) -> tuple[KnowledgeEntry, ...]:
        if not self._directory.is_dir():
            raise ValueError(f"knowledge directory does not exist: {self._directory}")
        seeds: list[_SeedEntry] = []
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
                seeds.extend(_SeedEntry.model_validate(item) for item in raw)
            except ValidationError as error:
                raise ValueError(f"invalid knowledge entry in: {path.name}") from error
            if len(seeds) > self._max_entries:
                raise ValueError("knowledge entry count exceeds limit")
        ids = [seed.id for seed in seeds]
        if len(ids) != len(set(ids)):
            raise ValueError("knowledge entry ids must be unique")
        loaded_at = datetime.now(UTC)
        return tuple(
            KnowledgeEntry.create(
                entry_id=seed.id,
                title=seed.title,
                summary=seed.summary,
                error_types=tuple(seed.error_types),
                tags=tuple(seed.tags),
                source=seed.source,
                status=KnowledgeStatus(seed.status),
                now=loaded_at,
            )
            for seed in seeds
        )
