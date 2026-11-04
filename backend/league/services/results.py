"""Result registration, correction, contestation and admin walkovers.

All writes lock the league row (round lock) and the match row, check the
caller's relationship with the match (never trusting an id from the body) and
append to ``MatchResultLog``.
"""
from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.exceptions import AppError

from ..models import League, Match, MatchResultLog
from .rounds import ensure_round_open


def _get_locked_match(match_id: int) -> Match:
    match = (
        Match.objects.select_for_update(of=("self",))
        .select_related("home__user", "away__user", "round", "result_reported_by", "contested_by")
        .filter(pk=match_id)
        .first()
    )
    if match is None:
        raise AppError("NOT_FOUND", 404)
    return match


def _lock_league(league_id: int) -> League:
    """Serialize round-lock checks and settings changes between writers.

    Returning the locked row lets the caller evaluate ``single_round_mode`` as
    it is stored at write time, inside the same transaction.
    """
    return League.objects.select_for_update().get(pk=league_id)


def _validate_score(value) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise AppError("INVALID_SCORE", 400)
    if value < 0 or value > settings.MAX_GOALS_PER_MATCH:
        raise AppError("INVALID_SCORE", 400)
    return value


def _log(match: Match, user, action: str, previous=None, new=None, note: str = "") -> None:
    MatchResultLog.objects.create(
        match=match,
        user=user if getattr(user, "is_authenticated", False) else None,
        action=action,
        previous=previous or {},
        new=new or {},
        note=note,
    )


def _state(match: Match) -> dict:
    return {
        "status": match.status,
        "home_goals": match.home_goals,
        "away_goals": match.away_goals,
        "is_walkover": match.is_walkover,
        "kickoff_at": match.kickoff_at.isoformat() if match.kickoff_at else None,
        "reported_by_id": match.result_reported_by_id,
    }


def permissions_for(match: Match, user, *, round_locked: bool = False) -> dict:
    """Capabilities used by the UI. The backend re-checks every one of them."""
    permissions = {
        "is_participant": False,
        "can_set_kickoff": False,
        "can_report": False,
        "can_report_walkover": False,
        "can_contest": False,
        "can_correct": False,
        "can_confirm": False,
        "round_locked": round_locked,
    }
    if user is None or not getattr(user, "is_authenticated", False):
        return permissions

    is_admin = bool(user.is_staff)
    is_participant = match.involves(user)
    permissions["is_participant"] = is_participant

    can_act = is_admin or is_participant
    # Changing the date stays allowed on a locked round: the lock only gates
    # the result, because a delayed game is exactly why the round is behind.
    permissions["can_set_kickoff"] = (
        can_act and not match.has_result and match.status == Match.Status.SCHEDULED
    )
    permissions["can_report"] = can_act and not match.has_result and not round_locked
    permissions["can_report_walkover"] = (
        is_admin and not match.has_result and not round_locked
    )
    permissions["can_correct"] = is_admin and match.has_result
    permissions["can_confirm"] = is_admin and match.status == Match.Status.CONTESTED

    deadline = match.contest_deadline
    permissions["can_contest"] = bool(
        can_act
        and match.has_result
        and match.status == Match.Status.FINISHED
        and match.contested_at is None
        and match.result_reported_by_id != user.id
        and deadline is not None
        and timezone.now() <= deadline
    )
    return permissions


