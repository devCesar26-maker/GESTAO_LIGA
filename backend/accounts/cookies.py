"""HttpOnly cookie helpers for the JWT session.

The tokens never reach JavaScript: the API sets them as HttpOnly cookies and the
browser sends them automatically on every API request. A readable ``csrftoken``
cookie plus the ``X-CSRFToken`` header protects write requests, so a stolen
cookie cannot be replayed from another site.
"""
from django.conf import settings


def _lifetime_seconds(key: str) -> int:
    return int(settings.SIMPLE_JWT[key].total_seconds())


def _secure() -> bool:
    """Secure flag follows DEBUG at request time, so tests can exercise both."""
    return not settings.DEBUG


def set_access_cookie(response, raw_token: str):
    response.set_cookie(
        settings.AUTH_ACCESS_COOKIE,
        raw_token,
        max_age=_lifetime_seconds("ACCESS_TOKEN_LIFETIME"),
        path=settings.AUTH_ACCESS_COOKIE_PATH,
        httponly=True,
        secure=_secure(),
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )
    return response


def set_refresh_cookie(response, raw_token: str):
    response.set_cookie(
        settings.AUTH_REFRESH_COOKIE,
        raw_token,
        max_age=_lifetime_seconds("REFRESH_TOKEN_LIFETIME"),
        path=settings.AUTH_REFRESH_COOKIE_PATH,
        httponly=True,
        secure=_secure(),
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )
    return response


def set_auth_cookies(response, *, access_token: str, refresh_token: str | None = None):
    set_access_cookie(response, access_token)
    if refresh_token:
        set_refresh_cookie(response, refresh_token)
    return response


def clear_auth_cookies(response):
    """Remove both cookies; paths must match the ones used when setting them."""
    response.delete_cookie(
        settings.AUTH_ACCESS_COOKIE, path=settings.AUTH_ACCESS_COOKIE_PATH
    )
    response.delete_cookie(
        settings.AUTH_REFRESH_COOKIE, path=settings.AUTH_REFRESH_COOKIE_PATH
    )
    return response
