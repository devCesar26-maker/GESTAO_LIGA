"""Sequential round lock, generalized to fixed blocks of one or two rounds.

A result may only be registered for a round whose previous *blocks* are fully
closed, so a table can never be built out of order. With the league setting
``single_round_mode`` enabled (the default) each block is one round, preserving
the original rule: round N only opens after round N-1 is closed. When it is
disabled, rounds are grouped in fixed pairs by number -- (1, 2), (3, 4), (5, 6)
-- and both rounds of a pair open and are blocked together.

Round numbers are continuous across the two legs, so a pair may straddle the
turnaround (with 11 players, the pair (11, 12) is the last round of the first
leg plus the first of the return leg). If the league somehow has an odd number
of rounds, the last round is alone in its block.

A round is closed when every match has a result (``FINISHED`` or ``CONTESTED``,
including a W.O.). A BYE creates no match at all, so an odd league closes its
rounds normally. The rule is evaluated inside the same transaction that writes
the result, with the league row locked, which keeps two concurrent requests
from slipping through even if the setting is changed mid-flight.
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


def block_size(league) -> int:
    """How many rounds open together: 1 in single mode, 2 otherwise."""
    return 1 if getattr(league, "single_round_mode", True) else 2


def block_number(number: int, size: int = 2) -> int:
    """Block of a round: ``ceil(number / size)`` (1-based)."""
    return (int(number) - 1) // size + 1


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


def previous_blocks_are_closed(
    league, number: int, closed_numbers: set[int] | None = None
) -> bool:
    """True when every existing round in an earlier block is closed."""
    if closed_numbers is None:
        closed_numbers = _closed_round_numbers(league)
    size = block_size(league)
    current_block = block_number(number, size)
    earlier_numbers = [
        candidate
        for candidate in league.rounds.values_list("number", flat=True)
        if block_number(candidate, size) < current_block
    ]
    return all(candidate in closed_numbers for candidate in earlier_numbers)


def previous_round_is_closed(league, number: int) -> bool:
    """Backward-compatible helper: check the immediately previous block."""
    return previous_blocks_are_closed(league, number)


def round_states(league) -> dict[int, str]:
    """Map ``round number -> locked/open/closed`` for a whole league.

    States are always derived from the current matches and the current setting;
    nothing is stored. Changing the setting therefore recalculates every state
    safely, without touching results already registered.
    """
    closed_numbers = _closed_round_numbers(league)
    size = block_size(league)
    numbers = list(
        league.rounds.order_by("number").values_list("number", flat=True)
    )
    states: dict[int, str] = {}
    for number in numbers:
        if number in closed_numbers:
            states[number] = STATE_CLOSED
            continue
        current_block = block_number(number, size)
        earlier = [
            candidate
            for candidate in numbers
            if block_number(candidate, size) < current_block
        ]
        states[number] = (
            STATE_OPEN
            if all(candidate in closed_numbers for candidate in earlier)
            else STATE_LOCKED
        )
    return states


def round_state(league, number: int) -> str:
    return round_states(league).get(number, STATE_OPEN)


def ensure_round_open(league, round_obj: Round | None) -> None:
    """Raise ``ROUND_NOT_OPEN`` when the round's earlier blocks still have work.

    Must be called inside the transaction that writes the result, after the
    league row is locked, so the setting read here is the one in force at write
    time.
    """
    if round_obj is None:
        return
    if round_state(league, round_obj.number) != STATE_LOCKED:
        return
    raise AppError("ROUND_NOT_OPEN", 409)


def is_round_locked(league, number: int) -> bool:
    return round_states(league).get(number) == STATE_LOCKED
