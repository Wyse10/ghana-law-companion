import json
import logging
import time
from uuid import uuid4

from prometheus_client import Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_COUNT = Counter(
    "ghana_law_http_requests_total",
    "Total HTTP requests.",
    ("method", "path", "status_code"),
)
REQUEST_LATENCY = Histogram(
    "ghana_law_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ("method", "path"),
)


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
        recorded = False
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            REQUEST_COUNT.labels(
                request.method,
                request.url.path,
                str(status_code),
            ).inc()
            REQUEST_LATENCY.labels(
                request.method,
                request.url.path,
            ).observe(time.perf_counter() - started)
            recorded = True
            return response
        finally:
            if not recorded:
                REQUEST_COUNT.labels(
                    request.method,
                    request.url.path,
                    "500",
                ).inc()
                REQUEST_LATENCY.labels(
                    request.method,
                    request.url.path,
                ).observe(time.perf_counter() - started)
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


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add browser security headers to every HTTP response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response


def metrics_response() -> Response:
    """Return metrics in Prometheus text format."""
    return Response(
        content=generate_latest(),
        media_type="text/plain; version=0.0.4",
    )
