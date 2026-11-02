"""Single origin: Django serves the API under /api/ and the SPA everywhere else."""
from pathlib import Path

import pytest
from django.conf import settings


def _build_exists() -> bool:
    return (Path(settings.FRONTEND_BUILD_DIR) / "index.html").is_file()


@pytest.mark.django_db
def test_django_admin_lives_on_the_hardened_path(client):
    response = client.get("/django-admin/")
    assert response.status_code == 302
    assert "/django-admin/login/" in response["Location"]


@pytest.mark.django_db
@pytest.mark.skipif(not _build_exists(), reason="frontend build not present")
def test_react_routes_are_served_by_django(client):
    for path in ["/", "/rodadas", "/admin"]:
        response = client.get(path)
        assert response.status_code == 200, path
        assert b'<div id="root">' in response.content, path
        assert response["Cache-Control"] == "no-store"


@pytest.mark.django_db
def test_api_prefix_is_not_hijacked_by_the_spa(client):
    assert client.get("/api/health/").json() == {"status": "ok"}
