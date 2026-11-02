"""Authentication helpers: webhook shared secret and management API key."""
import hmac

from fastapi import Header, HTTPException

from app.config import get_settings


def _equal(a: str, b: str) -> bool:
    # Constant-time comparison so response timing cannot be used to guess a secret.
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def verify_webhook_secret(provided: str | None) -> None:
    """Raise 401 unless `provided` matches WEBHOOK_SECRET.

    An empty WEBHOOK_SECRET disables the check; startup refuses that in production.
    """
    expected = get_settings().webhook_secret
    if not expected:
        return
    if not provided or not _equal(provided, expected):
        raise HTTPException(status_code=401, detail="Invalid webhook secret")


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """FastAPI dependency protecting every /api/* endpoint (they expose lead PII)."""
    settings = get_settings()
    if not settings.api_key:
        if settings.is_production:
            raise HTTPException(status_code=503, detail="API_KEY is not configured on the server")
        return
    if not x_api_key or not _equal(x_api_key, settings.api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header")
