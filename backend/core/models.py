from django.conf import settings
from django.db import models


class IdempotencyRecord(models.Model):
    """Stores the response of a write request sent with ``Idempotency-Key``.

    Replays with the same key and payload get the original response, so a
    retry after a timeout cannot create a second result or fixture set.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="idempotency_records",
    )
    key = models.CharField(max_length=100)
    endpoint = models.CharField(max_length=80)
    request_hash = models.CharField(max_length=64)
    status_code = models.PositiveSmallIntegerField(default=0)
    response_body = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "key", "endpoint"], name="unique_idempotency_key"
            )
        ]

    def __str__(self):  # pragma: no cover
        return f"{self.endpoint}:{self.key}"
