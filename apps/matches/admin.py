from django.contrib import admin, messages
from django.urls import path
from django.shortcuts import render, redirect
from django.utils.html import format_html
from django.urls import reverse
from datetime import datetime

from .models import Match, MatchEvent, DigitalScoreSheet
from .generator import generate_season_schedule, get_season_teams
from apps.teams.models import Season


class MatchEventInline(admin.TabularInline):
    model = MatchEvent
    extra = 0
    show_change_link = True
    can_delete = False
    readonly_fields = ("period", "game_clock", "team", "player", "event_type", "points", "description", "created_at")


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = (
        "round_number",
        "home_team",
        "home_score",
        "away_score",
        "away_team",
        "status",
        "scheduled_at",
        "location",
        "referee",
        "second_referee",
        "table_official",
        "timekeeper",
    )
    list_filter = ("status", "season", "current_period", "round_number")
    search_fields = ("home_team__name", "away_team__name", "location")
    ordering = ("-season__is_current", "season", "round_number", "scheduled_at")
    inlines = [MatchEventInline]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        if db_field.name in ["referee", "second_referee"]:
            kwargs["queryset"] = User.objects.filter(role=User.Role.REFEREE)
        elif db_field.name in ["table_official", "timekeeper"]:
            kwargs["queryset"] = User.objects.filter(role=User.Role.TABLE_OFFICIAL)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "generate-schedule/",
                self.admin_site.admin_view(self.generate_schedule_view),
                name="matches_match_generate_schedule",
            ),
        ]
        return custom_urls + urls

    def generate_schedule_view(self, request):
        """
        Vista administrativa para generar de forma automática y aleatoria el calendario oficial,
        las sedes y las designaciones arbitrales y de mesa.
        """
        all_seasons = Season.objects.filter(is_current=True).select_related("league").order_by("-start_date", "league__name")
        preview_data = None
        error_message = None

        selected_season_id = None
        selected_format_type = "double"
        selected_start_date = ""
        selected_round_interval = 7
        selected_time_slots = "12:30, 17:00, 18:30, 20:45"
        selected_weekend_spread = True
        selected_assign_officials = True
        selected_clear_existing = True

        preview_seed = None

        if request.method == "POST":
            import random
            season_id = request.POST.get("season_id")
            action = request.POST.get("action", "preview")
            double_round = request.POST.get("format_type", "double") == "double"
            start_date_str = request.POST.get("start_date", "").strip()
            interval_str = request.POST.get("round_interval", "7").strip()
            time_slots_str = request.POST.get("time_slots", "12:30, 17:00, 18:30, 20:45").strip()
            weekend_spread = request.POST.get("weekend_spread") == "on"
            assign_officials = request.POST.get("assign_officials") == "on"
            clear_existing = request.POST.get("clear_existing") == "on"
            preview_seed_str = request.POST.get("preview_seed", "").strip()

            try:
                selected_season_id = int(season_id) if season_id else None
            except (ValueError, TypeError):
                selected_season_id = None

            selected_format_type = "double" if double_round else "single"
            selected_start_date = start_date_str
            selected_round_interval = interval_str
            selected_time_slots = time_slots_str
            selected_weekend_spread = weekend_spread
            selected_assign_officials = assign_officials
            selected_clear_existing = clear_existing

            season = Season.objects.filter(id=season_id).first() if season_id else None
            if not season:
                error_message = "Debe seleccionar una temporada válida para confeccionar el calendario."
            elif not season.is_current:
                error_message = f"No es posible generar ni modificar el calendario de '{season.name}' porque es una temporada histórica finalizada. Esta acción solo está permitida para temporadas oficiales activas."
            else:
                start_date = None
                if start_date_str:
                    try:
                        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                    except ValueError:
                        error_message = "Formato de fecha de inicio incorrecto. Utilice AAAA-MM-DD."

                try:
                    interval = int(interval_str)
                except ValueError:
                    interval = 7

                time_slots = [t.strip() for t in time_slots_str.split(",") if t.strip()]
                if not time_slots:
                    time_slots = ["12:30", "17:00", "18:30", "20:45"]

                if not error_message:
                    try:
                        is_dry_run = (action in ["preview", "re_preview"])

                        # Si se solicita una nueva previsualización o probar otra combinación, generar una nueva semilla aleatoria.
                        # Si se solicita guardar, utilizar la semilla preview_seed para persistir exactamente lo previsualizado.
                        if action in ["preview", "re_preview"]:
                            seed_to_use = random.randint(100000, 99999999)
                        elif preview_seed_str:
                            try:
                                seed_to_use = int(preview_seed_str)
                            except ValueError:
                                seed_to_use = random.randint(100000, 99999999)
                        else:
                            seed_to_use = random.randint(100000, 99999999)

                        preview_seed = seed_to_use

                        result = generate_season_schedule(
                            season=season,
                            double_round=double_round,
                            start_date=start_date,
                            round_interval_days=interval,
                            time_slots=time_slots,
                            weekend_spread=weekend_spread,
                            assign_officials=assign_officials,
                            clear_existing=clear_existing,
                            dry_run=is_dry_run,
                            random_seed=seed_to_use,
                        )

                        if action == "generate":
                            if result.get("already_played_rounds", 0) > 0:
                                messages.success(
                                    request,
                                    f"¡Calendario actualizado con éxito! Se han programado {result['total_matches']} partidos para las jornadas restantes "
                                    f"(Jornadas {result['start_round_idx']} a {result['total_rounds']}) de la competición '{season.league.name}' ({season.name}). "
                                    f"Las {result['already_played_rounds']} jornadas previas ya disputadas o en curso ({result['already_played_matches_count']} partidos) se han mantenido intactas."
                                )
                            else:
                                messages.success(
                                    request,
                                    f"¡Calendario generado con éxito! Se han programado {result['total_matches']} partidos a lo largo de {result['total_rounds']} jornadas "
                                    f"para la competición '{season.league.name}' ({season.name}). Todas las sedes y designaciones de árbitros y mesas han quedado asignadas."
                                )
                            return redirect(reverse("admin:matches_match_changelist") + f"?season__id__exact={season.id}")
                        else:
                            preview_data = result

                    except Exception as e:
                        error_message = f"Error al generar el calendario: {str(e)}"

        # Resumen de equipos por temporada para la interfaz
        seasons_info = []
        for s in all_seasons:
            teams = get_season_teams(s)
            seasons_info.append({
                "season": s,
                "teams_count": len(teams),
                "teams": teams,
            })

        is_re_preview = (request.method == "POST" and request.POST.get("action") == "re_preview")

        context = {
            **self.admin_site.each_context(request),
            "title": "Generador Automático de Calendario, Sedes y Designaciones",
            "opts": self.model._meta,
            "seasons_info": seasons_info,
            "preview_data": preview_data,
            "preview_seed": preview_seed,
            "is_re_preview": is_re_preview,
            "error_message": error_message,
            "selected_season_id": selected_season_id,
            "selected_format_type": selected_format_type,
            "selected_start_date": selected_start_date,
            "selected_round_interval": selected_round_interval,
            "selected_time_slots": selected_time_slots,
            "selected_weekend_spread": selected_weekend_spread,
            "selected_assign_officials": selected_assign_officials,
            "selected_clear_existing": selected_clear_existing,
        }
        return render(request, "admin/matches/generate_schedule.html", context)


@admin.register(MatchEvent)
class MatchEventAdmin(admin.ModelAdmin):
    list_display = ("match", "period", "game_clock", "team", "player", "event_type", "points")
    list_filter = ("event_type", "period")
    search_fields = ("match__home_team__name", "match__away_team__name", "player__first_name", "player__last_name")


@admin.register(DigitalScoreSheet)
class DigitalScoreSheetAdmin(admin.ModelAdmin):
    list_display = ("match", "is_closed", "referee_signature", "second_referee_signature", "table_official_signature", "timekeeper_signature", "closed_at")
    list_filter = ("is_closed",)
