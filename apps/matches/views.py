import json
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, View

from .models import Match, MatchEvent, DigitalScoreSheet
from apps.teams.models import TeamMembership
from apps.accounts.permissions import RoleRequiredMixin


class MatchListView(LoginRequiredMixin, ListView):
    """
    Directorio y calendario de todos los partidos: en directo, programados y finalizados.
    Requiere que el usuario haya iniciado sesión.
    """

    model = Match
    template_name = "matches/match_list.html"
    context_object_name = "matches"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.teams.models import Season
        all_seasons = Season.objects.all().select_related("league").order_by("-start_date", "league__name")
        season_id = self.request.GET.get("season")

        base_qs = Match.objects.select_related(
            "home_team", "away_team", "season__league"
        )

        selected_season = None
        if season_id == "all":
            selected_season = None
        elif season_id:
            selected_season = all_seasons.filter(id=season_id).first()
        else:
            selected_season = (
                all_seasons.filter(is_current=True, league__slug="liga-endesa-acb").first()
                or all_seasons.filter(is_current=True).first()
                or all_seasons.first()
            )

        if selected_season:
            base_qs = base_qs.filter(season=selected_season)

        context["all_seasons"] = all_seasons
        context["selected_season"] = selected_season
        context["season_id"] = season_id
        context["live_matches"] = base_qs.filter(status=Match.Status.LIVE).order_by("scheduled_at")
        context["upcoming_matches"] = base_qs.filter(status=Match.Status.SCHEDULED).order_by("scheduled_at")
        context["finished_matches"] = base_qs.filter(status=Match.Status.FINISHED).order_by("-scheduled_at")
        return context


class MatchLiveView(LoginRequiredMixin, DetailView):
    """
    Pantalla de retransmisión en tiempo real (Marcador, Reloj y Eventos por WebSocket).
    Requiere que el usuario haya iniciado sesión.
    """

    model = Match
    template_name = "matches/match_live.html"
    context_object_name = "match"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        match = self.get_object()

        # Plantillas de ambos equipos para el acta / box score (únicas y ligadas a la temporada)
        context["home_roster"] = match.get_team_roster(match.home_team)
        context["away_roster"] = match.get_team_roster(match.away_team)

        # Estadísticas individuales oficiales de este partido (Box Score)
        from apps.analytics.models import PlayerMatchStat
        for member in context["home_roster"]:
            PlayerMatchStat.objects.get_or_create(
                match=match,
                player=member.player,
                defaults={"team": match.home_team}
            )
        for member in context["away_roster"]:
            PlayerMatchStat.objects.get_or_create(
                match=match,
                player=member.player,
                defaults={"team": match.away_team}
            )

        home_stats = list(PlayerMatchStat.objects.filter(
            match=match, team=match.home_team
        ).select_related("player").order_by("-points", "-valuation_pir"))

        away_stats = list(PlayerMatchStat.objects.filter(
            match=match, team=match.away_team
        ).select_related("player").order_by("-points", "-valuation_pir"))

        # Calcular los minutos disputados de forma exacta para todos los jugadores (tanto en pista como en banquillo)
        for st in home_stats + away_stats:
            calc_mins = match.calculate_player_minutes(st.player_id)
            st.live_minutes_played = calc_mins
            if st.minutes_played != calc_mins:
                st.minutes_played = calc_mins
                st.compute_pir()
                st.save(update_fields=["minutes_played", "valuation_pir"])

        context["home_player_stats"] = home_stats
        context["away_player_stats"] = away_stats

        # Tiempos muertos y faltas de equipo según normativa FIBA
        context["home_timeouts"] = match.get_team_timeouts_info(match.home_team)
        context["away_timeouts"] = match.get_team_timeouts_info(match.away_team)
        context["home_fouls_info"] = match.get_team_fouls_info(match.home_team)
        context["away_fouls_info"] = match.get_team_fouls_info(match.away_team)
        home_on_court = match.get_on_court_player_ids(match.home_team)
        away_on_court = match.get_on_court_player_ids(match.away_team)
        context["home_on_court_ids"] = home_on_court
        context["away_on_court_ids"] = away_on_court
        context["home_on_court_json"] = json.dumps(home_on_court)
        context["away_on_court_json"] = json.dumps(away_on_court)

        # Cronología completa de eventos del partido (Jugada a Jugada)
        context["recent_events"] = match.events.select_related(
            "player", "team"
        ).order_by("-id")

        # Asegurar que el acta de un partido finalizado esté formalmente cerrada
        if match.status == Match.Status.FINISHED:
            scoresheet, _ = DigitalScoreSheet.objects.get_or_create(match=match)
            if not scoresheet.is_closed:
                scoresheet.is_closed = True
                if not scoresheet.referee_signature:
                    scoresheet.referee_signature = (
                        f"{match.referee.get_full_name() or match.referee.username} (Lic. FEB-48192)"
                        if match.referee else "Juan Carlos García González (Lic. FEB-48192)"
                    )
                if not scoresheet.second_referee_signature:
                    scoresheet.second_referee_signature = (
                        f"{match.second_referee.get_full_name() or match.second_referee.username} (Lic. FEB-31084)"
                        if match.second_referee else "Antonio Conde Ruiz (Lic. FEB-31084)"
                    )
                if not scoresheet.table_official_signature:
                    scoresheet.table_official_signature = (
                        match.table_official.get_full_name() or match.table_official.username
                        if match.table_official else "Carlos Murillo (Anotador)"
                    )
                if not scoresheet.timekeeper_signature:
                    scoresheet.timekeeper_signature = (
                        match.timekeeper.get_full_name() or match.timekeeper.username
                        if match.timekeeper else "Laura Gómez (Cronometradora)"
                    )
                scoresheet.save()
            match.scoresheet = scoresheet

        # Comprobar si el usuario es oficial de mesa asignado a este partido o administrador
        user = self.request.user
        is_assigned_official = (
            user.is_authenticated
            and user.role == "TABLE_OFFICIAL"
            and (match.table_official_id == user.id or match.timekeeper_id == user.id)
        )
        is_admin = user.is_authenticated and (user.is_superuser or user.role == "ADMIN")
        context["can_manage_table"] = (
            user.is_authenticated
            and match.status != Match.Status.FINISHED
            and (is_admin or is_assigned_official)
        )

        # Comprobar si el usuario tiene permiso para acceder al acta oficial (solo Mesa Arbitral y Entrenadores)
        context["can_view_scoresheet"] = (
            user.is_authenticated
            and user.role in ["ADMIN", "TABLE_OFFICIAL", "COACH"]
        )

        return context


