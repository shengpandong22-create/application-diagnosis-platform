import asyncio
from datetime import UTC, datetime, timedelta

from app_diagnosis.adapters.enterprise import RedisDeduplicationStore


class FakeRedis:
    def __init__(self) -> None:
        self.keys: set[str] = set()
        self.lock = asyncio.Lock()
        self.calls: list[tuple] = []

    async def eval(self, script: str, numkeys: int, *values: object) -> int:
        self.calls.append((script, numkeys, *values))
        async with self.lock:
            key = str(values[0])
            if key in self.keys:
                return 0
            self.keys.add(key)
            return 1


async def test_redis_claim_is_atomic_and_has_positive_ttl() -> None:
    client = FakeRedis()
    store = RedisDeduplicationStore(client)
    results = await asyncio.gather(
        *(
            store.claim("same", expires_at=datetime.now(UTC) + timedelta(minutes=5))
            for _ in range(20)
        )
    )
    assert sum(results) == 1
    assert all(call[1] == 1 and int(call[3]) > 0 for call in client.calls)
    assert "PX" in RedisDeduplicationStore.CLAIM_SCRIPT
    assert "NX" in RedisDeduplicationStore.CLAIM_SCRIPT
