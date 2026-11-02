"""Session security: HttpOnly cookies, CSRF, rotation, logout and headers."""
import json
from pathlib import Path

import pytest
from django.conf import settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from core.messages import MESSAGES

PASSWORD = "SenhaForte123"
EMAIL = "jogador@teste.com"


@pytest.fixture
def player(make_user):
    return make_user(EMAIL, "Jogador", "Time J", password=PASSWORD)


def do_login(client, email=EMAIL, password=PASSWORD):
    return client.post(
        "/api/auth/login/", {"email": email, "password": password}, format="json"
    )


@pytest.mark.django_db
def test_login_sets_httponly_samesite_cookies_and_no_tokens_in_body(league, player, api):
    response = do_login(api)
    assert response.status_code == 200

    body = response.json()
    assert "access" not in body
    assert "refresh" not in body
    assert "token" not in json.dumps(body).lower()
    assert body["user"]["email"] == EMAIL

    access = response.cookies[settings.AUTH_ACCESS_COOKIE]
    assert bool(access.get("httponly")) is True
    assert access["samesite"] == "Lax"
    assert access["path"] == settings.AUTH_ACCESS_COOKIE_PATH
    # DEBUG is False while running the suite, so production flags apply.
    assert bool(access.get("secure")) is (not settings.DEBUG)

    refresh = response.cookies[settings.AUTH_REFRESH_COOKIE]
    assert bool(refresh.get("httponly")) is True
    assert refresh["samesite"] == "Lax"
    assert refresh["path"] == settings.AUTH_REFRESH_COOKIE_PATH
    assert bool(refresh.get("secure")) is (not settings.DEBUG)


@pytest.mark.django_db
def test_cookie_alone_authenticates_and_bearer_header_does_not(league, player, api):
    assert do_login(api).status_code == 200

    me = api.get("/api/auth/me/")
    assert me.status_code == 200
    assert me.json()["email"] == EMAIL

    # A stolen/forged Authorization header is not a session.
    other = APIClient()
    other.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(player)}")
    assert other.get("/api/auth/me/").status_code == 401


@pytest.mark.django_db
def test_write_without_csrf_token_returns_csrf_failed(league, player):
    client = APIClient(enforce_csrf_checks=True)
    response = do_login(client)
    assert response.status_code == 403
    assert response.json() == {
        "code": "CSRF_FAILED",
        "message": MESSAGES["CSRF_FAILED"],
    }


@pytest.mark.django_db
def test_login_works_with_csrf_cookie_and_header(league, player):
    client = APIClient(enforce_csrf_checks=True)
    csrf = client.get("/api/auth/csrf/")
    assert csrf.status_code == 200
    assert client.cookies["csrftoken"].value

    response = client.post(
        "/api/auth/login/",
        {"email": EMAIL, "password": PASSWORD},
        format="json",
        HTTP_X_CSRFTOKEN=csrf.json()["csrfToken"],
    )
    assert response.status_code == 200
    assert client.get("/api/auth/me/").status_code == 200


@pytest.mark.django_db
def test_login_does_not_reveal_whether_the_email_exists(league, player, api):
    unknown = do_login(api, "ninguem@teste.com", "qualquer123")
    wrong_password = do_login(api, EMAIL, "senha-errada")
    assert unknown.status_code == wrong_password.status_code == 401
    assert unknown.json() == wrong_password.json() == {
        "code": "INVALID_CREDENTIALS",
        "message": "Email ou senha incorretos.",
    }


@pytest.mark.django_db
def test_refresh_rotates_and_the_previous_token_is_rejected(league, player, api):
    assert do_login(api).status_code == 200
    old_refresh = api.cookies[settings.AUTH_REFRESH_COOKIE].value
    assert old_refresh

    response = api.post("/api/auth/refresh/", {}, format="json")
    assert response.status_code == 200
    assert "access" not in response.json()

    new_refresh = api.cookies[settings.AUTH_REFRESH_COOKIE].value
    assert new_refresh and new_refresh != old_refresh

    # Replaying the rotated (blacklisted) token must fail.
    api.cookies[settings.AUTH_REFRESH_COOKIE] = old_refresh
    replay = api.post("/api/auth/refresh/", {}, format="json")
    assert replay.status_code == 401
    assert replay.json()["code"] == "INVALID_TOKEN"


@pytest.mark.django_db
def test_refresh_without_cookie_reports_session_expired(league, api):
    response = api.post("/api/auth/refresh/", {}, format="json")
    assert response.status_code == 401
    assert response.json() == {
        "code": "SESSION_EXPIRED",
        "message": MESSAGES["SESSION_EXPIRED"],
    }


@pytest.mark.django_db
def test_logout_clears_cookies_and_invalidates_the_session(league, player, api):
    assert do_login(api).status_code == 200
    refresh_value = api.cookies[settings.AUTH_REFRESH_COOKIE].value

    response = api.post("/api/auth/logout/", {}, format="json")
    assert response.status_code == 200
    assert response.json()["code"] == "LOGGED_OUT"
    assert response.cookies[settings.AUTH_ACCESS_COOKIE].value == ""
    assert response.cookies[settings.AUTH_REFRESH_COOKIE].value == ""

    assert api.get("/api/auth/me/").status_code == 401

    # The blacklisted refresh cannot resurrect the session.
    api.cookies[settings.AUTH_REFRESH_COOKIE] = refresh_value
    assert api.post("/api/auth/refresh/", {}, format="json").status_code == 401


@pytest.mark.django_db
def test_security_headers_are_present(league, api):
    response = api.get("/api/health/")
    assert response["X-Frame-Options"] == "DENY"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Referrer-Policy"] == "same-origin"

    csp = response["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "unsafe-eval" not in csp


@pytest.mark.django_db
def test_hsts_is_enabled_for_production_https_requests(settings, api):
    assert settings.SECURE_HSTS_SECONDS > 0
    assert settings.SECURE_HSTS_INCLUDE_SUBDOMAINS is True

    response = api.get("/api/health/", secure=True)
    header = response["Strict-Transport-Security"]
    assert f"max-age={settings.SECURE_HSTS_SECONDS}" in header
    assert "includeSubDomains" in header


@pytest.mark.django_db
def test_legacy_token_keys_are_removed_on_the_client_source():
    """The cleanup module must list the old localStorage keys."""
    source = (
        Path(settings.ROOT_DIR)
        / "frontend"
        / "src"
        / "lib"
        / "legacyTokenCleanup.js"
    ).read_text(encoding="utf-8")
    assert "liga.access" in source
    assert "liga.refresh" in source
    assert "removeItem" in source
