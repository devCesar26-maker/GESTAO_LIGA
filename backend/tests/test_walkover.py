import pytest

from league.models import Match, MatchResultLog, Round

from .helpers import round_one_pair


@pytest.fixture
def generated(league, players, api, admin):
    api.force_authenticate(admin)
    assert api.post("/api/admin/generate-fixtures/", {}, format="json").status_code == 200
    return league


def walkover(api, user, match, absent_side):
    api.force_authenticate(user)
    return api.post(
        f"/api/matches/{match.pk}/walkover/",
        {"absent_side": absent_side},
        format="json",
    )


@pytest.mark.django_db
def test_only_the_admin_can_register_a_walkover(generated, api):
    home_user, _, match = round_one_pair(generated)

    response = walkover(api, home_user, match, "away")
    assert response.status_code == 403
    assert response.json()["code"] == "ADMIN_ONLY"

    match.refresh_from_db()
    assert match.home_goals is None
    assert match.is_walkover is False


@pytest.mark.django_db
def test_walkover_awards_three_to_zero_to_the_player_who_showed_up(generated, api, admin):
    _, _, match = round_one_pair(generated)

    response = walkover(api, admin, match, "away")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "WALKOVER_REGISTERED"
    assert body["match"]["is_walkover"] is True
    assert body["match"]["home_goals"] == 3
    assert body["match"]["away_goals"] == 0
    assert body["match"]["status"] == "FINISHED"

    match.refresh_from_db()
    assert match.is_walkover is True
    assert match.status == Match.Status.FINISHED
    assert (match.home_goals, match.away_goals) == (3, 0)

    log = match.logs.get(action=MatchResultLog.Action.RESULT_WALKOVER)
    assert log.user == admin
    assert "W.O." in log.note


@pytest.mark.django_db
def test_walkover_for_the_away_side_is_mirrored(generated, api, admin):
    _, _, match = round_one_pair(generated)

    response = walkover(api, admin, match, "home")
    assert response.status_code == 200
    assert response.json()["match"]["home_goals"] == 0
    assert response.json()["match"]["away_goals"] == 3


@pytest.mark.django_db
def test_walkover_counts_in_the_standings(generated, api, admin):
    _, _, match = round_one_pair(generated)
    home_team = match.home.team_name
    away_team = match.away.team_name

    assert walkover(api, admin, match, "away").status_code == 200

    table = api.get("/api/standings/").json()
    home_row = next(row for row in table if row["team_name"] == home_team)
    away_row = next(row for row in table if row["team_name"] == away_team)
    assert home_row["points"] == 3
    assert home_row["wins"] == 1
    assert home_row["goals_for"] == 3
    assert away_row["points"] == 0
    assert away_row["goals_against"] == 3


@pytest.mark.django_db
def test_walkover_closes_the_round(generated, api, admin):
    """A W.O. is what unblocks a league stuck on an absent player."""
    _, _, match = round_one_pair(generated)
    assert walkover(api, admin, match, "away").status_code == 200

    rounds = api.get("/api/rounds/").json()
    assert rounds[0]["state"] == "closed"
    assert rounds[1]["state"] == "open"


@pytest.mark.django_db
def test_walkover_requires_a_pending_match(generated, api, admin):
    _, _, match = round_one_pair(generated)
    assert walkover(api, admin, match, "away").status_code == 200

    again = walkover(api, admin, match, "away")
    assert again.status_code == 409
    assert again.json()["code"] == "RESULT_ALREADY_REGISTERED"


@pytest.mark.django_db
def test_walkover_validates_the_absent_side(generated, api, admin):
    _, _, match = round_one_pair(generated)

    response = walkover(api, admin, match, "both")
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_ABSENT_SIDE"


@pytest.mark.django_db
def test_walkover_respects_the_round_lock(league, api, admin, make_user, enroll):
    users = [
        make_user(f"lock{i}@teste.com", f"Jogador {i}", f"Time {i}") for i in range(1, 5)
    ]
    enroll(users)
    api.force_authenticate(admin)
    assert api.post("/api/admin/generate-fixtures/", {}, format="json").status_code == 200

    match = Round.objects.get(league=league, number=2).matches.first()
    response = walkover(api, admin, match, "away")
    assert response.status_code == 409
    assert response.json()["code"] == "ROUND_NOT_OPEN"
