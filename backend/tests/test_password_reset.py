import json
import re
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient

from accounts.models import User
from core.messages import MESSAGES

PASSWORD = "SenhaForte123"
NEW_PASSWORD = "OutraSenha456"
EMAIL = "reset@teste.com"


@pytest.fixture
def mailbox(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.FRONTEND_URL = "https://liga.test"
    mail.outbox = []
    yield mail.outbox
    mail.outbox = []


def request_reset(api, email=EMAIL):
    return api.post(
        "/api/auth/password-reset/", {"email": email}, format="json"
    )


def confirm_reset(api, uid, token, password=NEW_PASSWORD):
    return api.post(
        "/api/auth/password-reset/confirm/",
        {"uid": uid, "token": token, "password": password},
        format="json",
    )


def reset_credentials(message) -> tuple[str, str]:
    match = re.search(
        r"/redefinir-senha\?uid=([^&\s]+)&token=([^\s]+)", message.body
    )
    assert match, message.body
    return match.group(1), match.group(2)


def do_login(api, email, password):
    return api.post(
        "/api/auth/login/", {"email": email, "password": password}, format="json"
    )


@pytest.mark.django_db
def test_request_sends_email_for_existing_user(league, make_user, api, mailbox):
    make_user(EMAIL, "Reset", "Reset FC", password=PASSWORD)

    response = request_reset(api, "RESET@teste.com")

    assert response.status_code == 200
    assert response.json() == {
        "code": "PASSWORD_RESET_SENT",
        "message": MESSAGES["PASSWORD_RESET_SENT"],
    }
    assert len(mailbox) == 1
    message = mailbox[0]
    assert message.to == [f"Reset <{EMAIL}>"]
    assert "Liga eFootball" in message.subject
    assert "https://liga.test/redefinir-senha?uid=" in message.body
    uid, token = reset_credentials(message)
    assert uid
    assert token


@pytest.mark.django_db
def test_request_does_not_reveal_whether_the_email_exists(
    league, make_user, api, mailbox
):
    make_user(EMAIL, "Reset", "Reset FC", password=PASSWORD)

    existing = request_reset(api, EMAIL)
    unknown = request_reset(api, "ninguem@teste.com")

    assert existing.status_code == unknown.status_code == 200
    assert existing.json() == unknown.json() == {
        "code": "PASSWORD_RESET_SENT",
        "message": MESSAGES["PASSWORD_RESET_SENT"],
    }
    # Only the existing account triggered an email.
    assert len(mailbox) == 1


@pytest.mark.django_db
def test_inactive_user_does_not_receive_reset_email(
    league, make_user, api, mailbox
):
    user = make_user(EMAIL, "Reset", "Reset FC", password=PASSWORD)
    user.is_active = False
    user.save(update_fields=["is_active"])

    response = request_reset(api)

    assert response.status_code == 200
    assert response.json()["code"] == "PASSWORD_RESET_SENT"
    assert mailbox == []


@pytest.mark.django_db
def test_confirm_changes_password_and_token_is_single_use(
    league, make_user, api, mailbox
):
    user = make_user(EMAIL, "Reset", "Reset FC", password=PASSWORD)
    assert request_reset(api).status_code == 200
    uid, token = reset_credentials(mailbox[0])

    response = confirm_reset(api, uid, token)

    assert response.status_code == 200
    assert response.json() == {
        "code": "PASSWORD_RESET_SUCCESS",
        "message": MESSAGES["PASSWORD_RESET_SUCCESS"],
    }
    assert response.cookies[settings.AUTH_ACCESS_COOKIE].value == ""
    assert response.cookies[settings.AUTH_REFRESH_COOKIE].value == ""

    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)
    assert not user.check_password(PASSWORD)
    assert do_login(api, EMAIL, PASSWORD).status_code == 401
    assert do_login(api, EMAIL, NEW_PASSWORD).status_code == 200

    # The same token cannot be used again (the password hash changed).
    replay = confirm_reset(api, uid, token, password="MaisUmaSenha789")
    assert replay.status_code == 400
    assert replay.json()["code"] == "PASSWORD_RESET_INVALID"


