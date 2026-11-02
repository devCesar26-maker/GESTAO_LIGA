"""CSRF failure response in the standard ``{code, message}`` shape.

Django calls ``settings.CSRF_FAILURE_VIEW`` when a request does not carry a
valid token; we answer 403 ``CSRF_FAILED`` instead of the default HTML page so
the frontend can show the friendly message.
"""
from django.http import JsonResponse

from .messages import MESSAGES


def csrf_failure(request, reason: str = "") -> JsonResponse:
    return JsonResponse(
        {"code": "CSRF_FAILED", "message": MESSAGES["CSRF_FAILED"]}, status=403
    )
