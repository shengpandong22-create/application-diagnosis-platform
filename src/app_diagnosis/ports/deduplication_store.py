from datetime import datetime
from typing import Protocol


class DeduplicationStore(Protocol):
    async def claim(self, key: str, *, expires_at: datetime) -> bool:
        """首次声明返回 True；未过期的重复键返回 False。"""
        ...
