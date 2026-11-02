from django.conf import settings
from rest_framework import serializers

from core.exceptions import AppError

from .models import League, Match, MatchResultLog, Participant, Round
from .services.results import permissions_for
from .services.rounds import round_states


class ParticipantSerializer(serializers.ModelSerializer):
    player_name = serializers.CharField(read_only=True)
    team_name = serializers.CharField(read_only=True)
    user_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Participant
        fields = ["id", "user_id", "player_name", "team_name", "joined_at"]
        read_only_fields = fields


class AdminParticipantSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    player_name = serializers.CharField(read_only=True)
    team_name = serializers.CharField(read_only=True)

    class Meta:
        model = Participant
        fields = ["id", "email", "player_name", "team_name", "joined_at"]
        read_only_fields = fields


class LeagueSerializer(serializers.ModelSerializer):
    registration_open = serializers.BooleanField(read_only=True)
    players_count = serializers.IntegerField(read_only=True)
    matches_count = serializers.SerializerMethodField()
    rounds_count = serializers.SerializerMethodField()
    current_round = serializers.IntegerField(source="current_round_number", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = League
        fields = [
            "id",
            "name",
            "status",
            "status_label",
            "registration_open",
            "fixtures_generated_at",
            "fixture_seed",
            "players_count",
            "rounds_count",
            "matches_count",
            "current_round",
        ]

    def get_matches_count(self, obj):
        return obj.matches.count()

    def get_rounds_count(self, obj):
        return obj.rounds.count()


class MatchSerializer(serializers.ModelSerializer):
    home = ParticipantSerializer(read_only=True)
    away = ParticipantSerializer(read_only=True)
    round_number = serializers.IntegerField(source="round.number", read_only=True)
    round_state = serializers.SerializerMethodField()
    score = serializers.JSONField(read_only=True)
    has_result = serializers.BooleanField(read_only=True)
    contest_deadline = serializers.DateTimeField(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    reported_by_name = serializers.SerializerMethodField()
    contested_by_name = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = Match
        fields = [
            "id",
            "round_number",
            "round_state",
            "leg",
            "home",
            "away",
            "kickoff_at",
            "is_walkover",
            "status",
            "status_label",
            "home_goals",
            "away_goals",
            "score",
            "has_result",
            "result_reported_at",
            "reported_by_name",
            "contested_at",
            "contested_by_name",
            "contest_reason",
            "contest_deadline",
            "permissions",
            "updated_at",
        ]
        read_only_fields = fields

    def _states(self) -> dict:
        states = self.context.get("round_states")
        if states is None:
            match = getattr(self.instance, "league", None)
            states = round_states(match) if match is not None else {}
            self.context["round_states"] = states
        return states

    def get_round_state(self, obj):
        return self._states().get(obj.round.number)

    def get_reported_by_name(self, obj):
        user = obj.result_reported_by
        return user.display_name if user else None

    def get_contested_by_name(self, obj):
        user = obj.contested_by
        return user.display_name if user else None

    def get_permissions(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        locked = self._states().get(obj.round.number) == "locked"
        return permissions_for(obj, user, round_locked=locked)


class RoundSerializer(serializers.ModelSerializer):
    matches = MatchSerializer(many=True, read_only=True)
    leg_label = serializers.SerializerMethodField()
    state = serializers.SerializerMethodField()
    state_label = serializers.SerializerMethodField()

    class Meta:
        model = Round
        fields = ["id", "number", "leg", "leg_label", "state", "state_label", "matches"]
        read_only_fields = fields

    def get_leg_label(self, obj):
        return "1º turno" if obj.leg == 1 else "2º turno"

    def get_state(self, obj):
        return (self.context.get("round_states") or {}).get(obj.number)

    def get_state_label(self, obj):
        return {"locked": "Bloqueada", "open": "Aberta", "closed": "Encerrada"}.get(
            self.get_state(obj), ""
        )


class MatchResultLogSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    action_label = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = MatchResultLog
        fields = [
            "id",
            "action",
            "action_label",
            "user_name",
            "previous",
            "new",
            "note",
            "created_at",
        ]

    def get_user_name(self, obj):
        return obj.user.display_name if obj.user else "Sistema"


class StandingSerializer(serializers.Serializer):
    position = serializers.IntegerField()
    user_id = serializers.IntegerField()
    participant_id = serializers.IntegerField()
    player_name = serializers.CharField()
    team_name = serializers.CharField()
    played = serializers.IntegerField()
    wins = serializers.IntegerField()
    draws = serializers.IntegerField()
    losses = serializers.IntegerField()
    goals_for = serializers.IntegerField()
    goals_against = serializers.IntegerField()
    goal_difference = serializers.IntegerField()
    points = serializers.IntegerField()


class ScoreField(serializers.IntegerField):
    """Integer 0..MAX_GOALS with the specific INVALID_SCORE error code."""

    def run_validation(self, data=serializers.empty):
        if data is None or data == "":
            raise AppError("INVALID_SCORE", 400)
        return super().run_validation(data)

    def to_internal_value(self, data):
        try:
            value = super().to_internal_value(data)
        except serializers.ValidationError:
            raise AppError("INVALID_SCORE", 400)
        if value < 0 or value > settings.MAX_GOALS_PER_MATCH:
            raise AppError("INVALID_SCORE", 400)
        return value


class ResultSerializer(serializers.Serializer):
    home_goals = ScoreField()
    away_goals = ScoreField()


class ContestSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)


class KickoffSerializer(serializers.Serializer):
    kickoff_at = serializers.DateTimeField(required=True, allow_null=True)


class WalkoverSerializer(serializers.Serializer):
    """``absent_side`` picks who did not show up; the other side wins 3x0."""

    absent_side = serializers.ChoiceField(choices=["home", "away"])


class LeagueNameSerializer(serializers.Serializer):
    """League display name: 3-60 chars, no markup, extra spaces collapsed."""

    name = serializers.CharField(
        max_length=settings.LEAGUE_NAME_MAX_LENGTH * 3,
        trim_whitespace=True,
        allow_blank=True,
    )

    def validate_name(self, value):
        cleaned = " ".join((value or "").split())
        if "<" in cleaned or ">" in cleaned:
            raise AppError("INVALID_LEAGUE_NAME", 400)
        if not (
            settings.LEAGUE_NAME_MIN_LENGTH
            <= len(cleaned)
            <= settings.LEAGUE_NAME_MAX_LENGTH
        ):
            raise AppError("INVALID_LEAGUE_NAME", 400)
        return cleaned


class AdminEnrollSerializer(serializers.Serializer):
    email = serializers.EmailField()
    name = serializers.CharField(required=False, allow_blank=True, max_length=120)
    team_name = serializers.CharField(required=False, allow_blank=True, max_length=60)
    password = serializers.CharField(
        required=False, allow_blank=True, write_only=True, trim_whitespace=False
    )


class AdminOverviewSerializer(serializers.Serializer):
    league = LeagueSerializer()
    participants = AdminParticipantSerializer(many=True)
    contested_matches = MatchSerializer(many=True)
    pending_matches = serializers.IntegerField()
    finished_matches = serializers.IntegerField()
    has_results = serializers.BooleanField()
    seed = serializers.IntegerField(allow_null=True)
