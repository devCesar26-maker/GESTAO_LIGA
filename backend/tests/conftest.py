import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from accounts.models import User
from league.models import League, Participant


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    """Keep anonymous throttle counters from leaking between tests."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def fast_password_hasher(settings):
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture(autouse=True)
def production_security_posture(settings):
    """Run the suite on the production security configuration.

    pytest-django flips DEBUG to False after the settings module is imported, so
    the values that are derived from DEBUG at import time are re-applied here.
    """
    settings.DEBUG = False
    # The test client speaks plain http; the redirect itself is covered by the
    # deployment settings, not by the request cycle.
    settings.SECURE_SSL_REDIRECT = False
    settings.SESSION_COOKIE_SECURE = True
    settings.CSRF_COOKIE_SECURE = True
    settings.SECURE_HSTS_SECONDS = 31536000
    settings.SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    settings.SECURE_HSTS_PRELOAD = True


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def league(db):
    # The data migration creates a default league; tests must own the active one.
    League.objects.all().delete()
    return League.objects.create(
        name="Liga de Teste", status=League.Status.REGISTRATION, is_active=True
    )


@pytest.fixture
def make_user(db):
    def factory(
        email,
        name="Jogador",
        team="Time",
        staff=False,
        password="senha12345",
    ):
        return User.objects.create_user(
            email=email,
            password=password,
            name=name,
            team_name=team,
            is_staff=staff,
        )

    return factory


@pytest.fixture
def admin(make_user):
    return make_user("admin@teste.com", "Administrador", "Comissão", staff=True)


@pytest.fixture
def enroll(league):
    def factory(users):
        return [
            Participant.objects.get_or_create(league=league, user=user)[0] for user in users
        ]

    return factory


@pytest.fixture
def players(league, make_user, enroll):
    """A, B and C enrolled in the league (odd count exercises the BYE)."""
    alice = make_user("alice@teste.com", "Alice", "Time A")
    bruno = make_user("bruno@teste.com", "Bruno", "Time B")
    caio = make_user("caio@teste.com", "Caio", "Time C")
    enroll([alice, bruno, caio])
    return alice, bruno, caio


@pytest.fixture
def generate_api(api, admin):
    def factory():
        api.force_authenticate(admin)
        return api.post("/api/admin/generate-fixtures/", {}, format="json")

    return factory
