import time

from fastapi import HTTPException, status
from redis.asyncio import Redis
from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply a fixed-window Redis rate limit per client address."""

    def __init__(self, app, redis: Redis, limit: int) -> None:
        super().__init__(app)
        self.redis = redis
        self.limit = limit

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in {"/health/live", "/health/ready", "/metrics"}:
            return await call_next(request)

        client = request.client.host if request.client else "unknown"
        window = int(time.time() // 60)
        key = f"rate-limit:{client}:{window}"
        try:
            count = await self.redis.incr(key)
            if count == 1:
                await self.redis.expire(key, 60)
        except RedisError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Rate limiting service is unavailable.",
            ) from error

        if count > self.limit:
            response = Response(
                content='{"detail":"Rate limit exceeded."}',
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                media_type="application/json",
            )
            response.headers["Retry-After"] = str(60 - int(time.time() % 60))
            return response
        return await call_next(request)
