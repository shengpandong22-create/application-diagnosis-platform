from datetime import UTC, datetime
from typing import Protocol


class RedisScriptClient(Protocol):
    async def eval(self, script: str, numkeys: int, *values: object) -> object: ...


class RedisDeduplicationStore:
    """使用单条 Lua 脚本完成 SET NX PX，声明和 TTL 清理是原子的。"""

    CLAIM_SCRIPT = """
local claimed = redis.call('SET', KEYS[1], '1', 'PX', ARGV[1], 'NX')
if claimed then return 1 else return 0 end
""".strip()

    def __init__(self, client: RedisScriptClient, *, key_prefix: str = "appdiag:dedup:") -> None:
        self._client = client
        self._prefix = key_prefix

    async def claim(self, key: str, *, expires_at: datetime) -> bool:
        now = datetime.now(UTC)
        ttl_ms = max(1, int((expires_at - now).total_seconds() * 1000))
        result = await self._client.eval(
            self.CLAIM_SCRIPT, 1, f"{self._prefix}{key}", ttl_ms
        )
        return int(result or 0) == 1
