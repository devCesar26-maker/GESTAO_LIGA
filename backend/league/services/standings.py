"""Standings are always recomputed from finished matches, never incremented.

That makes corrections safe: change a score and the table is rebuilt from
scratch, so no stale points can linger.

Order (exactly): points, wins, goal difference. Then goals scored and finally the
team name, only to make the order deterministic. There is no head-to-head rule.
"""
from __future__ import annotations

from ..models import League, Match

COUNTED_STATUSES = (Match.Status.FINISHED, Match.Status.CONTESTED)


def _empty_row(participant) -> dict:
    return {
        "participant_id": participant.id,
        "user_id": participant.user_id,
        "player_name": participant.player_name,
        "team_name": participant.team_name,
        "team_key": (participant.team_name or "").strip().lower(),
        "played": 0,
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "goals_for": 0,
        "goals_against": 0,
        "goal_difference": 0,
        "points": 0,
    }


SORT_FIELDS = ("points", "wins", "goal_difference", "goals_for")


def sorting_key(row: dict) -> tuple:
    """Deterministic ranking key: higher points/wins/GD/GF first."""
    return (
        -row["points"],
        -row["wins"],
        -row["goal_difference"],
        -row["goals_for"],
        row["team_key"],
        row["player_name"].lower(),
    )


def compute_standings(league: League) -> list[dict]:
    participants = list(
        league.participants.select_related("user").order_by("id")
    )
    rows = {participant.id: _empty_row(participant) for participant in participants}

    matches = list(
        Match.objects.filter(
            league=league,
            status__in=COUNTED_STATUSES,
            home_goals__isnull=False,
            away_goals__isnull=False,
        ).select_related("home", "away")
    )

    for match in matches:
        home = rows.get(match.home_id)
        away = rows.get(match.away_id)
        if home is None or away is None:
            continue  # stale participant (should not happen)

        home_goals, away_goals = match.home_goals, match.away_goals

        home["played"] += 1
        away["played"] += 1
        home["goals_for"] += home_goals
        home["goals_against"] += away_goals
        away["goals_for"] += away_goals
        away["goals_against"] += home_goals

        if home_goals > away_goals:
            home["wins"] += 1
            away["losses"] += 1
            home["points"] += 3
        elif home_goals < away_goals:
            away["wins"] += 1
            home["losses"] += 1
            away["points"] += 3
        else:
            home["draws"] += 1
            away["draws"] += 1
            home["points"] += 1
            away["points"] += 1

    for row in rows.values():
        row["goal_difference"] = row["goals_for"] - row["goals_against"]

    final = sorted(rows.values(), key=sorting_key)

    for position, row in enumerate(final, start=1):
        row["position"] = position
        row.pop("team_key", None)  # internal sorting helper

    return final
