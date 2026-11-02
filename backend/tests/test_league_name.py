import pytest

from core.messages import MESSAGES
from league.models import League, LeagueChangeLog, Match


@pytest.mark.django_db
def test_admin_renames_the_league_and_the_public_endpoint_reflects_it(league, api, admin):
    api.force_authenticate(admin)
    response = api.patch(
        "/api/admin/league/", {"name": "  Liga   dos  Craques "}, format="json"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "LEAGUE_UPDATED"
    assert body["league"]["name"] == "Liga dos Craques"

    league.refresh_from_db()
    assert league.name == "Liga dos Craques"

    public = api.get("/api/league/")
    assert public.status_code == 200
    assert public.json()["name"] == "Liga dos Craques"

    log = LeagueChangeLog.objects.get(league=league)
    assert log.action == LeagueChangeLog.Action.NAME_CHANGED
    assert log.previous == {"name": "Liga de Teste"}
    assert log.new == {"name": "Liga dos Craques"}
    assert log.user == admin


@pytest.mark.django_db
def test_non_admin_cannot_rename(league, api, make_user):
    regular = make_user("regular@teste.com", "Regular", "Regular FC")
    api.force_authenticate(regular)
    response = api.patch("/api/admin/league/", {"name": "Nome Novo"}, format="json")
    assert response.status_code == 403
    assert response.json()["code"] == "ADMIN_ONLY"
    league.refresh_from_db()
    assert league.name == "Liga de Teste"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "bad_name",
    ["", "   ", "ab", "x" * 61, "<script>alert(1)</script>", "Liga <b>Forte</b>"],
)
def test_invalid_names_are_rejected(league, api, admin, bad_name):
    api.force_authenticate(admin)
    response = api.patch("/api/admin/league/", {"name": bad_name}, format="json")
    assert response.status_code == 400
    assert response.json() == {
        "code": "INVALID_LEAGUE_NAME",
        "message": MESSAGES["INVALID_LEAGUE_NAME"],
    }
    league.refresh_from_db()
    assert league.name == "Liga de Teste"
    assert LeagueChangeLog.objects.count() == 0


@pytest.mark.django_db
def test_rename_is_a_no_op_when_the_name_did_not_change(league, api, admin):
    api.force_authenticate(admin)
    response = api.patch(
        "/api/admin/league/", {"name": "  Liga de Teste "}, format="json"
    )
    assert response.status_code == 200
    assert response.json()["code"] == "NOTHING_CHANGED"
    assert LeagueChangeLog.objects.count() == 0


@pytest.mark.django_db
def test_league_can_be_renamed_mid_season_without_touching_matches(league, players, api, admin):
    api.force_authenticate(admin)
    assert api.post("/api/admin/generate-fixtures/", {}, format="json").status_code == 200

    matches_before = Match.objects.filter(league=league).count()
    standings_before = api.get("/api/standings/").json()

    response = api.patch("/api/admin/league/", {"name": "Liga Renomeada"}, format="json")
    assert response.status_code == 200

    assert Match.objects.filter(league=league).count() == matches_before
    assert api.get("/api/standings/").json() == standings_before
    league.refresh_from_db()
    assert league.name == "Liga Renomeada"
    assert league.status == League.Status.IN_PROGRESS
