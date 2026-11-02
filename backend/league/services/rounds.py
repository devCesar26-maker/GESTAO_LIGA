"""Sequential round lock.

A result may only be registered for round N when round N-1 is closed, so a
table can never be built out of order. Round numbers are continuous across the
two legs, which means the first round of the return leg only opens after the
last round of the first leg is closed.

A round is closed when every match has a result (``FINISHED`` or ``CONTESTED``,
including a W.O.). A BYE creates no match at all, so an odd league closes its
rounds normally. The rule is evaluated inside the same transaction that writes
the result, which keeps two concurrent requests from slipping through.
"""
from __future__ import annotations

from django.db.models import Count, Q

from core.exceptions import AppError

from ..models import Match, Round

STATE_LOCKED = "locked"
STATE_OPEN = "open"
STATE_CLOSED = "closed"

STATE_LABELS = {
    STATE_LOCKED: "Bloqueada",
    STATE_OPEN: "Aberta",
    STATE_CLOSED: "Encerrada",
}

CLOSED_STATUSES = (Match.Status.FINISHED, Match.Status.CONTESTED)


def _closed_round_numbers(league) -> set[int]:
    """Numbers of the rounds whose matches all have a result, in one query."""
    rows = (
        Match.objects.filter(league=league)
        .values("round__number")
        .annotate(
            total=Count("id"),
            done=Count(
                "id",
                filter=Q(
                    status__in=CLOSED_STATUSES,
                    home_goals__isnull=False,
                    away_goals__isnull=False,
                ),
            ),
        )
    )
    return {row["round__number"] for row in rows if row["total"] and row["total"] == row["done"]}


def round_is_closed(round_obj: Round) -> bool:
    total = round_obj.matches.count()
    if not total:
        return False
    done = round_obj.matches.filter(
        status__in=CLOSED_STATUSES,
        home_goals__isnull=False,
        away_goals__isnull=False,
    ).count()
    return done == total


def previous_round_is_closed(league, number: int) -> bool:
    if number <= 1:
        return True
    previous = Round.objects.filter(league=league, number=number - 1).first()
    if previous is None:
        return True  # no previous round to wait for
    return round_is_closed(previous)


def round_states(league) -> dict[int, str]:
    """Map ``round number -> locked/open/closed`` for a whole league."""
    closed_numbers = _closed_round_numbers(league)
    numbers = list(
        league.rounds.order_by("number").values_list("number", flat=True)
    )
    states: dict[int, str] = {}
    previous_available = True
    for number in numbers:
        if number in closed_numbers:
            states[number] = STATE_CLOSED
            previous_available = True
        else:
            states[number] = STATE_OPEN if previous_available else STATE_LOCKED
            previous_available = False
    return states


def round_state(league, number: int) -> str:
    return round_states(league).get(number, STATE_OPEN)


def ensure_round_open(league, round_obj: Round | None) -> None:
    """Raise ``ROUND_NOT_OPEN`` when the previous round still has pending work.

    Must be called inside the transaction that writes the result.
    """
    if round_obj is None or round_obj.number <= 1:
        return
    if previous_round_is_closed(league, round_obj.number):
        return
    raise AppError("ROUND_NOT_OPEN", 409)


def is_round_locked(league, number: int) -> bool:
    return round_states(league).get(number) == STATE_LOCKED
