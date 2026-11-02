from django.db.models import Prefetch, Q
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import AppError
from core.idempotency import run_idempotent
from core.messages import MESSAGES
from core.permissions import IsAdmin, IsAuthenticatedWithMessage, IsMatchParticipant

from .models import League, Match, MatchResultLog, Participant, Round
from .serializers import (
    AdminEnrollSerializer,
    AdminParticipantSerializer,
    ContestSerializer,
    KickoffSerializer,
    LeagueNameSerializer,
    LeagueSerializer,
    MatchResultLogSerializer,
    MatchSerializer,
    ParticipantSerializer,
    ResultSerializer,
    RoundSerializer,
    WalkoverSerializer,
)
from .services.fixtures import generate_fixtures, reset_and_regenerate
from .services.league_name import update_league_name
from .services.participants import add_participant
from .services.results import (
    confirm_result,
    contest_result,
    correct_result,
    register_walkover,
    report_result,
    update_kickoff,
)
from .services.rounds import round_states
from .services.standings import compute_standings


def get_league() -> League:
    league = League.get_active()
    if league is None:
        raise AppError("NO_ACTIVE_LEAGUE", 404)
    return league


def match_queryset():
    return Match.objects.select_related(
        "home__user",
        "away__user",
        "round",
        "result_reported_by",
        "contested_by",
    )


def get_match(pk: int) -> Match:
    match = match_queryset().filter(pk=pk).first()
    if match is None:
        raise AppError("NOT_FOUND", 404)
    return match


def serialize_match(match, request, states=None):
    if states is None:
        states = round_states(match.league)
    return MatchSerializer(
        match, context={"request": request, "round_states": states}
    ).data


class LeagueDetailView(APIView):
    """Public: current league overview."""

    permission_classes = [AllowAny]

    def get(self, request):
        league = get_league()
        return Response(LeagueSerializer(league).data)


class ParticipantListView(APIView):
    """Public: enrolled players."""

    permission_classes = [AllowAny]

    def get(self, request):
        league = get_league()
        participants = league.participants.select_related("user").all()
        return Response(ParticipantSerializer(participants, many=True).data)


class StandingsView(APIView):
    """Public: table always derived from finished matches."""

    permission_classes = [AllowAny]

    def get(self, request):
        league = get_league()
        rows = compute_standings(league)
        return Response(rows)


class RoundListView(APIView):
    """Public: rounds grouped by leg, with optional filters."""

    permission_classes = [AllowAny]

    def get(self, request):
        league = get_league()
        mine = request.query_params.get("mine") in {"1", "true", "True", "yes"}
        if mine and not request.user.is_authenticated:
            raise AppError("NOT_AUTHENTICATED", 401)

        matches = match_queryset().filter(league=league)
        if mine:
            matches = matches.filter(
                Q(home__user=request.user) | Q(away__user=request.user)
            )

        rounds = league.rounds.prefetch_related(
            Prefetch("matches", queryset=matches)
        ).all()

        leg = request.query_params.get("leg")
        if leg in {"1", "2"}:
            rounds = rounds.filter(leg=int(leg))

        data = RoundSerializer(
            rounds,
            many=True,
            context={"request": request, "round_states": round_states(league)},
        ).data
        if mine:
            data = [round_data for round_data in data if round_data["matches"]]
        return Response(data)


class MatchListView(APIView):
    """Public: flat list of matches with filters."""

    permission_classes = [AllowAny]

    def get(self, request):
        league = get_league()
        queryset = match_queryset().filter(league=league)

        mine = request.query_params.get("mine") in {"1", "true", "True", "yes"}
        if mine:
            if not request.user.is_authenticated:
                raise AppError("NOT_AUTHENTICATED", 401)
            queryset = queryset.filter(
                Q(home__user=request.user) | Q(away__user=request.user)
            )

        status_filter = request.query_params.get("status")
        if status_filter == "pending":
            queryset = queryset.filter(status=Match.Status.SCHEDULED)
        elif status_filter == "finished":
            queryset = queryset.filter(status=Match.Status.FINISHED)
        elif status_filter == "contested":
            queryset = queryset.filter(status=Match.Status.CONTESTED)

        round_number = request.query_params.get("round")
        if round_number and str(round_number).isdigit():
            queryset = queryset.filter(round__number=int(round_number))

        return Response(
            MatchSerializer(
                queryset,
                many=True,
                context={"request": request, "round_states": round_states(league)},
            ).data
        )


class MatchDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        return Response(serialize_match(get_match(pk), request))


class MatchLogsView(APIView):
    """Admin: audit trail for a match."""

    permission_classes = [IsAdmin]

    def get(self, request, pk):
        match = get_match(pk)
        logs = match.logs.select_related("user").all()
        return Response(MatchResultLogSerializer(logs, many=True).data)


class KickoffUpdateView(APIView):
    """Only the two participants (or admin) may schedule a match."""

    permission_classes = [IsAuthenticatedWithMessage, IsMatchParticipant]

    def patch(self, request, pk):
        match = get_match(pk)
        self.check_object_permissions(request, match)

        serializer = KickoffSerializer(data=request.data)
        if not serializer.is_valid():
            raise AppError("INVALID_KICKOFF_DATE", 400)

        updated, changed = update_kickoff(
            match, request.user, serializer.validated_data["kickoff_at"]
        )
        code = "KICKOFF_UPDATED" if changed else "NOTHING_CHANGED"
        return Response(
            {
                "code": code,
                "message": MESSAGES[code],
                "match": serialize_match(updated, request),
            }
        )


class MatchResultView(APIView):
    """POST registers (participants only, winner reports); PATCH corrects (admin)."""

    def get_permissions(self):
        if self.request.method == "PATCH":
            return [IsAdmin()]
        return [IsAuthenticatedWithMessage(), IsMatchParticipant()]

    def post(self, request, pk):
        match = get_match(pk)
        self.check_object_permissions(request, match)

        serializer = ResultSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        def action():
            updated, changed = report_result(
                match,
                request.user,
                serializer.validated_data["home_goals"],
                serializer.validated_data["away_goals"],
            )
            code = "RESULT_REPORTED" if changed else "NOTHING_CHANGED"
            return Response(
                {
                    "code": code,
                    "message": MESSAGES[code],
                    "changed": changed,
                    "match": serialize_match(updated, request),
                }
            )

        return run_idempotent(request, f"report-result:{match.pk}", action)

    def patch(self, request, pk):
        match = get_match(pk)
        serializer = ResultSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        updated, changed = correct_result(
            match,
            request.user,
            serializer.validated_data["home_goals"],
            serializer.validated_data["away_goals"],
            note=str(request.data.get("note", ""))[:500],
        )
        code = "RESULT_CORRECTED" if changed else "NOTHING_CHANGED"
        return Response(
            {
                "code": code,
                "message": MESSAGES[code],
                "changed": changed,
                "match": serialize_match(updated, request),
            }
        )


class ContestResultView(APIView):
    permission_classes = [IsAuthenticatedWithMessage, IsMatchParticipant]

    def post(self, request, pk):
        match = get_match(pk)
        self.check_object_permissions(request, match)

        serializer = ContestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        updated, changed = contest_result(
            match, request.user, serializer.validated_data.get("reason", "")
        )
        return Response(
            {
                "code": "RESULT_CONTESTED" if changed else "NOTHING_CHANGED",
                "message": MESSAGES["RESULT_CONTESTED"],
                "changed": changed,
                "match": serialize_match(updated, request),
            }
        )


class ConfirmResultView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, pk):
        match = get_match(pk)
        updated, changed = confirm_result(match, request.user)
        return Response(
            {
                "code": "RESULT_CONFIRMED" if changed else "NOTHING_CHANGED",
                "message": MESSAGES["RESULT_CONFIRMED"],
                "changed": changed,
                "match": serialize_match(updated, request),
            }
        )


class GenerateFixturesView(APIView):
    """Admin button: idempotent fixture generation."""

    permission_classes = [IsAdmin]

    def post(self, request):
        league = get_league()

        def action():
            result = generate_fixtures(league)
            return Response(
                {
                    "code": result.code,
                    "message": result.message,
                    "data": result.as_dict(),
                    "league": LeagueSerializer(result.league).data,
                }
            )

        return run_idempotent(request, "generate-fixtures", action)


