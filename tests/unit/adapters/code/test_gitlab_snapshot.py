import httpx
import pytest

from app_diagnosis.adapters.code.gitlab_snapshot import GitLabSnapshotRepository

COMMIT = "a" * 40


def repository(client: httpx.AsyncClient, **overrides) -> GitLabSnapshotRepository:
    values = {
        "client": client,
        "base_url": "https://gitlab.example.com",
        "project": "team/app",
        "commit": COMMIT,
        "allowed_projects": {"team/app"},
        "allowed_commits": {COMMIT},
        "private_token": "token",
    }
    values.update(overrides)
    return GitLabSnapshotRepository(**values)


async def test_gitlab_reads_only_fixed_commit_snapshot() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/repository/tree"):
            return httpx.Response(200, json=[{"type": "blob", "path": "src/App.java"}])
        return httpx.Response(200, text="class App { RuntimeException error; }")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        repo = repository(client)
        matches = await repo.search("RuntimeException", limit=3)
        excerpt = await repo.read("src/App.java", start_line=1, end_line=1)
    assert matches[0].path == "src/App.java"
    assert excerpt.revision == COMMIT
    assert all(request.url.params.get("ref") == COMMIT for request in requests)


async def test_gitlab_rejects_project_commit_and_path_outside_allowlist() -> None:
    async with httpx.AsyncClient() as client:
        with pytest.raises(PermissionError):
            repository(client, project="other/app")
        with pytest.raises(PermissionError):
            repository(client, commit="main")
        repo = repository(client)
        with pytest.raises(PermissionError):
            await repo.read("../secret", start_line=1, end_line=1)
