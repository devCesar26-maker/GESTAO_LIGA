from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class League(models.Model):
    """A season/championship. The app starts with a single active league but
    the schema supports several seasons."""

    class Status(models.TextChoices):
        REGISTRATION = "REGISTRATION", "Inscrições abertas"
        IN_PROGRESS = "IN_PROGRESS", "Em andamento"
        FINISHED = "FINISHED", "Finalizada"

    name = models.CharField(
        "nome", max_length=100, default="Liga eFootball"
    )
    status = models.CharField(
        "situação", max_length=20, choices=Status.choices, default=Status.REGISTRATION
    )
    is_active = models.BooleanField("ativa", default=True)
    fixtures_generated_at = models.DateTimeField("confrontos gerados em", null=True, blank=True)
    fixture_seed = models.BigIntegerField("semente do sorteio", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "liga"
        verbose_name_plural = "ligas"
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["name"], name="unique_league_name"),
        ]

    def __str__(self):
        return self.name

    @classmethod
    def get_active(cls):
        """Return the active league, falling back to the newest one."""
        return (
            cls.objects.filter(is_active=True).order_by("created_at").first()
            or cls.objects.order_by("-created_at").first()
        )

    @property
    def registration_open(self) -> bool:
        return self.status == self.Status.REGISTRATION and self.fixtures_generated_at is None

    @property
    def players_count(self) -> int:
        return self.participants.count()

    @property
    def current_round_number(self):
        """First round with a pending match, or the last round when all played."""
        pending = (
            self.matches.filter(status=Match.Status.SCHEDULED)
            .order_by("round__number")
            .values_list("round__number", flat=True)
            .first()
        )
        if pending is not None:
            return pending
        return self.rounds.order_by("-number").values_list("number", flat=True).first()


class Participant(models.Model):
    """A player enrolled in a league."""

    league = models.ForeignKey(
        League, on_delete=models.CASCADE, related_name="participants", verbose_name="liga"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="participations",
        verbose_name="jogador",
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "participante"
        verbose_name_plural = "participantes"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["league", "user"], name="unique_league_participant"),
        ]

    def __str__(self):
        return f"{self.team_name} ({self.league.name})"

    @property
    def team_name(self) -> str:
        return self.user.display_team

    @property
    def player_name(self) -> str:
        return self.user.display_name


class Round(models.Model):
    """A matchday. ``leg`` 1 is the first turn, 2 the return turn."""

    league = models.ForeignKey(
        League, on_delete=models.CASCADE, related_name="rounds", verbose_name="liga"
    )
    number = models.PositiveIntegerField("número")
    leg = models.PositiveSmallIntegerField("turno", default=1)

    class Meta:
        verbose_name = "rodada"
        verbose_name_plural = "rodadas"
        ordering = ["number"]
        constraints = [
            models.UniqueConstraint(fields=["league", "number"], name="unique_round_number"),
            models.UniqueConstraint(
                fields=["league", "leg", "number"], name="unique_round_leg_number"
            ),
            models.CheckConstraint(
                condition=Q(leg__in=[1, 2]), name="round_leg_valid"
            ),
        ]

    def __str__(self):
        return f"Rodada {self.number} (turno {self.leg})"


