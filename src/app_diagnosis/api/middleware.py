import logging
import re
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request, Response

from app_diagnosis.observability import bind_request_id, reset_request_id

logger = logging.getLogger("app_diagnosis.http")
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def install_request_context_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_context(request: Request, call_next) -> Response:
        supplied = request.headers.get("X-Request-ID", "")
        request_id = supplied if _SAFE_REQUEST_ID.fullmatch(supplied) else str(uuid4())
        request.state.request_id = request_id
        token = bind_request_id(request_id)
        started = perf_counter()
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            logger.info(
                "http_request_completed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round((perf_counter() - started) * 1000, 2),
                },
            )
            return response
        finally:
            reset_request_id(token)
