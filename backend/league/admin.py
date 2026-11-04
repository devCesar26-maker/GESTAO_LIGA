from django.contrib import admin

from .models import League, LeagueChangeLog, Match, MatchResultLog, Participant, Round


class ParticipantInline(admin.TabularInline):
    model = Participant
    extra = 0
    autocomplete_fields = ["user"]


class RoundInline(admin.TabularInline):
    model = Round
    extra = 0


@admin.register(League)
class LeagueAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "status",
        "is_active",
        "single_round_mode",
        "fixtures_generated_at",
        "fixture_seed",
    )
    list_filter = ("status", "is_active", "single_round_mode")
    inlines = [RoundInline, ParticipantInline]


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ("team_name", "player_name", "league", "joined_at")
    list_filter = ("league",)
    search_fields = ("user__email", "user__name", "user__team_name")


@admin.register(Round)
class RoundAdmin(admin.ModelAdmin):
    list_display = ("league", "number", "leg")
    list_filter = ("league", "leg")


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "league",
        "round",
        "home",
        "away",
        "status",
        "home_goals",
        "away_goals",
        "is_walkover",
        "kickoff_at",
    )
    list_filter = ("league", "status", "leg", "is_walkover")
    search_fields = ("home__user__team_name", "away__user__team_name")


@admin.register(MatchResultLog)
class MatchResultLogAdmin(admin.ModelAdmin):
    list_display = ("match", "action", "user", "created_at")
    list_filter = ("action",)
    readonly_fields = ("match", "user", "action", "previous", "new", "note", "created_at")


@admin.register(LeagueChangeLog)
class LeagueChangeLogAdmin(admin.ModelAdmin):
    list_display = ("league", "action", "user", "created_at")
    list_filter = ("action",)
    readonly_fields = ("league", "user", "action", "previous", "new", "created_at")
