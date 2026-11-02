import json
from datetime import timedelta

import pytest
from django.test import RequestFactory
from rest_framework.exceptions import Throttled
from rest_framework_simplejwt.tokens import AccessToken

from core.exceptions import api_exception_handler
from core.messages import MESSAGES
from core.middleware import ApiErrorMiddleware

from .helpers import match_between


def assert_standard_error(response, status, code):
    assert response.status_code == status
    body = response.json()
    assert body["code"] == code
    assert body["message"] == MESSAGES[code]
    assert "detail" not in body


@pytest.fixture
def generated(league, players, api, admin):
    api.force_authenticate(admin)
    assert api.post("/api/admin/generate-fixtures/", {}, format="json").status_code == 200
    return league


@pytest.mark.django_db
def test_404_uses_friendly_message(api):
    api.force_authenticate(user=None)
    response = api.get("/api/matches/999999/")
    assert_standard_error(response, 404, "NOT_FOUND")
    assert response.json()["message"] == "Não encontramos o que você procurava."


@pytest.mark.django_db
def test_401_uses_friendly_message(generated, players, api):
    alice, bruno, _ = players
    match = match_between(generated, alice, bruno)
    api.force_authenticate(user=None)
    response = api.post(
        f"/api/matches/{match.pk}/result/",
        {"home_goals": 1, "away_goals": 0},
        format="json",
    )
    assert_standard_error(response, 401, "NOT_AUTHENTICATED")


@pytest.mark.django_db
def test_403_admin_only_uses_friendly_message(league, players, api, make_user):
    regular = make_user("regular@teste.com", "Regular", "Regular FC")
    api.force_authenticate(regular)
    response = api.post("/api/admin/generate-fixtures/", {}, format="json")
    assert_standard_error(response, 403, "ADMIN_ONLY")
    assert response.json()["message"] == "Esta ação é exclusiva do administrador da liga."


@pytest.mark.django_db
@pytest.mark.parametrize("bad_score", [-1, 31, "abc", None])
def test_invalid_score(generated, players, api, bad_score):
    alice, bruno, _ = players
    match = match_between(generated, alice, bruno)
    api.force_authenticate(alice)
    response = api.post(
        f"/api/matches/{match.pk}/result/",
        {"home_goals": bad_score, "away_goals": 0},
        format="json",
    )
    assert_standard_error(response, 400, "INVALID_SCORE")


def test_429_handler():
    response = api_exception_handler(Throttled(wait=42), {})
    assert response.status_code == 429
    assert response.data["code"] == "TOO_MANY_REQUESTS"
    assert response.data["message"] == MESSAGES["TOO_MANY_REQUESTS"]
    assert response.data["retry_after_seconds"] == 42


def test_500_middleware_returns_friendly_json():
    request = RequestFactory().get("/api/qualquer-coisa/")

    def boom(_request):
        raise RuntimeError("unexpected failure")

    middleware = ApiErrorMiddleware(boom)
    response = middleware(request)
    assert response.status_code == 500
    body = json.loads(response.content)
    assert body == {"code": "SERVER_ERROR", "message": MESSAGES["SERVER_ERROR"]}
    assert "Traceback" not in response.content.decode()


@pytest.mark.django_db
def test_expired_access_cookie_is_translated(api, make_user, settings):
    user = make_user("expirado@teste.com", "Expirado", "Expirado FC")
    token = AccessToken.for_user(user)
    token.set_exp(lifetime=timedelta(seconds=-30))
    api.cookies[settings.AUTH_ACCESS_COOKIE] = str(token)
    response = api.get("/api/auth/me/")
    assert_standard_error(response, 401, "TOKEN_EXPIRED")
    assert response.json()["message"] == "Sua sessão expirou. Entre novamente para continuar."


@pytest.mark.django_db
def test_invalid_access_cookie_is_translated(api, settings):
    api.cookies[settings.AUTH_ACCESS_COOKIE] = "token-invalido"
    response = api.get("/api/auth/me/")
    assert_standard_error(response, 401, "INVALID_TOKEN")