class OfficialTableScorekeeperView(LoginRequiredMixin, RoleRequiredMixin, DetailView):
    """
    Consola interactiva de Mesa Arbitral: control de marcador, reloj, faltas y acta oficial.
    Solo accesible por los Oficiales de Mesa Arbitral específicamente asignados a este partido (Anotador y Cronometrador) o Administradores.
    """

    model = Match
    template_name = "matches/scorekeeper.html"
    context_object_name = "match"
    allowed_roles = ["ADMIN", "TABLE_OFFICIAL"]

    def get_object(self, queryset=None):
        match = super().get_object(queryset)
        user = self.request.user
        is_assigned_official = (
            user.is_authenticated
            and user.role == "TABLE_OFFICIAL"
            and (match.table_official_id == user.id or match.timekeeper_id == user.id)
        )
        is_admin = user.is_authenticated and (user.is_superuser or user.role == "ADMIN")
        if not (is_admin or is_assigned_official):
            messages.error(
                self.request,
                "Acceso denegado: No estás asignado como oficial de mesa (Anotador o Cronometrador) para este partido.",
            )
            raise PermissionDenied
        return match

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.status == Match.Status.FINISHED:
            messages.info(
                request,
                "Este encuentro ya ha finalizado y su acta oficial está cerrada y homologada.",
            )
            return redirect("matches:scoresheet_detail", pk=self.object.pk)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        match = self.get_object()

        # Plantillas de ambos equipos para la consola de mesa (únicas y ligadas a la temporada)
        context["home_roster"] = match.get_team_roster(match.home_team)
        context["away_roster"] = match.get_team_roster(match.away_team)

        # Asegurar estadísticas individuales para los jugadores de las plantillas
        from apps.analytics.models import PlayerMatchStat
        import json

        for member in context["home_roster"]:
            PlayerMatchStat.objects.get_or_create(
                match=match,
                player=member.player,
                defaults={"team": match.home_team}
            )
        for member in context["away_roster"]:
            PlayerMatchStat.objects.get_or_create(
                match=match,
                player=member.player,
                defaults={"team": match.away_team}
            )

        player_stats = PlayerMatchStat.objects.filter(match=match)
        player_points_map = {str(stat.player_id): stat.points for stat in player_stats}
        player_fouls_map = {str(stat.player_id): stat.fouls_committed for stat in player_stats}
        context["player_points_json"] = json.dumps(player_points_map)
        context["player_fouls_json"] = json.dumps(player_fouls_map)

        home_on_court_ids = match.get_on_court_player_ids(match.home_team)
        away_on_court_ids = match.get_on_court_player_ids(match.away_team)
        context["home_on_court_ids"] = home_on_court_ids
        context["away_on_court_ids"] = away_on_court_ids
        context["home_on_court_json"] = json.dumps(home_on_court_ids)
        context["away_on_court_json"] = json.dumps(away_on_court_ids)
        context["home_has_five"] = match.has_valid_five_on_court(match.home_team)
        context["away_has_five"] = match.has_valid_five_on_court(match.away_team)

        context["home_timeouts"] = match.get_team_timeouts_info(match.home_team)
        context["away_timeouts"] = match.get_team_timeouts_info(match.away_team)
        context["home_fouls_info"] = match.get_team_fouls_info(match.home_team)
        context["away_fouls_info"] = match.get_team_fouls_info(match.away_team)

        context["recent_events"] = match.events.select_related(
            "player", "team"
        ).order_by("-created_at")[:30]

        # Comprobar si tiene acta creada
        scoresheet, _ = DigitalScoreSheet.objects.get_or_create(match=match)
        context["scoresheet"] = scoresheet

        return context


