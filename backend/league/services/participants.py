"""Admin-signed enrollment for people who could not self-register."""
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction

from accounts.models import User
from core.exceptions import AppError

from ..models import League, Participant


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
