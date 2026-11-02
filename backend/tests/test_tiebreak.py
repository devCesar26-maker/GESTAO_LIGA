"""Tiebreak order: points, wins, goal difference, goals for, team name.

There is no head-to-head rule anymore.
"""
import pytest
from django.utils import timezone

from league.models import Match, Round
from league.services.standings import compute_standings

from .helpers import participant_for


def _match(league, round_obj, home, away, home_goals, away_goals):
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
def test_equal_points_are_decided_by_wins(league, players, make_user, enroll):
    alice, bruno, caio = players
    diego = make_user("diego@teste.com", "Diego", "Time D")
    enroll([diego])

    a, b, c, d = (participant_for(league, user) for user in (alice, bruno, caio, diego))
    round_obj = Round.objects.create(league=league, number=1, leg=1)

    # A: one win and one heavy loss -> 3 points, 1 win, negative GD.
    _match(league, round_obj, a, d, 1, 0)
    _match(league, round_obj, a, c, 0, 4)
    # B: three draws -> 3 points, 0 wins, GD 0.
    _match(league, round_obj, b, c, 2, 2)
    _match(league, round_obj, c, b, 2, 2)
    _match(league, round_obj, b, d, 3, 3)

    table = compute_standings(league)
    rows = {row["team_name"]: row for row in table}

    assert rows["Time A"]["points"] == rows["Time B"]["points"] == 3
    assert rows["Time A"]["wins"] == 1
    assert rows["Time B"]["wins"] == 0
    assert rows["Time B"]["goal_difference"] > rows["Time A"]["goal_difference"]
    # More wins wins, even with a worse goal difference.
    assert table.index(rows["Time A"]) < table.index(rows["Time B"])


@pytest.mark.django_db
def test_equal_wins_are_decided_by_goal_difference(league, players):
    alice, bruno, caio = players
    a, b, c = (participant_for(league, user) for user in (alice, bruno, caio))
    round_obj = Round.objects.create(league=league, number=1, leg=1)

    _match(league, round_obj, a, c, 5, 0)
    _match(league, round_obj, b, c, 2, 1)

    table = compute_standings(league)
    assert [row["team_name"] for row in table] == ["Time A", "Time B", "Time C"]
    assert all(row["points"] == 3 for row in table[:2])
    assert all(row["wins"] == 1 for row in table[:2])
    assert table[0]["goal_difference"] > table[1]["goal_difference"]


@pytest.mark.django_db
def test_head_to_head_is_not_used(league, players, make_user, enroll):
    """The team that won the direct clash can still rank below on goal difference."""
    alice, bruno, caio = players
    diego = make_user("diego@teste.com", "Diego", "Time D")
    enroll([diego])

    a, b, c, d = (participant_for(league, user) for user in (alice, bruno, caio, diego))
    round_obj = Round.objects.create(league=league, number=1, leg=1)

    _match(league, round_obj, a, c, 1, 0)  # A beats C head-to-head
    _match(league, round_obj, a, d, 0, 2)  # A loses to D
    _match(league, round_obj, c, d, 5, 0)  # C ends with the best goal difference

    table = compute_standings(league)
    # Time B (enrolled by the fixture) played nothing, so it comes last.
    assert [row["team_name"] for row in table] == ["Time C", "Time A", "Time D", "Time B"]
    assert [row["points"] for row in table[:3]] == [3, 3, 3]
    assert [row["wins"] for row in table[:3]] == [1, 1, 1]


@pytest.mark.django_db
def test_three_teams_tied_are_ordered_predictably(league, players):
    alice, bruno, caio = players
    a, b, c = (participant_for(league, user) for user in (alice, bruno, caio))
    round_obj = Round.objects.create(league=league, number=1, leg=1)

    _match(league, round_obj, a, c, 4, 0)
    _match(league, round_obj, b, a, 2, 1)
    _match(league, round_obj, c, b, 1, 0)

    table = compute_standings(league)
    assert [row["team_name"] for row in table] == ["Time A", "Time B", "Time C"]
    assert all(row["points"] == 3 for row in table)
    assert all(row["wins"] == 1 for row in table)
    assert [row["goal_difference"] for row in table] == [3, 0, -3]
    assert [row["position"] for row in table] == [1, 2, 3]


@pytest.mark.django_db
def test_fully_tied_rows_fall_back_to_the_team_name(league, players, make_user, enroll):
    alice, bruno, caio = players
    diego = make_user("diego@teste.com", "Diego", "Time D")
    enroll([diego])

    a, b, c, d = (participant_for(league, user) for user in (alice, bruno, caio, diego))
    round_obj = Round.objects.create(league=league, number=1, leg=1)

    _match(league, round_obj, a, d, 2, 0)
    _match(league, round_obj, c, d, 2, 0)
    _match(league, round_obj, a, c, 1, 1)

    table = compute_standings(league)
    rows = {row["team_name"]: row for row in table}
    # A and C share points, wins, goal difference and goals scored.
    for field in ("points", "wins", "goal_difference", "goals_for"):
        assert rows["Time A"][field] == rows["Time C"][field]
    assert [row["team_name"] for row in table] == ["Time A", "Time C", "Time B", "Time D"]
