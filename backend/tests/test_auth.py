import pytest
from django.conf import settings
from django.utils import timezone

from accounts.models import User
from league.models import League, Participant


def register_payload(**overrides):
    payload = {
        "email": "novo@teste.com",
        "password": "SenhaForte123",
        "name": "Novo Jogador",
        "team_name": "Novo FC",
    }
    payload.update(overrides)
    return payload


def do_login(api, email, password):
    return api.post(
        "/api/auth/login/", {"email": email, "password": password}, format="json"
    )


@pytest.mark.django_db
def test_register_creates_account_participant_and_session_cookies(league, api):
    response = api.post("/api/auth/register/", register_payload(), format="json")
    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "novo@teste.com"
    assert body["user"]["team_name"] == "Novo FC"
    assert body["message"] == "Cadastro realizado com sucesso!"
    # Tokens never travel in the body.
    assert "access" not in body
    assert "refresh" not in body
    assert response.cookies[settings.AUTH_ACCESS_COOKIE].value
    assert response.cookies[settings.AUTH_REFRESH_COOKIE].value

    user = User.objects.get(email="novo@teste.com")
    assert user.check_password("SenhaForte123")
    assert Participant.objects.filter(league=league, user=user).exists()

    # The cookies are enough to use the API.
    assert api.get("/api/auth/me/").json()["email"] == "novo@teste.com"


@pytest.mark.django_db
def test_register_rejects_duplicate_email_case_insensitive(league, api):
    first = api.post("/api/auth/register/", register_payload(), format="json")
    assert first.status_code == 201

    duplicate = api.post(
        "/api/auth/register/",
        register_payload(email="NOVO@teste.com"),
        format="json",
    )
    assert duplicate.status_code == 400
    assert duplicate.json() == {
        "code": "EMAIL_TAKEN",
        "message": "Este email já está cadastrado. Tente entrar ou recuperar sua senha.",
    }


@pytest.mark.django_db
def test_register_rejects_weak_password(league, api):
    response = api.post(
        "/api/auth/register/", register_payload(password="123"), format="json"
    )
    assert response.status_code == 400
    assert response.json()["code"] == "WEAK_PASSWORD"
    assert not User.objects.filter(email="novo@teste.com").exists()


@pytest.mark.django_db
def test_registration_closed_after_fixtures(league, api):
    league.status = League.Status.IN_PROGRESS
    league.fixtures_generated_at = timezone.now()
    league.save(update_fields=["status", "fixtures_generated_at"])

    response = api.post("/api/auth/register/", register_payload(), format="json")
    assert response.status_code == 403
    assert response.json() == {
        "code": "REGISTRATION_CLOSED",
        "message": (
            "As inscrições estão encerradas, pois os confrontos já foram gerados. "
            "Fale com o administrador para entrar na liga."
        ),
    }
    assert not User.objects.filter(email="novo@teste.com").exists()


@pytest.mark.django_db
def test_login_and_authenticated_profile(league, make_user, api):
    user = make_user("jogador@teste.com", "Jogador", "Time J", password="SenhaForte123")

    wrong = do_login(api, "jogador@teste.com", "errada")
    assert wrong.status_code == 401
    assert wrong.json() == {
        "code": "INVALID_CREDENTIALS",
        "message": "Email ou senha incorretos.",
    }

    login = do_login(api, "JOGADOR@teste.com", "SenhaForte123")
    assert login.status_code == 200
    assert "access" not in login.json()
    assert "refresh" not in login.json()

    me = api.get("/api/auth/me/")
    assert me.status_code == 200
    assert me.json()["team_name"] == "Time J"

    updated = api.patch(
        "/api/auth/me/",
        {"team_name": "Time Renomeado", "name": "Novo Nome"},
        format="json",
    )
    assert updated.status_code == 200
    assert updated.json()["user"]["team_name"] == "Time Renomeado"
    user.refresh_from_db()
    assert user.team_name == "Time Renomeado"

    logout = api.post("/api/auth/logout/", {}, format="json")
    assert logout.status_code == 200
    assert logout.json()["code"] == "LOGGED_OUT"
    assert api.get("/api/auth/me/").status_code == 401


@pytest.mark.django_db
def test_refresh_rotates_the_cookie(league, make_user, api):
    make_user("refresh@teste.com", "Refresh", "Refresh FC", password="SenhaForte123")
    assert do_login(api, "refresh@teste.com", "SenhaForte123").status_code == 200

    response = api.post("/api/auth/refresh/", {}, format="json")
    assert response.status_code == 200
    assert "access" not in response.json()
    assert response.cookies[settings.AUTH_ACCESS_COOKIE].value

    # The body is ignored: the refresh token only comes from the cookie.
    api.cookies.pop(settings.AUTH_REFRESH_COOKIE, None)
    invalid = api.post(
        "/api/auth/refresh/", {"refresh": "not-a-token"}, format="json"
    )
    assert invalid.status_code == 401
    assert invalid.json()["code"] == "SESSION_EXPIRED"


@pytest.mark.django_db
def test_anonymous_me_requires_login(api):
    response = api.get("/api/auth/me/")
    assert response.status_code == 401
    assert response.json()["code"] == "NOT_AUTHENTICATED"


@pytest.mark.django_db
def test_profile_validates_blank_fields(make_user, api):
    user = make_user("blank@teste.com", "Blank", "Blank FC")
    api.force_authenticate(user)
    response = api.patch("/api/auth/me/", {"team_name": ""}, format="json")
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_DATA"
