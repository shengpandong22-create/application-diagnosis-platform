import base64
import re
from collections.abc import Collection
from pathlib import PurePosixPath
from urllib.parse import quote

import httpx

from app_diagnosis.ports.code_repository import CodeExcerpt, CodeMatch


class GitHubSnapshotRepository:
    """读取公开或已授权 GitHub 仓库中的固定 commit 快照。"""

    _COMMIT = re.compile(r"^[0-9a-fA-F]{40}$")
    _EXTENSIONS = frozenset({".java", ".py", ".ts", ".tsx", ".js", ".json", ".yml", ".yaml"})

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        repository: str,
        commit: str,
        allowed_repositories: Collection[str],
        allowed_commits: Collection[str],
        token: str = "",
        max_files: int = 100,
        max_file_bytes: int = 262_144,
    ) -> None:
        if repository not in set(allowed_repositories):
            raise PermissionError("GitHub repository is not allowlisted")
        if commit not in set(allowed_commits) or not self._COMMIT.fullmatch(commit):
            raise PermissionError("GitHub commit is not allowlisted")
        if len(repository.split("/")) != 2:
            raise ValueError("GitHub repository must use owner/name format")
        self._client = client
        self._repository = repository
        self._commit = commit
        self._headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        }
        self._max_files = max_files
        self._max_file_bytes = max_file_bytes
        self._cache: dict[str, str] = {}

    async def search(self, query: str, *, limit: int) -> tuple[CodeMatch, ...]:
        needle = query.strip().casefold()
        if not needle or limit < 1 or limit > 50:
            raise ValueError("invalid GitHub code search")
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
            raise PermissionError("GitHub code path is outside snapshot")
        if start_line < 1 or end_line < start_line or end_line - start_line + 1 > 120:
            raise ValueError("invalid GitHub code line range")
        content = await self._raw(normalized.as_posix())
        lines = content.splitlines()[start_line - 1 : end_line]
        if not lines:
            raise ValueError("requested GitHub code range is empty")
        return CodeExcerpt(
            workspace=self._repository,
            revision=self._commit,
            path=normalized.as_posix(),
            start_line=start_line,
            end_line=start_line + len(lines) - 1,
            content="\n".join(
                f"{start_line + index}: {line}" for index, line in enumerate(lines)
            ),
        )

    async def _tree(self) -> tuple[str, ...]:
        response = await self._client.get(
            f"https://api.github.com/repos/{self._repository}/git/trees/{self._commit}",
            params={"recursive": "1"},
            headers=self._headers,
        )
        response.raise_for_status()
        values = response.json().get("tree")
        if not isinstance(values, list):
            raise ValueError("invalid GitHub tree response")
        return tuple(
            str(item["path"])
            for item in values[: self._max_files]
            if item.get("type") == "blob"
            and PurePosixPath(str(item.get("path", ""))).suffix.casefold() in self._EXTENSIONS
        )

    async def _raw(self, path: str) -> str:
        if path in self._cache:
            return self._cache[path]
        encoded = "/".join(quote(part, safe="") for part in PurePosixPath(path).parts)
        response = await self._client.get(
            f"https://api.github.com/repos/{self._repository}/contents/{encoded}",
            params={"ref": self._commit},
            headers=self._headers,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("encoding") != "base64" or not isinstance(payload.get("content"), str):
            raise ValueError("invalid GitHub contents response")
        encoded_content = "".join(payload["content"].split())
        content = base64.b64decode(encoded_content, validate=True)
        if len(content) > self._max_file_bytes:
            raise ValueError("GitHub source file exceeds byte limit")
        decoded = content.decode("utf-8")
        self._cache[path] = decoded
        return decoded
