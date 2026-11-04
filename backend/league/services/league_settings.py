"""League settings that can be changed mid-season.

``single_round_mode`` only changes which rounds are open; the round states are
always derived from the current matches, so toggling it never deletes or
invalidates a result. The change is audited in ``LeagueChangeLog`` exactly like
the custom league name.
"""
from __future__ import annotations

from django.db import transaction

from ..models import League, LeagueChangeLog


def update_single_round_mode(league: League, user, value: bool) -> tuple[League, bool]:
    """Return ``(league, changed)``; setting the same value writes no log row."""
    value = bool(value)

    with transaction.atomic():
        locked = League.objects.select_for_update().get(pk=league.pk)
        if locked.single_round_mode == value:
            return locked, False

        previous = {"single_round_mode": locked.single_round_mode}
        locked.single_round_mode = value
        locked.save(update_fields=["single_round_mode", "updated_at"])
        LeagueChangeLog.objects.create(
            league=locked,
            user=user if getattr(user, "is_authenticated", False) else None,
            action=LeagueChangeLog.Action.SINGLE_ROUND_MODE_CHANGED,
            previous=previous,
            new={"single_round_mode": value},
        )
    return locked, True
