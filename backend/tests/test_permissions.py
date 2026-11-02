import pytest

from league.models import Match

from .helpers import (
    losing_score_for,
    outsider_for,
    round_one_pair,
    winning_score_for,
)

NOT_PARTICIPANT_MESSAGE = (
    "Você não pode alterar dados desse confronto, pois não está envolvido nele."
)


@pytest.fixture
def generated(league, players, api, admin):
    api.force_authenticate(admin)
    assert api.post("/api/admin/generate-fixtures/", {}, format="json").status_code == 200
    return league


@pytest.mark.django_db
def test_third_player_cannot_touch_match(generated, api):
    home_user, away_user, match = round_one_pair(generated)
    outsider = outsider_for(generated, match)
    assert outsider is not None

    api.force_authenticate(outsider)
    kickoff = api.patch(
        f"/api/matches/{match.pk}/kickoff/",
        {"kickoff_at": "2026-11-10T20:30:00-03:00"},
        format="json",
    )
    assert kickoff.status_code == 403
    assert kickoff.json() == {
        "code": "NOT_MATCH_PARTICIPANT",
        "message": NOT_PARTICIPANT_MESSAGE,
    }

    result = api.post(
        f"/api/matches/{match.pk}/result/",
        {"home_goals": 3, "away_goals": 0},
        format="json",
    )
    assert result.status_code == 403
    assert result.json()["code"] == "NOT_MATCH_PARTICIPANT"
    assert result.json()["message"] == NOT_PARTICIPANT_MESSAGE

    # Sending participant ids in the body does not help: identity comes from
    # the session cookie.
    forged = api.post(
        f"/api/matches/{match.pk}/result/",
        {
            "home_goals": 3,
            "away_goals": 0,
            "user_id": home_user.id,
            "reported_by": home_user.id,
        },
        format="json",
    )
    assert forged.status_code == 403
    assert Match.objects.get(pk=match.pk).home_goals is None

    # Once the match has a result, the outsider still cannot contest or edit it.
    api.force_authenticate(home_user)
    home_goals, away_goals = winning_score_for(match, home_user)
    assert api.post(
        f"/api/matches/{match.pk}/result/",
        {"home_goals": home_goals, "away_goals": away_goals},
        format="json",
    ).status_code == 200

    api.force_authenticate(outsider)
    contest = api.post(f"/api/matches/{match.pk}/contest/", {}, format="json")
    assert contest.status_code == 403
    assert contest.json()["code"] == "NOT_MATCH_PARTICIPANT"

    correction = api.patch(
        f"/api/matches/{match.pk}/result/",
        {"home_goals": 9, "away_goals": 9},
        format="json",
    )
    assert correction.status_code == 403
    assert correction.json()["code"] == "ADMIN_ONLY"


@pytest.mark.django_db
def test_participants_can_act_but_only_winner_reports(generated, api):
    home_user, away_user, match = round_one_pair(generated)

    api.force_authenticate(away_user)
    kickoff = api.patch(
        f"/api/matches/{match.pk}/kickoff/",
        {"kickoff_at": "2026-11-12T21:00:00-03:00"},
        format="json",
    )
    assert kickoff.status_code == 200

    # The declared loser is not allowed to report the win.
    api.force_authenticate(home_user)
    loser_score = losing_score_for(match, home_user)
    loser = api.post(
        f"/api/matches/{match.pk}/result/",
        {"home_goals": loser_score[0], "away_goals": loser_score[1]},
        format="json",
    )
    assert loser.status_code == 403
    assert loser.json()["code"] == "ONLY_WINNER_CAN_REPORT"

    api.force_authenticate(away_user)
    winner_score = winning_score_for(match, away_user)
    winner = api.post(
        f"/api/matches/{match.pk}/result/",
        {"home_goals": winner_score[0], "away_goals": winner_score[1]},
        format="json",
    )
    assert winner.status_code == 200

    # The opponent can contest.
    api.force_authenticate(home_user)
    contest = api.post(f"/api/matches/{match.pk}/contest/", {}, format="json")
    assert contest.status_code == 200


@pytest.mark.django_db
def test_anonymous_requests_get_401(generated, api):
    _, _, match = round_one_pair(generated)
    api.force_authenticate(user=None)

    for method, url in [
        ("post", f"/api/matches/{match.pk}/result/"),
        ("patch", f"/api/matches/{match.pk}/kickoff/"),
        ("post", f"/api/matches/{match.pk}/contest/"),
        ("post", "/api/admin/generate-fixtures/"),
    ]:
        response = getattr(api, method)(url, {}, format="json")
        assert response.status_code == 401
        assert response.json()["code"] == "NOT_AUTHENTICATED"
        assert response.json()["message"] == "Faça login para continuar."


@pytest.mark.django_db
def test_admin_can_correct_any_match_and_logs_it(generated, api, admin):
    _, _, match = round_one_pair(generated)

    api.force_authenticate(admin)
    response = api.patch(
        f"/api/matches/{match.pk}/result/",
        {"home_goals": 4, "away_goals": 2},
        format="json",
    )
    assert response.status_code == 200
    match.refresh_from_db()
    assert (match.home_goals, match.away_goals) == (4, 2)
    assert match.logs.first().user == admin

    logs = api.get(f"/api/matches/{match.pk}/logs/")
    assert logs.status_code == 200
    assert logs.json()[0]["action"] == "RESULT_CORRECTED"

    # Non-admins cannot see the audit trail.
    api.force_authenticate(match.home.user)
    assert api.get(f"/api/matches/{match.pk}/logs/").status_code == 403


@pytest.mark.django_db
def test_public_reads_work_without_login(generated, players, api):
    api.force_authenticate(user=None)
    for url in [
        "/api/league/",
        "/api/participants/",
        "/api/standings/",
        "/api/rounds/",
        "/api/matches/",
    ]:
        response = api.get(url)
        assert response.status_code == 200, url