def report_result(match: Match, user, home_goals, away_goals) -> tuple[Match, bool]:
    """Register a result. Returns ``(match, changed)``.

    Rules:
    * only the two players of the match (or an admin) may report;
    * the previous round must be closed (sequential round lock);
    * the reporter must be on the winning side (any side can report a draw);
    * sending the exact same result again is a no-op (idempotent).
    """
    home_goals = _validate_score(home_goals)
    away_goals = _validate_score(away_goals)

    with transaction.atomic():
        league = _lock_league(match.league_id)
        locked = _get_locked_match(match.pk)
        is_admin = bool(user.is_staff)

        if not is_admin and not locked.involves(user):
            raise AppError("NOT_MATCH_PARTICIPANT", 403)

        if locked.has_result:
            same_score = (
                locked.home_goals == home_goals and locked.away_goals == away_goals
            )
            if same_score and (locked.result_reported_by_id == user.id or is_admin):
                return locked, False  # idempotent replay: nothing changes
            raise AppError("RESULT_ALREADY_REGISTERED", 409)

        # Enforced inside the same transaction that writes the result.
        ensure_round_open(league, locked.round)

        if not is_admin:
            user_is_home = locked.home.user_id == user.id
            user_is_away = locked.away.user_id == user.id
            if not (user_is_home or user_is_away):
                raise AppError("NOT_MATCH_PARTICIPANT", 403)
            if home_goals != away_goals:
                user_won = (home_goals > away_goals and user_is_home) or (
                    away_goals > home_goals and user_is_away
                )
                if not user_won:
                    raise AppError("ONLY_WINNER_CAN_REPORT", 403)

        previous = _state(locked)
        locked.home_goals = home_goals
        locked.away_goals = away_goals
        locked.is_walkover = False
        locked.status = Match.Status.FINISHED
        locked.result_reported_by = user
        locked.result_reported_at = timezone.now()
        locked.contested_by = None
        locked.contested_at = None
        locked.contest_reason = ""
        locked.save(
            update_fields=[
                "home_goals",
                "away_goals",
                "is_walkover",
                "status",
                "result_reported_by",
                "result_reported_at",
                "contested_by",
                "contested_at",
                "contest_reason",
                "updated_at",
            ]
        )
        _log(
            locked,
            user,
            MatchResultLog.Action.RESULT_REPORTED,
            previous,
            _state(locked),
        )
        return locked, True


def register_walkover(match: Match, admin_user, absent_side: str) -> tuple[Match, bool]:
    """Admin awards a 3x0 to the player who showed up.

    This is how a missing player stops holding the whole league: the result is
    registered like any other, so the round closes and the next one opens. A
    common result still honors the sequential lock; the admin cannot skip it.
    """
    if not getattr(admin_user, "is_staff", False):
        raise AppError("ADMIN_ONLY", 403)

    side = str(absent_side or "").strip().lower()
    if side not in {"home", "away"}:
        raise AppError("INVALID_ABSENT_SIDE", 400)

    goals = min(settings.WALKOVER_GOALS, settings.MAX_GOALS_PER_MATCH)

    with transaction.atomic():
        league = _lock_league(match.league_id)
        locked = _get_locked_match(match.pk)

        if locked.has_result:
            raise AppError("RESULT_ALREADY_REGISTERED", 409)

        ensure_round_open(league, locked.round)

        home_goals, away_goals = (0, goals) if side == "home" else (goals, 0)
        previous = _state(locked)
        locked.home_goals = home_goals
        locked.away_goals = away_goals
        locked.is_walkover = True
        locked.status = Match.Status.FINISHED
        locked.result_reported_by = admin_user
        locked.result_reported_at = timezone.now()
        locked.contested_by = None
        locked.contested_at = None
        locked.contest_reason = ""
        locked.save(
            update_fields=[
                "home_goals",
                "away_goals",
                "is_walkover",
                "status",
                "result_reported_by",
                "result_reported_at",
                "contested_by",
                "contested_at",
                "contest_reason",
                "updated_at",
            ]
        )
        absent_team = locked.home.team_name if side == "home" else locked.away.team_name
        _log(
            locked,
            admin_user,
            MatchResultLog.Action.RESULT_WALKOVER,
            previous,
            _state(locked),
            note=f"W.O. registrado: {absent_team} não compareceu.",
        )
        return locked, True


