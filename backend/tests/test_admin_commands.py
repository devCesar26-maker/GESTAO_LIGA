"""Tests for the production admin-promotion commands and the demo guard."""
import io

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from accounts.models import User


@pytest.mark.django_db
def test_set_admin_promotes_an_existing_account(make_user):
    user = make_user("admin@teste.com", "Admin", "Time A")
    assert user.is_staff is False

    call_command("set_admin", "ADMIN@teste.com")

    user.refresh_from_db()
    assert user.is_staff is True
    assert user.is_superuser is False


@pytest.mark.django_db
def test_set_admin_can_grant_and_revoke_everything(make_user):
    user = make_user("admin@teste.com", "Admin", "Time A")

    call_command("set_admin", user.email, "--superuser")
    user.refresh_from_db()
    assert user.is_staff is True
    assert user.is_superuser is True

    call_command("set_admin", user.email, "--revoke")
    user.refresh_from_db()
    assert user.is_staff is False
    assert user.is_superuser is False


@pytest.mark.django_db
def test_set_admin_refuses_unknown_account():
    with pytest.raises(CommandError, match="Nenhuma conta"):
        call_command("set_admin", "ninguem@teste.com")


@pytest.mark.django_db
def test_sync_admins_promotes_only_existing_accounts(make_user, monkeypatch):
    existing = make_user("admin@teste.com", "Admin", "Time A")
    monkeypatch.setenv("ADMIN_EMAILS", "admin@teste.com, ausente@teste.com")

    stderr = io.StringIO()
    call_command("sync_admins", stderr=stderr)

    existing.refresh_from_db()
    assert existing.is_staff is True
    assert "ausente@teste.com" in stderr.getvalue()
    assert User.objects.filter(email="ausente@teste.com").exists() is False


@pytest.mark.django_db
def test_sync_admins_is_a_noop_without_env(make_user, monkeypatch):
    user = make_user("admin@teste.com", "Admin", "Time A")
    monkeypatch.delenv("ADMIN_EMAILS", raising=False)

    call_command("sync_admins")

    user.refresh_from_db()
    assert user.is_staff is False


@pytest.mark.django_db
def test_seed_demo_is_blocked_when_debug_is_false(settings):
    settings.DEBUG = False
    with pytest.raises(CommandError, match="DEBUG=False"):
        call_command("seed_demo")
