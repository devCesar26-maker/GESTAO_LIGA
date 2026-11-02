"""Rename the league and keep an audit trail of it.

The name is a display setting only: fixtures, results and standings never depend
on it, so it can be changed at any moment, even mid-season.
"""
from __future__ import annotations

from django.db import IntegrityError, transaction

from core.exceptions import AppError

from ..models import League, LeagueChangeLog


def update_league_name(league: League, user, new_name: str) -> tuple[League, bool]:
    """Return ``(league, changed)``; a no-op rename does not write a log row."""
    name = " ".join((new_name or "").split())
    if name == league.name:
        return league, False

    with transaction.atomic():
        locked = League.objects.select_for_update().get(pk=league.pk)
        previous = {"name": locked.name}
        locked.name = name
        try:
            locked.save(update_fields=["name", "updated_at"])
        except IntegrityError:
            raise AppError("LEAGUE_NAME_TAKEN", 400)
        LeagueChangeLog.objects.create(
            league=locked,
            user=user if getattr(user, "is_authenticated", False) else None,
            action=LeagueChangeLog.Action.NAME_CHANGED,
            previous=previous,
            new={"name": name},
        )
    return locked, True
