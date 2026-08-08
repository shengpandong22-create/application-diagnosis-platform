import re
from collections.abc import Collection
from pathlib import PurePosixPath
from urllib.parse import quote

import httpx

from app_diagnosis.ports.code_repository import CodeExcerpt, CodeMatch, CodeRepository


class GitLabSnapshotRepository:
    """只读取白名单项目的固定 deployed commit，不跟随 branch HEAD。"""

    _COMMIT = re.compile(r"^[0-9a-fA-F]{7,40}$")
    _EXTENSIONS = frozenset({".java", ".py", ".ts", ".tsx", ".js", ".json", ".yml", ".yaml"})

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        base_url: str,
        project: str,
        commit: str,
        allowed_projects: Collection[str],
        allowed_commits: Collection[str],
        private_token: str,
        max_files: int = 100,
        max_file_bytes: int = 262_144,
    ) -> None:
        if project not in set(allowed_projects):
            raise PermissionError("GitLab project is not allowlisted")
        if commit not in set(allowed_commits) or not self._COMMIT.fullmatch(commit):
            raise PermissionError("GitLab commit is not allowlisted")
        self._client = client
        self._base = base_url.rstrip("/")
        self._project = project
        self._commit = commit
        self._headers = {"PRIVATE-TOKEN": private_token}
        self._max_files = max_files
        self._max_file_bytes = max_file_bytes
        self._cache: dict[str, str] = {}

    async def search(self, query: str, *, limit: int) -> tuple[CodeMatch, ...]:
        needle = query.strip().casefold()
        if not needle or limit < 1 or limit > 50:
            raise ValueError("invalid GitLab code search")
        matches: list[CodeMatch] = []
        for path in await self._tree():
            if len(matches) >= limit:
                break
            content = await self._raw(path)
            for line_number, line in enumerate(content.splitlines(), 1):
                if needle in line.casefold() or needle in PurePosixPath(path).name.casefold():
                    matches.append(CodeMatch(path, line_number, line.strip()[:300]))
                    if len(matches) >= limit:
                        break
        return tuple(matches)

    async def read(self, path: str, *, start_line: int, end_line: int) -> CodeExcerpt:
        normalized = PurePosixPath(path)
        if normalized.is_absolute() or ".." in normalized.parts:
            raise PermissionError("GitLab code path is outside snapshot")
        if start_line < 1 or end_line < start_line or end_line - start_line + 1 > 120:
            raise ValueError("invalid GitLab code line range")
        content = await self._raw(normalized.as_posix())
        lines = content.splitlines()[start_line - 1 : end_line]
        if not lines:
            raise ValueError("requested GitLab code range is empty")
        return CodeExcerpt(
            workspace=self._project,
            revision=self._commit,
            path=normalized.as_posix(),
            start_line=start_line,
            end_line=start_line + len(lines) - 1,
            content="\n".join(
                f"{start_line + index}: {line}" for index, line in enumerate(lines)
            ),
        )

    async def _tree(self) -> tuple[str, ...]:
        project = quote(self._project, safe="")
        response = await self._client.get(
            f"{self._base}/api/v4/projects/{project}/repository/tree",
            params={"ref": self._commit, "recursive": "true", "per_page": self._max_files},
            headers=self._headers,
        )
        response.raise_for_status()
        values = response.json()
        if not isinstance(values, list):
            raise ValueError("invalid GitLab tree response")
        return tuple(
            str(item["path"])
            for item in values[: self._max_files]
            if item.get("type") == "blob"
            and PurePosixPath(str(item.get("path", ""))).suffix.casefold() in self._EXTENSIONS
        )

    async def _raw(self, path: str) -> str:
        if path in self._cache:
            return self._cache[path]
        project = quote(self._project, safe="")
        encoded_path = quote(path, safe="")
        response = await self._client.get(
            f"{self._base}/api/v4/projects/{project}/repository/files/{encoded_path}/raw",
            params={"ref": self._commit},
            headers=self._headers,
        )
        response.raise_for_status()
        if len(response.content) > self._max_file_bytes:
            raise ValueError("GitLab source file exceeds byte limit")
        self._cache[path] = response.text
        return response.text


class FallbackCodeRepository:
    """远程快照不可用时安全降级到已授权的本地 Repository。"""

    def __init__(self, primary: CodeRepository, fallback: CodeRepository) -> None:
        self._primary = primary
        self._fallback = fallback

    async def search(self, query: str, *, limit: int) -> tuple[CodeMatch, ...]:
        try:
            return await self._primary.search(query, limit=limit)
        except (httpx.HTTPError, TimeoutError):
            return await self._fallback.search(query, limit=limit)

    async def read(self, path: str, *, start_line: int, end_line: int) -> CodeExcerpt:
        try:
            return await self._primary.read(path, start_line=start_line, end_line=end_line)
        except (httpx.HTTPError, TimeoutError):
            return await self._fallback.read(path, start_line=start_line, end_line=end_line)
