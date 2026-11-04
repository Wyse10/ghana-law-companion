import json
import logging
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class JsonFormatter(logging.Formatter):
    """Format access records as compact JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "event": "http_request",
            "level": record.levelname.lower(),
            "method": getattr(record, "method", None),
            "path": getattr(record, "path", None),
            "status_code": getattr(record, "status_code", None),
            "duration_ms": getattr(record, "duration_ms", None),
            "request_id": getattr(record, "request_id", None),
        }
        return json.dumps(payload, separators=(",", ":"))


def configure_logging() -> None:
    """Configure one JSON stream handler for application access records."""
    logger = logging.getLogger("ghana_law_companion.access")
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Attach request IDs and emit metadata-only access logs."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid4())
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            logging.getLogger("ghana_law_companion.access").info(
                "request completed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    "request_id": request_id,
                },
            )