@pytest.mark.django_db
def test_confirm_rejects_invalid_token(league, make_user, api):
    make_user(EMAIL, "Reset", "Reset FC", password=PASSWORD)

    response = confirm_reset(api, "not-a-uid", "not-a-token")

    assert response.status_code == 400
    assert response.json() == {
        "code": "PASSWORD_RESET_INVALID",
        "message": MESSAGES["PASSWORD_RESET_INVALID"],
    }


@pytest.mark.django_db
def test_confirm_rejects_expired_token(league, make_user, api):
    user = make_user(EMAIL, "Reset", "Reset FC", password=PASSWORD)
    old_now = datetime.now() - timedelta(
        seconds=settings.PASSWORD_RESET_TIMEOUT + 60
    )
    with patch.object(default_token_generator, "_now", return_value=old_now):
        token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))

    response = confirm_reset(api, uid, token)

    assert response.status_code == 400
    assert response.json()["code"] == "PASSWORD_RESET_INVALID"
    user.refresh_from_db()
    assert user.check_password(PASSWORD)


@pytest.mark.django_db
def test_confirm_rejects_weak_password(league, make_user, api, mailbox):
    user = make_user(EMAIL, "Reset", "Reset FC", password=PASSWORD)
    assert request_reset(api).status_code == 200
    uid, token = reset_credentials(mailbox[0])

    response = confirm_reset(api, uid, token, password="123")

    assert response.status_code == 400
    assert response.json()["code"] == "WEAK_PASSWORD"
    user.refresh_from_db()
    assert user.check_password(PASSWORD)


@pytest.mark.django_db
def test_reset_invalidates_existing_refresh_tokens(
    league, make_user, api, mailbox
):
    make_user(EMAIL, "Reset", "Reset FC", password=PASSWORD)
    assert do_login(api, EMAIL, PASSWORD).status_code == 200
    old_refresh = api.cookies[settings.AUTH_REFRESH_COOKIE].value
    assert old_refresh

    resetter = APIClient()
    assert request_reset(resetter).status_code == 200
    uid, token = reset_credentials(mailbox[0])
    assert confirm_reset(resetter, uid, token).status_code == 200

    # The old session cannot rotate its refresh token after the reset.
    api.cookies[settings.AUTH_REFRESH_COOKIE] = old_refresh
    response = api.post("/api/auth/refresh/", {}, format="json")
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_TOKEN"


@pytest.mark.django_db
def test_brevo_api_is_used_when_key_is_configured(league, make_user, api, settings):
    settings.BREVO_API_KEY = "xkeysib-test"
    settings.FRONTEND_URL = "https://liga.test"
    settings.DEFAULT_FROM_EMAIL = "Liga Amigos <no-reply@liga-amigos.test>"
    make_user(EMAIL, "Reset", "Reset FC", password=PASSWORD)

    response_mock = MagicMock()
    response_mock.status = 201
    response_mock.__enter__.return_value = response_mock
    with patch(
        "core.mailer.urllib.request.urlopen", return_value=response_mock
    ) as urlopen:
        response = request_reset(api)

    assert response.status_code == 200
    assert response.json()["code"] == "PASSWORD_RESET_SENT"
    urlopen.assert_called_once()
    request = urlopen.call_args.args[0]
    assert request.full_url == "https://api.brevo.com/v3/smtp/email"
    assert request.get_header("Api-key") == "xkeysib-test"

    payload = json.loads(request.data.decode("utf-8"))
    assert payload["sender"] == {
        "name": "Liga Amigos",
        "email": "no-reply@liga-amigos.test",
    }
    assert payload["to"] == [{"email": EMAIL, "name": "Reset"}]
    assert payload["subject"] == "Redefinição de senha — Liga eFootball"
    assert "https://liga.test/redefinir-senha?uid=" in payload["textContent"]
    assert "https://liga.test/redefinir-senha?uid=" in payload["htmlContent"]
