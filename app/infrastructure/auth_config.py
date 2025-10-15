# app/infrastructure/auth_config.py

from fastapi_users.authentication import (
    AuthenticationBackend,
    CookieTransport,
    JWTStrategy,
)
from config.settings import settings


# Cookie transport for authentication
cookie_transport = CookieTransport(
    cookie_name="l2p_auth",
    cookie_max_age=settings.JWT_LIFETIME_SECONDS,
    cookie_httponly=True,
    cookie_samesite="lax",
)


def get_jwt_strategy() -> JWTStrategy:
    """JWT strategy for authentication"""
    return JWTStrategy(
        secret=settings.SECRET_KEY,
        lifetime_seconds=settings.JWT_LIFETIME_SECONDS,
    )


# Authentication backend combining transport and strategy
auth_backend = AuthenticationBackend(
    name="jwt-cookie",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)
