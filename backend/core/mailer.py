"""Transactional email delivery.

Brevo's HTTP API is used when ``BREVO_API_KEY`` is configured, so production
only needs one secret. Without a key the project falls back to Django's email
backend: the console backend in development/tests and SMTP when configured.
"""

import json
import urllib.error
import urllib.request
from email.utils import parseaddr

from django.conf import settings
from django.core.mail import EmailMultiAlternatives


class EmailDeliveryError(RuntimeError):
    """Raised when the configured provider rejects or cannot deliver an email."""


def send_transactional_email(
    *, subject: str, text_body: str, html_body: str, to_email: str, to_name: str = ""
):
    if settings.BREVO_API_KEY:
        _send_with_brevo(
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            to_email=to_email,
            to_name=to_name,
        )
        return

    _send_with_django(
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        to_email=to_email,
        to_name=to_name,
    )


def _send_with_brevo(
    *, subject: str, text_body: str, html_body: str, to_email: str, to_name: str = ""
):
    sender_name, sender_email = parseaddr(settings.DEFAULT_FROM_EMAIL)
    if not sender_email:
        raise EmailDeliveryError(
            "DEFAULT_FROM_EMAIL must contain a sender address verified in Brevo."
        )

    recipient = {"email": to_email}
    if to_name:
        recipient["name"] = to_name

    payload = {
        "sender": {"email": sender_email, "name": sender_name or "Biblioteca"},
        "to": [recipient],
        "subject": subject,
        "textContent": text_body,
        "htmlContent": html_body,
    }
    request = urllib.request.Request(
        settings.BREVO_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "accept": "application/json",
            "api-key": settings.BREVO_API_KEY,
            "content-type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=settings.EMAIL_TIMEOUT) as response:
            status_code = getattr(response, "status", 200)
            if status_code >= 300:
                raise EmailDeliveryError(f"Brevo API returned HTTP {status_code}.")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise EmailDeliveryError(
            f"Brevo API returned HTTP {exc.code}: {detail}"
        ) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        reason = getattr(exc, "reason", exc)
        raise EmailDeliveryError(f"Brevo API request failed: {reason}") from exc


def _send_with_django(
    *, subject: str, text_body: str, html_body: str, to_email: str, to_name: str = ""
):
    recipient = f"{to_name} <{to_email}>" if to_name else to_email
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)
