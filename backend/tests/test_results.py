from datetime import timedelta

import pytest
from django.utils import timezone

from league.models import Match, MatchResultLog

from .helpers import (
    losing_score_for,
    outsider_for,
    round_one_pair,
    winning_score_for,
)


@pytest.fixture
def generated(league, players, api, admin):
    api.force_authenticate(admin)
    response = api.post("/api/admin/generate-fixtures/", {}, format="json")
    assert response.status_code == 200
    return league


def report(api, user, match, home_goals, away_goals, **headers):
    api.force_authenticate(user)
    return api.post(
        f"/api/matches/{match.pk}/result/",
        {"home_goals": home_goals, "away_goals": away_goals},
        format="json",
        **headers,
    )


def contest(api, user, match, reason=""):
    api.force_authenticate(user)
    return api.post(
        f"/api/matches/{match.pk}/contest/", {"reason": reason}, format="json"
    )


@pytest.mark.django_db
def test_winner_reports_and_table_updates(generated, api):
    # Round 1 is always open; later rounds are gated by the sequential lock.
    home_user, away_user, match = round_one_pair(generated)
    home_goals, away_goals = winning_score_for(match, home_user)

    response = report(api, home_user, match, home_goals, away_goals)
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "RESULT_REPORTED"
    assert body["match"]["status"] == "FINISHED"

    match.refresh_from_db()
    assert match.contested_at is None
    assert match.result_reported_by == home_user
    assert match.logs.count() == 1
    assert match.logs.first().action == MatchResultLog.Action.RESULT_REPORTED

    table = api.get("/api/standings/").json()
    row = next(row for row in table if row["user_id"] == home_user.id)
    assert row["points"] == 3
    assert row["wins"] == 1
    assert row["goals_for"] == max(home_goals, away_goals)


@pytest.mark.django_db
def test_loser_cannot_report_a_win(generated, api):
    home_user, _, match = round_one_pair(generated)
    home_goals, away_goals = losing_score_for(match, home_user)

    response = report(api, home_user, match, home_goals, away_goals)
    assert response.status_code == 403
    body = response.json()
    assert body["code"] == "ONLY_WINNER_CAN_REPORT"
    assert "Quem registra o resultado é o vencedor" in body["message"]
    assert Match.objects.get(pk=match.pk).home_goals is None


@pytest.mark.django_db
def test_draw_can_be_reported_by_either_player(generated, api):
    home_user, _, match = round_one_pair(generated)
    response = report(api, home_user, match, 1, 1)
    assert response.status_code == 200
    match.refresh_from_db()
    assert (match.home_goals, match.away_goals) == (1, 1)
    assert match.status == Match.Status.FINISHED


@pytest.mark.django_db
def test_same_result_from_other_player_is_rejected(generated, api):
    home_user, away_user, match = round_one_pair(generated)
    score = winning_score_for(match, home_user)
    assert report(api, home_user, match, *score).status_code == 200

    other = report(api, away_user, match, *score)
    assert other.status_code == 409
    assert other.json()["code"] == "RESULT_ALREADY_REGISTERED"
    assert MatchResultLog.objects.filter(match=match).count() == 1


@pytest.mark.django_db
def test_admin_correction_recalculates_table(generated, api, admin):
    home_user, away_user, match = round_one_pair(generated)
    winning = winning_score_for(match, home_user)
    losing = losing_score_for(match, home_user)

    assert report(api, home_user, match, *winning).status_code == 200
    table = api.get("/api/standings/").json()
    assert next(r for r in table if r["user_id"] == home_user.id)["points"] == 3

    api.force_authenticate(admin)
    correction = api.patch(
        f"/api/matches/{match.pk}/result/",
        {"home_goals": losing[0], "away_goals": losing[1], "note": "Placar digitado errado"},
        format="json",
    )
    assert correction.status_code == 200
    assert correction.json()["code"] == "RESULT_CORRECTED"

    table = api.get("/api/standings/").json()
    home_row = next(r for r in table if r["user_id"] == home_user.id)
    away_row = next(r for r in table if r["user_id"] == away_user.id)
    assert home_row["points"] == 0
    assert away_row["points"] == 3
    assert home_row["goals_for"] == min(winning)

    match.refresh_from_db()
    assert match.logs.count() == 2
    corrected = match.logs.first()
    assert corrected.action == MatchResultLog.Action.RESULT_CORRECTED
    assert corrected.previous["home_goals"] == winning[0]

    # Applying the same correction again is a no-op.
    again = api.patch(
        f"/api/matches/{match.pk}/result/",
        {"home_goals": losing[0], "away_goals": losing[1]},
        format="json",
    )
    assert again.status_code == 200
    assert again.json()["code"] == "NOTHING_CHANGED"
    assert match.logs.count() == 2


