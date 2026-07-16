import json
import logging
import sys
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    _STANDARD = frozenset(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        request_id = request_id_context.get()
        if request_id:
            payload["request_id"] = request_id
        for key, value in record.__dict__.items():
            if key not in self._STANDARD and not key.startswith("_") and _json_safe(value):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = record.exc_info[0].__name__
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _json_safe(value: object) -> bool:
    return value is None or isinstance(value, (str, int, float, bool, list, tuple, dict))


def configure_logging(level: str) -> None:
    resolved_level = getattr(logging, level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(resolved_level)
    for name in logging.root.manager.loggerDict:
        if name == "app_diagnosis" or name.startswith("app_diagnosis."):
            logging.getLogger(name).disabled = False


def bind_request_id(request_id: str) -> Token[str | None]:
    return request_id_context.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    request_id_context.reset(token)