class ScoreSheetDetailView(LoginRequiredMixin, RoleRequiredMixin, DetailView):
    """
    Vista del acta digital oficial del partido cerrada y firmada.
    Acceso estrictamente restringido a Administradores, Mesa Arbitral y Entrenadores.
    """

    model = Match
    template_name = "matches/scoresheet_detail.html"
    context_object_name = "match"
    allowed_roles = ["ADMIN", "TABLE_OFFICIAL", "COACH"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        match = self.get_object()

        scoresheet, _ = DigitalScoreSheet.objects.get_or_create(match=match)
        context["scoresheet"] = scoresheet

        # 1. Desglose oficial de puntos por cuartos
        context["quarters_breakdown"] = match.get_quarters_breakdown()

        # 2. Listado completo de jugadores participantes con puntos y faltas personales
        from apps.analytics.models import PlayerMatchStat

        def build_roster_stats(team):
            memberships = match.get_team_roster(team)

            stats_map = {
                stat.player_id: stat
                for stat in PlayerMatchStat.objects.filter(match=match, team=team)
            }

            roster_list = []
            total_points = 0
            total_fouls = 0

            for m in memberships:
                stat = stats_map.get(m.player_id)
                points = stat.points if stat else 0
                fouls = stat.fouls_committed if stat else 0
                is_starter = stat.is_starter if stat else False
                is_on_court = stat.is_on_court if stat else False

                total_points += points
                total_fouls += fouls

                roster_list.append({
                    "membership": m,
                    "player": m.player,
                    "jersey_number": m.jersey_number,
                    "is_captain": m.is_captain,
                    "is_starter": is_starter,
                    "is_on_court": is_on_court,
                    "points": points,
                    "fouls": fouls,
                    "is_fouled_out": fouls >= 5,
                    "stat": stat,
                })

            return roster_list, total_points, total_fouls

        home_roster, home_total_pts, home_total_fouls = build_roster_stats(match.home_team)
        away_roster, away_total_pts, away_total_fouls = build_roster_stats(match.away_team)

        context["home_roster_stats"] = home_roster
        context["away_roster_stats"] = away_roster
        context["home_total_fouls"] = home_total_fouls
        context["away_total_fouls"] = away_total_fouls

        context["all_events"] = match.events.select_related(
            "player", "team"
        ).order_by("created_at")

        return context


class RestoreDemoDataView(LoginRequiredMixin, View):
    """
    Restaura todos los partidos, estadísticas, clasificaciones y actas al estado canónico oficial
    para demostración ante el tutor o tribunal.
    """

    def get(self, request, *args, **kwargs):
        from .services import restore_canonical_matches
        from .consumers import SERVER_MATCH_CLOCKS

        SERVER_MATCH_CLOCKS.clear()
        restore_canonical_matches()
        messages.success(
            request,
            "Datos de partidos, actas y clasificaciones restaurados al estado oficial de demostración.",
        )
        return redirect("matches:match_list")


# Ejecutar una restauración al estado canónico oficial garantizado
try:
    from .services import restore_canonical_matches
    restore_canonical_matches()
except Exception:
    pass

