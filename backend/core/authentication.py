"""JWT authentication from the HttpOnly session cookie.

The access token is only ever read from the cookie set by the API. Tokens stored
in web storage (or sent as ``Authorization: Bearer``) are not accepted, so an
XSS payload cannot exfiltrate the session and replay it from another machine.
"""
from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import UntypedToken

from .exceptions import AppError


def _is_expired(raw_token: str) -> bool:
    try:
        UntypedToken(raw_token)
    except TokenError as exc:
        return "expired" in str(exc).lower()
    return False


class CookieJWTAuthentication(JWTAuthentication):
    """Translate cookie token failures into our friendly message codes.

    Returning ``None`` for anonymous requests keeps the public read endpoints
    open; the permissions of each view decide what an anonymous user may do.
    """

    def authenticate(self, request):
        raw_token = request.COOKIES.get(settings.AUTH_ACCESS_COOKIE)
        if not raw_token:
            return None

        try:
            validated_token = self.get_validated_token(raw_token)
        except (InvalidToken, TokenError):
            raise AppError(
                "TOKEN_EXPIRED" if _is_expired(raw_token) else "INVALID_TOKEN", 401
            )

        try:
            return self.get_user(validated_token), validated_token
        except Exception:  # user deleted/disabled after the token was issued
            raise AppError("NOT_AUTHENTICATED", 401)