@pytest.mark.django_db
def test_contest_flow(generated, api, admin):
    home_user, away_user, match = round_one_pair(generated)
    third = outsider_for(generated, match)
    assert third is not None

    assert report(api, home_user, match, *winning_score_for(match, home_user)).status_code == 200

    # The reporter cannot contest their own result.
    own = contest(api, home_user, match)
    assert own.status_code == 403
    assert own.json()["code"] == "CANNOT_CONTEST_OWN_RESULT"

    # A third player has no business here.
    third_response = contest(api, third, match)
    assert third_response.status_code == 403
    assert third_response.json()["code"] == "NOT_MATCH_PARTICIPANT"

    # The opponent can contest within the window.
    opponent = contest(api, away_user, match, "O placar foi outro")
    assert opponent.status_code == 200
    assert opponent.json()["code"] == "RESULT_CONTESTED"
    match.refresh_from_db()
    assert match.status == Match.Status.CONTESTED
    assert match.contested_by == away_user
    assert match.logs.filter(action=MatchResultLog.Action.RESULT_CONTESTED).count() == 1

    # Contested matches still count in the table.
    table = api.get("/api/standings/").json()
    assert next(r for r in table if r["user_id"] == home_user.id)["points"] == 3

    # Re-sending the contest is harmless.
    replay = contest(api, away_user, match)
    assert replay.status_code == 200
    assert replay.json()["code"] == "NOTHING_CHANGED"

    # Admin confirms the result and closes the review.
    api.force_authenticate(admin)
    confirm = api.post(f"/api/matches/{match.pk}/confirm/", {}, format="json")
    assert confirm.status_code == 200
    assert confirm.json()["code"] == "RESULT_CONFIRMED"
    match.refresh_from_db()
    assert match.status == Match.Status.FINISHED
    assert match.logs.filter(action=MatchResultLog.Action.RESULT_CONFIRMED).count() == 1

    # It cannot be contested again after review.
    again = contest(api, away_user, match)
    assert again.status_code == 409
    assert again.json()["code"] == "CONTEST_ALREADY_REVIEWED"


@pytest.mark.django_db
def test_contest_window_closed_after_48h(generated, api):
    home_user, away_user, match = round_one_pair(generated)
    assert report(api, home_user, match, *winning_score_for(match, home_user)).status_code == 200

    match.result_reported_at = timezone.now() - timedelta(hours=49)
    match.save(update_fields=["result_reported_at"])

    response = contest(api, away_user, match)
    assert response.status_code == 409
    assert response.json()["code"] == "CONTEST_WINDOW_CLOSED"
    assert "O prazo para contestar" in response.json()["message"]


@pytest.mark.django_db
def test_contest_requires_a_result(generated, api):
    _, away_user, match = round_one_pair(generated)
    response = contest(api, away_user, match)
    assert response.status_code == 409
    assert response.json()["code"] == "RESULT_NOT_REGISTERED"


@pytest.mark.django_db
def test_kickoff_update_rules(generated, api):
    home_user, _, match = round_one_pair(generated)

    api.force_authenticate(home_user)
    scheduled = api.patch(
        f"/api/matches/{match.pk}/kickoff/",
        {"kickoff_at": "2026-11-10T20:30:00-03:00"},
        format="json",
    )
    assert scheduled.status_code == 200
    assert scheduled.json()["code"] == "KICKOFF_UPDATED"
    match.refresh_from_db()
    assert match.kickoff_at is not None
    assert match.logs.filter(action=MatchResultLog.Action.KICKOFF_CHANGED).count() == 1

    # Same value is a no-op.
    same = api.patch(
        f"/api/matches/{match.pk}/kickoff/",
        {"kickoff_at": match.kickoff_at.isoformat()},
        format="json",
    )
    assert same.status_code == 200
    assert same.json()["code"] == "NOTHING_CHANGED"

    assert report(api, home_user, match, *winning_score_for(match, home_user)).status_code == 200

    finished = api.patch(
        f"/api/matches/{match.pk}/kickoff/",
        {"kickoff_at": "2026-12-01T20:30:00-03:00"},
        format="json",
    )
    assert finished.status_code == 409
    assert finished.json()["code"] == "MATCH_ALREADY_FINISHED"
    assert "já foi finalizada" in finished.json()["message"]

    invalid = api.patch(
        f"/api/matches/{match.pk}/kickoff/",
        {"kickoff_at": "not-a-date"},
        format="json",
    )
    assert invalid.status_code == 400
    assert invalid.json()["code"] == "INVALID_KICKOFF_DATE"


@pytest.mark.django_db
def test_invalid_kickoff_date_format(generated, api):
    home_user, _, match = round_one_pair(generated)
    api.force_authenticate(home_user)
    response = api.patch(
        f"/api/matches/{match.pk}/kickoff/",
        {"kickoff_at": "amanhã"},
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_KICKOFF_DATE"
