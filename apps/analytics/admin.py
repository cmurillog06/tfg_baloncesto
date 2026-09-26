from django.contrib import admin
from .models import Standing, PlayerMatchStat


@admin.register(Standing)
class StandingAdmin(admin.ModelAdmin):
    list_display = (
        "team",
        "season",
        "games_played",
        "wins",
        "losses",
        "points_for",
        "points_against",
        "points_diff",
        "league_points",
    )
    list_filter = ("season",)
    search_fields = ("team__name", "team__acronym")


@admin.register(PlayerMatchStat)
class PlayerMatchStatAdmin(admin.ModelAdmin):
    list_display = (
        "player",
        "team",
        "match",
        "points",
        "total_rebounds",
        "assists",
        "valuation_pir",
    )
    list_filter = ("team", "match")
    search_fields = ("player__first_name", "player__last_name", "team__name")