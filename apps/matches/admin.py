from django.contrib import admin
from .models import Match, MatchEvent, DigitalScoreSheet


class MatchEventInline(admin.TabularInline):
    model = MatchEvent
    extra = 0
    show_change_link = True
    can_delete = False
    readonly_fields = ("period", "game_clock", "team", "player", "event_type", "points", "description", "created_at")


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
        "timekeeper",
    )
    list_filter = ("status", "season", "current_period")
    search_fields = ("home_team__name", "away_team__name")
    inlines = [MatchEventInline]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name in ["table_official", "timekeeper"]:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            kwargs["queryset"] = User.objects.filter(role=User.Role.TABLE_OFFICIAL)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(MatchEvent)
class MatchEventAdmin(admin.ModelAdmin):
    list_display = ("match", "period", "game_clock", "team", "player", "event_type", "points")
    list_filter = ("event_type", "period")
    search_fields = ("match__home_team__name", "match__away_team__name", "player__first_name", "player__last_name")


@admin.register(DigitalScoreSheet)
class DigitalScoreSheetAdmin(admin.ModelAdmin):
    list_display = ("match", "is_closed", "referee_signature", "table_official_signature", "timekeeper_signature", "closed_at")
    list_filter = ("is_closed",)
