import asyncio
import json

import httpx

from app_diagnosis.adapters.code import GitHubSnapshotRepository
from app_diagnosis.bootstrap.settings import Settings

REPOSITORY = "shengpandong22-create/diagnosis-java-lab"
COMMIT = "025f335f309cd2bde9cc7cc536209fc068ad7379"
ORDER_SERVICE = "src/main/java/dev/agentstudy/lab/OrderService.java"


async def main() -> None:
    settings = Settings()
    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
        repository = GitHubSnapshotRepository(
            client=client,
            repository=REPOSITORY,
            commit=COMMIT,
            allowed_repositories={REPOSITORY},
            allowed_commits={COMMIT},
            token=settings.github_token.get_secret_value(),
        )
        excerpt = await repository.read(ORDER_SERVICE, start_line=1, end_line=22)
        matches = await repository.search("class OrderService", limit=3)
    if excerpt.revision != COMMIT or "class OrderService" not in excerpt.content:
        raise AssertionError("GitHub fixed commit excerpt verification failed")
    if not any(item.path == ORDER_SERVICE for item in matches):
        paths = sorted({item.path for item in matches})
        raise AssertionError(f"GitHub fixed commit search verification failed: {paths}")
    print(json.dumps({
        "repository": REPOSITORY,
        "commit": COMMIT,
        "path": excerpt.path,
        "search_matches": len(matches),
        "fixed_commit_verified": True,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
