"""
Security helpers shared across the API.

Goals:
- Avoid hardcoded / weak default secrets in production.
- Provide safe(ish) development fallbacks without leaking secrets.
"""

from __future__ import annotations

import os
import secrets
from loguru import logger


def is_production() -> bool:
    env = (os.getenv("ENVIRONMENT") or "development").strip().lower()
    return env in {"prod", "production"}


def _is_weak_secret(value: str | None, *, min_len: int = 32) -> bool:
    if not value:
        return True
    v = value.strip()
    if len(v) < min_len:
        return True
    if v.lower() in {"change_me_in_production", "changeme", "default", "secret"}:
        return True
    return False


def get_jwt_secret() -> str:
    """
    Returns a JWT secret.

    - Production: must be set and strong, otherwise raise.
    - Development: if missing/weak, generate an ephemeral secret for this process.
    """
    secret = os.getenv("JWT_SECRET")
    if not _is_weak_secret(secret):
        return secret  # type: ignore[return-value]

    if is_production():
        raise RuntimeError("JWT_SECRET manquant ou trop faible (production).")

    # Dev fallback: keep the app running without silently using a known weak value.
    generated = secrets.token_urlsafe(48)
    os.environ["JWT_SECRET"] = generated
    logger.warning("JWT_SECRET manquant/faible: secret ephemere genere pour le mode developpement.")
    return generated


def get_internal_api_secret() -> str:
    """
    Secret used for bot/service-to-API calls (X-API-SECRET).

    - Production: must be set and strong, otherwise raise.
    - Development: if missing/weak, generate an ephemeral secret for this process.
    """
    secret = os.getenv("INTERNAL_API_SECRET")
    if not _is_weak_secret(secret):
        return secret  # type: ignore[return-value]

    if is_production():
        raise RuntimeError("INTERNAL_API_SECRET manquant ou trop faible (production).")

    generated = secrets.token_urlsafe(48)
    os.environ["INTERNAL_API_SECRET"] = generated
    logger.warning("INTERNAL_API_SECRET manquant/faible: secret ephemere genere pour le mode developpement.")
    return generated


def security_headers() -> dict[str, str]:
    """
    Security headers for API JSON responses.
    Note: frontend HTML is served separately (web/), so CSP for the dashboard
    is handled in HTML meta or the web server config.
    """
    return {
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        # API responses should not be cached (tokens, configs, PII).
        "Cache-Control": "no-store",
        "Pragma": "no-cache",
    }

