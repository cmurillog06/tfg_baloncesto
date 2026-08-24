from django.contrib import admin
from .models import League, Season, Team, Player, TeamMembership


class TeamMembershipInline(admin.TabularInline):
    model = TeamMembership
    extra = 1
    autocomplete_fields = ["player"]


@admin.register(League)
class LeagueAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ("league", "name", "start_date", "end_date", "is_current")
    list_filter = ("league", "is_current")


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "acronym", "city", "coach", "created_at")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "acronym", "city")
    inlines = [TeamMembershipInline]


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ("last_name", "first_name", "position", "height_cm", "is_active")
    list_filter = ("position", "is_active")
    search_fields = ("first_name", "last_name")


@admin.register(TeamMembership)
class TeamMembershipAdmin(admin.ModelAdmin):
    list_display = ("jersey_number", "player", "team", "season", "is_captain", "is_active")
    list_filter = ("season", "team", "is_captain", "is_active")
    search_fields = ("player__first_name", "player__last_name", "team__name")
