"""Create a demo league with fictitious players for a visual test drive.

Usage:
    python manage.py seed_demo
    python manage.py seed_demo --reset --players 10 --results 4
    python manage.py seed_demo --no-fixtures
"""
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from core.exceptions import AppError
from league.models import League, Match, Participant
from league.services.fixtures import generate_fixtures
from league.services.results import report_result

TEAMS = [
    "Trovão FC",
    "Dragões SC",
    "Falcões EC",
    "Titãs FC",
    "Lobos FC",
    "Cometas FC",
    "Fênix FC",
    "Relâmpago FC",
    "Meteoros FC",
    "Tempestade FC",
]
PLAYERS = [
    "Carlos",
    "Bruno",
    "Diego",
    "Eduardo",
    "Felipe",
    "Gustavo",
    "Henrique",
    "Igor",
    "João",
    "Lucas",
]
DEMO_EMAIL_DOMAIN = "demo.efootball"
# Example of the customizable league name.
DEMO_LEAGUE_NAME = "Liga dos Amigos"


class Command(BaseCommand):
    help = "Cria uma liga demo com jogadores fictícios (admin, confrontos e placares)."

    def add_arguments(self, parser):
        parser.add_argument("--players", type=int, default=8, help="Number of demo players.")
        parser.add_argument(
            "--reset", action="store_true", help="Delete the demo league/users and rebuild."
        )
        parser.add_argument(
            "--no-fixtures", action="store_true", help="Only create players and league."
        )
        parser.add_argument(
            "--results", type=int, default=2, help="How many matches should start with a score."
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Permite rodar com DEBUG=False (somente em ambiente descartável).",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            raise CommandError(
                "seed_demo cria contas com senhas conhecidas e é bloqueado com "
                "DEBUG=False. Use --force apenas em um ambiente descartável."
            )
        players_count = max(2, min(int(options["players"]), len(PLAYERS)))
        results_count = max(0, int(options["results"]))

        with transaction.atomic():
            if options["reset"]:
                League.objects.filter(name=DEMO_LEAGUE_NAME).delete()
                User.objects.filter(email__endswith=f"@{DEMO_EMAIL_DOMAIN}").delete()

            league, _ = League.objects.get_or_create(
                name=DEMO_LEAGUE_NAME,
                defaults={"status": League.Status.REGISTRATION, "is_active": True},
            )
            # Keep a single active league for the UI.
            League.objects.exclude(pk=league.pk).update(is_active=False)
            league.is_active = True

            admin, created_admin = User.objects.get_or_create(
                email=f"admin@{DEMO_EMAIL_DOMAIN}",
                defaults={"name": "Administrador", "team_name": "Comissão Técnica", "is_staff": True},
            )
            if created_admin or not admin.has_usable_password():
                admin.set_password("admin12345")
                admin.save(update_fields=["password"])
            if not admin.is_staff:
                admin.is_staff = True
                admin.save(update_fields=["is_staff"])

            for index in range(players_count):
                email = f"jogador{index + 1}@{DEMO_EMAIL_DOMAIN}"
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        "name": PLAYERS[index],
                        "team_name": TEAMS[index],
                    },
                )
                if created:
                    user.set_password("demo12345")
                    user.save(update_fields=["password"])
                Participant.objects.get_or_create(league=league, user=user)

            if not options["no_fixtures"] and league.fixtures_generated_at is None:
                generate_fixtures(league)
                # The service updates the status in the database; refresh the
                # local instance so we never write stale fields back.
                league.refresh_from_db()
            league.save(update_fields=["is_active"])

            already_scored = Match.objects.filter(
                league=league, home_goals__isnull=False
            ).count()
            if results_count and already_scored < results_count:
                pending = list(
                    Match.objects.filter(
                        league=league,
                        status=Match.Status.SCHEDULED,
                        home_goals__isnull=True,
                    )
                    .select_related("home", "away", "round")
                    .order_by("round__number", "id")[:results_count]
                )
                for index, match in enumerate(pending):
                    if match.round.number == 1 and match.kickoff_at is None and index < 3:
                        match.kickoff_at = timezone.now() + timedelta(days=index + 1, hours=20)
                        match.save(update_fields=["kickoff_at"])
                    home_goals = (index + 1) % 3
                    away_goals = (index + 2) % 2
                    try:
                        report_result(match, admin, home_goals, away_goals)
                    except AppError:
                        # The sequential round lock stops the demo from filling
                        # a later round before the current one is closed.
                        break

            # Schedule a few upcoming matches so the rounds panel looks alive.
            upcoming = Match.objects.filter(
                league=league, home_goals__isnull=True, kickoff_at__isnull=True
            ).order_by("round__number", "id")[:5]
            for index, match in enumerate(upcoming):
                match.kickoff_at = timezone.now() + timedelta(days=3 + index)
                match.save(update_fields=["kickoff_at"])

            totals = {
                "rounds": league.rounds.count(),
                "matches": league.matches.count(),
                "participants": league.participants.count(),
                "finished": league.matches.exclude(home_goals__isnull=True).count(),
            }

        self.stdout.write(self.style.SUCCESS(f"Liga demo pronta: {league.name}"))
        self.stdout.write(
            f"Admin:    admin@{DEMO_EMAIL_DOMAIN} / admin12345"
        )
        self.stdout.write(
            f"Jogador:  jogador1@{DEMO_EMAIL_DOMAIN} / demo12345 (até jogador{players_count})"
        )
        self.stdout.write(
            "Resumo:   {participants} jogadores, {rounds} rodadas, {matches} partidas, "
            "{finished} com placar".format(**totals)
        )