def correct_result(match: Match, admin_user, home_goals, away_goals, note: str = "") -> tuple[Match, bool]:
    """Admin correction. Recomputes standings implicitly (they are derived).

    Corrections never re-open nor block later rounds: the round lock only gates
    new results, and the standings are always recalculated from the matches.
    """
    if not getattr(admin_user, "is_staff", False):
        raise AppError("ADMIN_ONLY", 403)

    home_goals = _validate_score(home_goals)
    away_goals = _validate_score(away_goals)

    with transaction.atomic():
        locked = _get_locked_match(match.pk)

        if (
            locked.has_result
            and locked.home_goals == home_goals
            and locked.away_goals == away_goals
            and locked.status == Match.Status.FINISHED
        ):
            return locked, False

        previous = _state(locked)
        locked.home_goals = home_goals
        locked.away_goals = away_goals
        # A corrected score is no longer a walkover.
        locked.is_walkover = False
        locked.status = Match.Status.FINISHED
        if locked.result_reported_by_id is None:
            locked.result_reported_by = admin_user
        locked.result_reported_at = timezone.now()
        locked.contested_by = None
        locked.contested_at = None
        locked.contest_reason = ""
        locked.save(
            update_fields=[
                "home_goals",
                "away_goals",
                "is_walkover",
                "status",
                "result_reported_by",
                "result_reported_at",
                "contested_by",
                "contested_at",
                "contest_reason",
                "updated_at",
            ]
        )
        _log(
            locked,
            admin_user,
            MatchResultLog.Action.RESULT_CORRECTED,
            previous,
            _state(locked),
            note=note,
        )
        return locked, True


def contest_result(match: Match, user, reason: str = "") -> tuple[Match, bool]:
    """The opponent of whoever reported the result may contest it within 48h."""
    with transaction.atomic():
        locked = _get_locked_match(match.pk)
        is_admin = bool(user.is_staff)

        if not is_admin and not locked.involves(user):
            raise AppError("NOT_MATCH_PARTICIPANT", 403)

        if locked.status == Match.Status.CONTESTED:
            # Already contested: re-sending the request is a harmless no-op.
            return locked, False

        if not locked.has_result:
            raise AppError("RESULT_NOT_REGISTERED", 409)

        if locked.result_reported_by_id == user.id:
            raise AppError("CANNOT_CONTEST_OWN_RESULT", 403)

        if locked.contested_at is not None:
            # The admin already reviewed a contest for this result.
            raise AppError("CONTEST_ALREADY_REVIEWED", 409)

        deadline = locked.contest_deadline
        if deadline is None or timezone.now() > deadline:
            raise AppError("CONTEST_WINDOW_CLOSED", 409)

        previous = _state(locked)
        locked.status = Match.Status.CONTESTED
        locked.contested_by = user
        locked.contested_at = timezone.now()
        locked.contest_reason = reason.strip()[:500]
        locked.save(
            update_fields=[
                "status",
                "contested_by",
                "contested_at",
                "contest_reason",
                "updated_at",
            ]
        )
        _log(
            locked,
            user,
            MatchResultLog.Action.RESULT_CONTESTED,
            previous,
            _state(locked),
            note=locked.contest_reason,
        )
        return locked, True


def confirm_result(match: Match, admin_user) -> tuple[Match, bool]:
    """Admin accepts the result as is, closing the contest."""
    if not getattr(admin_user, "is_staff", False):
        raise AppError("ADMIN_ONLY", 403)

    with transaction.atomic():
        locked = _get_locked_match(match.pk)
        if locked.status != Match.Status.CONTESTED:
            return locked, False

        previous = _state(locked)
        # Keep the contest metadata for the audit trail; it also prevents the
        # same result from being contested again after review.
        locked.status = Match.Status.FINISHED
        locked.save(update_fields=["status", "updated_at"])
        _log(
            locked,
            admin_user,
            MatchResultLog.Action.RESULT_CONFIRMED,
            previous,
            _state(locked),
        )
        return locked, True


def update_kickoff(match: Match, user, kickoff_at) -> tuple[Match, bool]:
    """Only the two players (or admin) may schedule; finished games are locked.

    Scheduling is intentionally NOT affected by the round lock: a delayed match
    in a blocked round still needs a new date.
    """
    with transaction.atomic():
        locked = _get_locked_match(match.pk)
        if not user.is_staff and not locked.involves(user):
            raise AppError("NOT_MATCH_PARTICIPANT", 403)
        if locked.has_result or locked.status != Match.Status.SCHEDULED:
            raise AppError("MATCH_ALREADY_FINISHED", 409)

        if locked.kickoff_at == kickoff_at:
            return locked, False

        previous = _state(locked)
        locked.kickoff_at = kickoff_at
        locked.save(update_fields=["kickoff_at", "updated_at"])
        _log(
            locked,
            user,
            MatchResultLog.Action.KICKOFF_CHANGED,
            previous,
            _state(locked),
        )
        return locked, True
