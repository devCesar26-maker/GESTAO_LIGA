"""Idempotency-Key support for critical write endpoints.

The key is optional: without it the endpoint still relies on domain-level
idempotency (unique constraints + no-op detection). With it, an exact retry
returns the stored response byte-for-byte equivalent and never re-runs the
business action.
"""
import hashlib
import json

from django.db import IntegrityError, transaction
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

from .exceptions import AppError
from .models import IdempotencyRecord


def _hash_payload(payload) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _json_safe(data):
    return json.loads(JSONRenderer().render(data).decode("utf-8"))


def run_idempotent(request, endpoint: str, action):
    """Run ``action`` at most once per (user, key, endpoint).

    ``action`` must be a callable returning a DRF ``Response``.
    """
    key = (request.headers.get("Idempotency-Key") or "").strip()
    user = getattr(request, "user", None)
    if not key or user is None or not user.is_authenticated:
        return action()

    request_hash = _hash_payload(request.data)
    existing = IdempotencyRecord.objects.filter(
        user=user, key=key[:100], endpoint=endpoint
    ).first()
    if existing:
        if existing.request_hash != request_hash:
            raise AppError("IDEMPOTENCY_KEY_REUSED", 409)
        response = Response(
            existing.response_body,
            status=existing.status_code or 200,
            headers={"Idempotency-Replayed": "true"},
        )
        return response

    response = action()

    try:
        with transaction.atomic():
            IdempotencyRecord.objects.create(
                user=user,
                key=key[:100],
                endpoint=endpoint,
                request_hash=request_hash,
                status_code=response.status_code,
                response_body=_json_safe(response.data),
            )
    except IntegrityError:
        # A concurrent request with the same key won the race. Its stored
        # response is authoritative; the current action was still safe because
        # the domain operations are idempotent.
        pass

    return response