class ResetAndRegenerateView(APIView):
    """Admin: explicit destructive action, blocked after results exist."""

    permission_classes = [IsAdmin]

    def post(self, request):
        league = get_league()

        def action():
            result = reset_and_regenerate(league)
            return Response(
                {
                    "code": "FIXTURES_REGENERATED",
                    "message": MESSAGES["FIXTURES_REGENERATED"],
                    "data": result.as_dict(),
                    "league": LeagueSerializer(result.league).data,
                }
            )

        return run_idempotent(request, "reset-and-regenerate", action)


class AdminOverviewView(APIView):
    """Admin dashboard payload."""

    permission_classes = [IsAdmin]

    def get(self, request):
        league = get_league()
        participants = league.participants.select_related("user").all()
        contested = match_queryset().filter(league=league, status=Match.Status.CONTESTED)
        pending = match_queryset().filter(league=league, status=Match.Status.SCHEDULED)
        context = {"request": request, "round_states": round_states(league)}
        return Response(
            {
                "league": LeagueSerializer(league).data,
                "participants": AdminParticipantSerializer(participants, many=True).data,
                "contested_matches": MatchSerializer(
                    contested, many=True, context=context
                ).data,
                # Used by the admin walkover action; the round lock still applies.
                "pending_matches_list": MatchSerializer(
                    pending.order_by("round__number", "id")[:20],
                    many=True,
                    context=context,
                ).data,
                "round_states": round_states(league),
                "pending_matches": league.matches.filter(
                    status=Match.Status.SCHEDULED
                ).count(),
                "finished_matches": league.matches.filter(
                    status=Match.Status.FINISHED
                ).count(),
                "has_results": league.matches.exclude(
                    home_goals__isnull=True, away_goals__isnull=True
                ).exists(),
            }
        )


class AdminEnrollView(APIView):
    """Admin: enroll someone after self-registration is closed."""

    permission_classes = [IsAdmin]

    def post(self, request):
        league = get_league()
        serializer = AdminEnrollSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        participant, user_created = add_participant(
            league,
            email=serializer.validated_data["email"],
            name=serializer.validated_data.get("name", ""),
            team_name=serializer.validated_data.get("team_name", ""),
            password=serializer.validated_data.get("password", ""),
        )
        message = MESSAGES["ADDED_TO_LEAGUE"] if league.fixtures_generated_at else MESSAGES[
            "PARTICIPANT_ADDED"
        ]
        return Response(
            {
                "code": "ADDED_TO_LEAGUE",
                "message": message,
                "user_created": user_created,
                "participant": AdminParticipantSerializer(participant).data,
            },
            status=201,
        )


class LeagueSettingsView(APIView):
    """Admin: rename the league at any moment (the change is audited)."""

    permission_classes = [IsAdmin]

    def patch(self, request):
        league = get_league()
        serializer = LeagueNameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        updated, changed = update_league_name(
            league, request.user, serializer.validated_data["name"]
        )
        code = "LEAGUE_UPDATED" if changed else "NOTHING_CHANGED"
        return Response(
            {
                "code": code,
                "message": MESSAGES[code],
                "changed": changed,
                "league": LeagueSerializer(updated).data,
            }
        )


class WalkoverView(APIView):
    """Admin: award a 3x0 when a player does not show up.

    This keeps an absent player from stalling the league, because a W.O. closes
    the match (and therefore the round) exactly like a reported result.
    """

    permission_classes = [IsAdmin]

    def post(self, request, pk):
        match = get_match(pk)
        serializer = WalkoverSerializer(data=request.data)
        if not serializer.is_valid():
            raise AppError("INVALID_ABSENT_SIDE", 400)

        updated, changed = register_walkover(
            match, request.user, serializer.validated_data["absent_side"]
        )
        return Response(
            {
                "code": "WALKOVER_REGISTERED",
                "message": MESSAGES["WALKOVER_REGISTERED"],
                "changed": changed,
                "match": serialize_match(updated, request),
            }
        )