class Match(models.Model):
    """A fixture. Results are typed in manually (no game API)."""

    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Agendada"
        FINISHED = "FINISHED", "Finalizada"
        CONTESTED = "CONTESTED", "Contestada"

    league = models.ForeignKey(
        League, on_delete=models.CASCADE, related_name="matches", verbose_name="liga"
    )
    round = models.ForeignKey(
        Round, on_delete=models.CASCADE, related_name="matches", verbose_name="rodada"
    )
    leg = models.PositiveSmallIntegerField("turno", default=1)
    home = models.ForeignKey(
        Participant,
        on_delete=models.CASCADE,
        related_name="home_matches",
        verbose_name="mandante",
    )
    away = models.ForeignKey(
        Participant,
        on_delete=models.CASCADE,
        related_name="away_matches",
        verbose_name="visitante",
    )
    kickoff_at = models.DateTimeField("data e hora", null=True, blank=True)
    is_walkover = models.BooleanField("vitória por W.O.", default=False)
    status = models.CharField(
        "situação", max_length=20, choices=Status.choices, default=Status.SCHEDULED
    )
    home_goals = models.PositiveSmallIntegerField("gols do mandante", null=True, blank=True)
    away_goals = models.PositiveSmallIntegerField("gols do visitante", null=True, blank=True)
    result_reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reported_results",
        verbose_name="resultado lançado por",
    )
    result_reported_at = models.DateTimeField("resultado lançado em", null=True, blank=True)
    contested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contested_results",
        verbose_name="contestado por",
    )
    contested_at = models.DateTimeField("contestado em", null=True, blank=True)
    contest_reason = models.CharField("motivo da contestação", max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "partida"
        verbose_name_plural = "partidas"
        ordering = ["round__number", "id"]
        indexes = [
            models.Index(fields=["league", "status"]),
            models.Index(fields=["league", "round"]),
        ]
        constraints = [
            # One ordered pairing per league: A x B exists once in the first
            # turn and B x A once in the return turn.
            models.UniqueConstraint(
                fields=["league", "home", "away"], name="unique_league_home_away"
            ),
            models.CheckConstraint(
                condition=~Q(home=F("away")), name="match_teams_differ"
            ),
            models.CheckConstraint(
                condition=Q(home_goals__isnull=True)
                | Q(home_goals__gte=0, home_goals__lte=30),
                name="match_home_goals_range",
            ),
            models.CheckConstraint(
                condition=Q(away_goals__isnull=True)
                | Q(away_goals__gte=0, away_goals__lte=30),
                name="match_away_goals_range",
            ),
            models.CheckConstraint(
                condition=Q(home_goals__isnull=True, away_goals__isnull=True)
                | Q(home_goals__isnull=False, away_goals__isnull=False),
                name="match_both_scores_set",
            ),
        ]

    def __str__(self):
        return f"{self.home.team_name} x {self.away.team_name} (R{self.round.number})"

    @property
    def has_result(self) -> bool:
        return self.home_goals is not None and self.away_goals is not None

    @property
    def is_closed(self) -> bool:
        """A result is registered (a W.O. counts) so the round can advance."""
        return (
            self.status in (self.Status.FINISHED, self.Status.CONTESTED)
            and self.has_result
        )

    @property
    def is_contested(self) -> bool:
        return self.status == self.Status.CONTESTED

    @property
    def contest_deadline(self):
        if self.result_reported_at is None:
            return None
        return self.result_reported_at + timedelta(hours=settings.CONTEST_WINDOW_HOURS)

    @property
    def score(self):
        if not self.has_result:
            return None
        return {"home": self.home_goals, "away": self.away_goals}

    def involves(self, user) -> bool:
        if user is None or not getattr(user, "is_authenticated", False):
            return False
        return user.id in (self.home.user_id, self.away.user_id)

    def opponent_of(self, user):
        if user is None or not getattr(user, "is_authenticated", False):
            return None
        if self.home.user_id == user.id:
            return self.away
        if self.away.user_id == user.id:
            return self.home
        return None


class MatchResultLog(models.Model):
    """Full audit trail for result and schedule changes."""

    class Action(models.TextChoices):
        RESULT_REPORTED = "RESULT_REPORTED", "Resultado lançado"
        RESULT_CORRECTED = "RESULT_CORRECTED", "Resultado corrigido"
        RESULT_CONFIRMED = "RESULT_CONFIRMED", "Resultado confirmado"
        RESULT_CONTESTED = "RESULT_CONTESTED", "Resultado contestado"
        RESULT_WALKOVER = "RESULT_WALKOVER", "Vitória por W.O."
        KICKOFF_CHANGED = "KICKOFF_CHANGED", "Data alterada"
        FIXTURES_GENERATED = "FIXTURES_GENERATED", "Confrontos gerados"
        FIXTURES_REGENERATED = "FIXTURES_REGENERATED", "Confrontos regerados"

    match = models.ForeignKey(
        Match, on_delete=models.CASCADE, related_name="logs", verbose_name="partida"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="match_logs",
        verbose_name="usuário",
    )
    action = models.CharField("ação", max_length=30, choices=Action.choices)
    previous = models.JSONField("valores anteriores", default=dict, blank=True)
    new = models.JSONField("novos valores", default=dict, blank=True)
    note = models.CharField("observação", max_length=500, blank=True)
    created_at = models.DateTimeField("quando", auto_now_add=True)

    class Meta:
        verbose_name = "registro de auditoria"
        verbose_name_plural = "registros de auditoria"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["match", "-created_at"])]

    def __str__(self):  # pragma: no cover
        return f"{self.match_id} {self.action} {self.created_at:%d/%m/%Y %H:%M}"


class LeagueChangeLog(models.Model):
    """Audit trail for league settings (currently the custom display name)."""

    class Action(models.TextChoices):
        NAME_CHANGED = "NAME_CHANGED", "Nome alterado"

    league = models.ForeignKey(
        League, on_delete=models.CASCADE, related_name="change_logs", verbose_name="liga"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="league_logs",
        verbose_name="usuário",
    )
    action = models.CharField("ação", max_length=30, choices=Action.choices)
    previous = models.JSONField("valores anteriores", default=dict, blank=True)
    new = models.JSONField("novos valores", default=dict, blank=True)
    created_at = models.DateTimeField("quando", auto_now_add=True)

    class Meta:
        verbose_name = "registro de configuração da liga"
        verbose_name_plural = "registros de configuração da liga"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["league", "-created_at"])]

    def __str__(self):  # pragma: no cover
        return f"{self.league_id} {self.action} {self.created_at:%d/%m/%Y %H:%M}"
