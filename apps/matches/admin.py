from django.contrib import admin
from .models import Match, MatchEvent, DigitalScoreSheet


class MatchEventInline(admin.TabularInline):
    model = MatchEvent
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = (
        "home_team",
        "home_score",
        "away_score",
        "away_team",
        "status",
        "current_period",
        "scheduled_at",
        "table_official",
    )
    list_filter = ("status", "season", "current_period")
    search_fields = ("home_team__name", "away_team__name")
    inlines = [MatchEventInline]


@admin.register(MatchEvent)
class MatchEventAdmin(admin.ModelAdmin):
    list_display = ("match", "period", "game_clock", "team", "player", "event_type", "points")
    list_filter = ("event_type", "period")
    search_fields = ("match__home_team__name", "match__away_team__name", "player__first_name", "player__last_name")


@admin.register(DigitalScoreSheet)
class DigitalScoreSheetAdmin(admin.ModelAdmin):
    list_display = ("match", "is_closed", "referee_signature", "closed_at")
    list_filter = ("is_closed",)
