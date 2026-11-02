import pytest
from django.utils import timezone

from league.models import Match, Round
from league.services.standings import compute_standings

from .helpers import participant_for


def _finished_match(league, round_obj, home, away, home_goals, away_goals):
    return Match.objects.create(
        league=league,
        round=round_obj,
        home=home,
        away=away,
        home_goals=home_goals,
        away_goals=away_goals,
        status=Match.Status.FINISHED,
        result_reported_at=timezone.now(),
    )


@pytest.mark.django_db
def test_standings_basic_stats(league, players, api):
    alice, bruno, caio = players
    a, b, c = (participant_for(league, user) for user in (alice, bruno, caio))
    round_obj = Round.objects.create(league=league, number=1, leg=1)

    _finished_match(league, round_obj, a, b, 2, 0)
    _finished_match(league, round_obj, a, c, 1, 1)
    _finished_match(league, round_obj, b, c, 3, 1)

    table = api.get("/api/standings/").json()
    assert [row["team_name"] for row in table] == ["Time A", "Time B", "Time C"]

    row_a = table[0]
    assert row_a == {
        "position": 1,
        "user_id": alice.id,
        "participant_id": a.id,
        "player_name": "Alice",
        "team_name": "Time A",
        "played": 2,
        "wins": 1,
        "draws": 1,
        "losses": 0,
        "goals_for": 3,
        "goals_against": 1,
        "goal_difference": 2,
        "points": 4,
    }

    row_b = table[1]
    assert (row_b["played"], row_b["wins"], row_b["draws"], row_b["losses"]) == (2, 1, 0, 1)
    assert (row_b["goals_for"], row_b["goals_against"], row_b["goal_difference"]) == (3, 3, 0)
    assert row_b["points"] == 3

    row_c = table[2]
    assert (row_c["points"], row_c["draws"], row_c["losses"]) == (1, 1, 1)
    assert (row_c["goals_for"], row_c["goals_against"], row_c["goal_difference"]) == (2, 4, -2)


@pytest.mark.django_db
def test_goal_difference_tiebreak(league, players):
    alice, bruno, caio = players
    a, b, c = (participant_for(league, user) for user in (alice, bruno, caio))
    round_obj = Round.objects.create(league=league, number=1, leg=1)

    _finished_match(league, round_obj, a, c, 4, 0)
    _finished_match(league, round_obj, b, a, 2, 1)
    _finished_match(league, round_obj, c, b, 1, 0)

    table = compute_standings(league)
    assert [row["team_name"] for row in table] == ["Time A", "Time B", "Time C"]
    assert all(row["points"] == 3 for row in table)
    assert [row["goal_difference"] for row in table] == [3, 0, -3]


@pytest.mark.django_db
def test_goals_for_and_team_name_tiebreak(league, players):
    alice, bruno, caio = players
    a, b, c = (participant_for(league, user) for user in (alice, bruno, caio))
    round_obj = Round.objects.create(league=league, number=1, leg=1)

    _finished_match(league, round_obj, a, c, 4, 2)
    _finished_match(league, round_obj, b, a, 2, 0)
    _finished_match(league, round_obj, c, b, 2, 0)

    table = compute_standings(league)
    # A and C are identical on points/wins/GD/GF, so the team name decides.
    assert [row["team_name"] for row in table] == ["Time A", "Time C", "Time B"]
    assert [row["goals_for"] for row in table] == [4, 4, 2]
    assert [row["position"] for row in table] == [1, 2, 3]


@pytest.mark.django_db
def test_standings_without_matches_are_sorted_by_team_name(league, players):
    table = compute_standings(league)
    assert [row["team_name"] for row in table] == ["Time A", "Time B", "Time C"]
    assert all(row["points"] == 0 and row["played"] == 0 for row in table)


@pytest.mark.django_db
def test_contested_results_still_count(league, players):
    alice, bruno, _ = players
    a, b = participant_for(league, alice), participant_for(league, bruno)
    round_obj = Round.objects.create(league=league, number=1, leg=1)
    Match.objects.create(
        league=league,
        round=round_obj,
        home=a,
        away=b,
        home_goals=2,
        away_goals=1,
        status=Match.Status.CONTESTED,
        result_reported_at=timezone.now(),
        result_reported_by=alice,
    )

    table = compute_standings(league)
    row_a = next(row for row in table if row["participant_id"] == a.id)
    assert row_a["points"] == 3
    assert row_a["wins"] == 1
