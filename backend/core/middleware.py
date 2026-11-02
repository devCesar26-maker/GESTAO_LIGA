"""Cross-cutting HTTP concerns: friendly 500s, CSRF for the API and CSP headers.

DRF handles expected exceptions, but a bug in a view would otherwise produce an
HTML stack trace (or Django's technical page). The frontend must always receive
the friendly ``{code, message}`` shape, so this middleware catches anything
raised under ``/api/`` and logs the traceback server-side.
"""
import logging

from django.http import JsonResponse
from django.middleware.csrf import CsrfViewMiddleware
from django.utils.deprecation import MiddlewareMixin

from .messages import MESSAGES

logger = logging.getLogger(__name__)

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})

CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        # Vite emits an external stylesheet; inline styles are only allowed for
        # the theme attribute and keep no script execution rights.
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data:",
        "font-src 'self' data:",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)


class ApiErrorMiddleware:
    """New-style middleware that catches exceptions raised by any inner layer."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except Exception:
            if not request.path.startswith("/api/"):
                raise
            logger.exception("Unhandled error on %s %s", request.method, request.path)
            return JsonResponse(
                {"code": "SERVER_ERROR", "message": MESSAGES["SERVER_ERROR"]},
                status=500,
            )


class ApiCsrfMiddleware(CsrfViewMiddleware):
    """Enforce Django's CSRF check on every unsafe ``/api/`` request.

    DRF's ``APIView`` is ``csrf_exempt`` (it only checks CSRF through
    ``SessionAuthentication``), and this project authenticates with cookies, so
    the check has to be explicit. Login, refresh and logout are covered too:
    without a valid token they answer 403 ``CSRF_FAILED``.
    """

    def process_view(self, request, callback, callback_args, callback_kwargs):
        if not request.path.startswith("/api/") or request.method in SAFE_METHODS:
            return super().process_view(
                request, callback, callback_args, callback_kwargs
            )
        if getattr(request, "_dont_enforce_csrf_checks", False):
            return None

        was_exempt = getattr(callback, "csrf_exempt", False)
        try:
            # Reuse Django's full validation (token comparison + origin checks).
            callback.csrf_exempt = False
            return super().process_view(
                request, callback, callback_args, callback_kwargs
            )
        finally:
            callback.csrf_exempt = was_exempt


class SecurityHeadersMiddleware(MiddlewareMixin):
    """Security headers that must also be present on error responses."""

    def process_response(self, request, response):
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
        return response
