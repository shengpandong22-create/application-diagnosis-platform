from app_diagnosis.ports.log_event_source import DiscoveredLogEvent


class ReplayLogEventSource:
    """测试和本地演示使用的有限事件源，不访问外部资源。"""

    def __init__(self, events: tuple[DiscoveredLogEvent, ...]) -> None:
        self._events = events

    async def collect(self) -> tuple[DiscoveredLogEvent, ...]:
        return self._events
