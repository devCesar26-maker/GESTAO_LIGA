"""Admin-signed enrollment and removal of league participants."""
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction

from accounts.models import User
from core.exceptions import AppError

from ..models import League, Match, Participant
from .fixtures import reset_and_regenerate


def add_participant(
    league: League,
    *,
    email: str,
    name: str = "",
    team_name: str = "",
    password: str = "",
) -> tuple[Participant, bool]:
    """Enroll an existing user by email, or create the account if needed.

    Returns ``(participant, user_created)``.
    """
    email = (email or "").strip().lower()
    if not email:
        raise AppError(
            "INVALID_DATA", 400, {"errors": {"email": ["Informe o email do jogador."]}}
        )

    with transaction.atomic():
        user = User.objects.filter(email__iexact=email).first()
        user_created = False

        if user is None:
            name = (name or "").strip()
            team_name = (team_name or "").strip()
            if not name or not team_name or not password:
                raise AppError(
                    "INVALID_DATA",
                    400,
                    {
                        "errors": {
                            "email": [
                                "Não existe conta com este email. Informe nome, nome do time "
                                "e uma senha para criar a conta."
                            ]
                        }
                    },
                )
            try:
                validate_password(password)
            except DjangoValidationError as exc:
                raise AppError(
                    "WEAK_PASSWORD", 400, {"errors": {"password": list(exc.messages)}}
                )
            try:
                user = User.objects.create_user(
                    email=email, password=password, name=name, team_name=team_name
                )
                user_created = True
            except IntegrityError:
                raise AppError("EMAIL_TAKEN", 400)

        if Participant.objects.filter(league=league, user=user).exists():
            raise AppError("PLAYER_ALREADY_IN_LEAGUE", 409)

        participant = Participant.objects.create(league=league, user=user)
        return participant, user_created


def remove_participant(participant: Participant) -> bool:
    """Remove a player from the league, preserving the login account.

    Returns ``True`` when the fixtures had to be regenerated without the player.
    If the player already has matches, removal is only allowed while no result
    exists; otherwise deleting the participant would erase match history and
    change the standings.
    """
    with transaction.atomic():
        league = League.objects.select_for_update().get(pk=participant.league_id)
        participant = (
            league.participants.select_related("user").filter(pk=participant.pk).first()
        )
        if participant is None:
            raise AppError("NOT_FOUND", 404)

        has_matches = (
            participant.home_matches.exists() or participant.away_matches.exists()
        )
        if has_matches:
            has_results = (
                Match.objects.filter(league=league)
                .exclude(home_goals__isnull=True, away_goals__isnull=True)
                .exists()
                or Match.objects.filter(
                    league=league,
                    status__in=[Match.Status.FINISHED, Match.Status.CONTESTED],
                ).exists()
            )
            if has_results:
                raise AppError("CANNOT_REMOVE_PARTICIPANT_WITH_RESULTS", 409)
            if league.participants.exclude(pk=participant.pk).count() < 2:
                raise AppError("CANNOT_REMOVE_LAST_PLAYERS", 409)

        participant.delete()
        if has_matches:
            # No result exists, so rebuilding the schedule is safe and keeps
            # rounds, byes and standings consistent after the removal.
            reset_and_regenerate(league)
            return True
        return False
