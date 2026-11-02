"""Centralized API error handling.

Every error leaves the API as ``{"code": "...", "message": "..."}`` where the
message is written in Brazilian Portuguese and comes from ``core.messages``.
Views and services raise :class:`AppError` instead of building responses by
hand, which keeps the contract consistent.
"""
import logging

from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    MethodNotAllowed,
    NotAuthenticated,
    NotFound,
    ParseError,
    PermissionDenied,
    Throttled,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from .messages import MESSAGES, message_for

logger = logging.getLogger(__name__)


class AppError(APIException):
    """API exception carrying a message code from ``core.messages``.

    ``status_code`` is the HTTP status; ``extra`` is merged into the response
    body for non-sensitive structured data (e.g. validation details).
    """

    def __init__(self, code: str, status_code: int = 400, extra: dict | None = None):
        self.code = code
        self.status_code = status_code
        self.extra = extra or {}
        super().__init__(detail=message_for(code), code=code)


def _error_response(code: str, status_code: int, extra: dict | None = None) -> Response:
    body = {"code": code, "message": message_for(code)}
    if extra:
        body.update(extra)
    return Response(body, status=status_code)


def _flatten_validation_errors(detail) -> dict:
    """Turn DRF/serializer errors into a plain ``{field: [messages]}`` dict."""
    if isinstance(detail, dict):
        return {str(key): _flatten_validation_errors(value) for key, value in detail.items()}
    if isinstance(detail, (list, tuple)):
        return [_flatten_validation_errors(item) for item in detail]
    return str(detail)


def api_exception_handler(exc, context):
    """DRF exception handler that enforces the standard friendly error body."""

    if isinstance(exc, AppError):
        return _error_response(exc.code, exc.status_code, exc.extra)

    if isinstance(exc, (InvalidToken, TokenError)):
        # simplejwt flags expired tokens with "expired"; everything else is a
        # malformed/revoked token.
        raw = str(exc)
        if "expired" in raw.lower():
            return _error_response("TOKEN_EXPIRED", status.HTTP_401_UNAUTHORIZED)
        return _error_response("INVALID_TOKEN", status.HTTP_401_UNAUTHORIZED)

    if isinstance(exc, (Http404, NotFound)):
        return _error_response("NOT_FOUND", status.HTTP_404_NOT_FOUND)

    if isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
        return _error_response("NOT_AUTHENTICATED", status.HTTP_401_UNAUTHORIZED)

    if isinstance(exc, PermissionDenied):
        return _error_response("FORBIDDEN", status.HTTP_403_FORBIDDEN)

    if isinstance(exc, Throttled):
        wait = int(exc.wait) if exc.wait else None
        extra = {"retry_after_seconds": wait} if wait else None
        return _error_response(
            "TOO_MANY_REQUESTS", status.HTTP_429_TOO_MANY_REQUESTS, extra
        )

    if isinstance(exc, (ValidationError, ParseError)):
        details = getattr(exc, "detail", None)
        return _error_response(
            "INVALID_DATA",
            status.HTTP_400_BAD_REQUEST,
            {"errors": _flatten_validation_errors(details)} if details else None,
        )

    if isinstance(exc, MethodNotAllowed):
        return _error_response("METHOD_NOT_ALLOWED", status.HTTP_405_METHOD_NOT_ALLOWED)

    # Imported lazily to avoid a circular import: DRF loads the default
    # authentication classes (and therefore this module) while
    # rest_framework.views is still being initialized.
    from rest_framework.views import exception_handler as drf_exception_handler

    # Fall back to DRF for anything else it knows about (e.g. UnsupportedMediaType),
    # still wrapping the body in our standard format.
    response = drf_exception_handler(exc, context)
    if response is None:
        # Unhandled exception: the middleware produces the friendly 500 body.
        return None

    if isinstance(exc, APIException):
        code = getattr(exc, "code", None)
        if code and code in MESSAGES:
            return _error_response(code, response.status_code)
        if response.status_code == 401:
            return _error_response("NOT_AUTHENTICATED", 401)
        if response.status_code == 403:
            return _error_response("FORBIDDEN", 403)
        if response.status_code == 404:
            return _error_response("NOT_FOUND", 404)
        return _error_response("INVALID_DATA", response.status_code)

    return response


__all__ = ["AppError", "api_exception_handler"]
