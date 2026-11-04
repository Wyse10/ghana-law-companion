import hmac

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from src.api.config import get_settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(
    provided_key: str | None = Security(api_key_header),
) -> None:
    """Require the configured API key when authentication is enabled."""
    settings = get_settings()
    expected_key = settings.api_key
    authentication_enabled = settings.require_api_key or expected_key is not None

    if not authentication_enabled:
        return
    if expected_key is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API authentication is not configured.",
        )
    if provided_key is None or not hmac.compare_digest(
        provided_key,
        expected_key.get_secret_value(),
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
