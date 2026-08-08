import base64

import httpx
import pytest

from app_diagnosis.adapters.code import GitHubSnapshotRepository

COMMIT = "b" * 40
REPOSITORY = "owner/repo"


def repository(client: httpx.AsyncClient, **overrides) -> GitHubSnapshotRepository:
    values = {
        "client": client,
        "repository": REPOSITORY,
        "commit": COMMIT,
        "allowed_repositories": {REPOSITORY},
        "allowed_commits": {COMMIT},
    }
    values.update(overrides)
    return GitHubSnapshotRepository(**values)


async def test_github_snapshot_uses_commit_for_tree_and_raw() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if "/git/trees/" in request.url.path:
            return httpx.Response(
                200, json={"tree": [{"type": "blob", "path": "src/App.java"}]}
            )
        return httpx.Response(
            200,
            json={
                "encoding": "base64",
                "content": base64.b64encode(b"class App {}").decode(),
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        repo = repository(client)
        assert await repo.search("App", limit=2)
        excerpt = await repo.read("src/App.java", start_line=1, end_line=1)
    assert excerpt.revision == COMMIT
    assert all(COMMIT in str(request.url) for request in requests)
    assert all(request.url.host == "api.github.com" for request in requests)


async def test_github_snapshot_rejects_unlisted_scope() -> None:
    async with httpx.AsyncClient() as client:
        with pytest.raises(PermissionError):
            repository(client, repository="other/repo")
        with pytest.raises(PermissionError):
            repository(client, commit="main")
