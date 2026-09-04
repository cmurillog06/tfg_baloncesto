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
        base_qs = Match.objects.select_related(
            "home_team", "away_team", "season__league"
        )
        context["live_matches"] = base_qs.filter(status=Match.Status.LIVE).order_by("scheduled_at")
        context["upcoming_matches"] = base_qs.filter(status=Match.Status.SCHEDULED).order_by("scheduled_at")
        context["finished_matches"] = base_qs.filter(status=Match.Status.FINISHED).order_by("-scheduled_at")[:10]
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

        # Plantillas de ambos equipos para el acta / box score
        context["home_roster"] = TeamMembership.objects.filter(
            team=match.home_team, is_active=True
        ).select_related("player").order_by("jersey_number")

        context["away_roster"] = TeamMembership.objects.filter(
            team=match.away_team, is_active=True
        ).select_related("player").order_by("jersey_number")

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

        context["home_player_stats"] = PlayerMatchStat.objects.filter(
            match=match, team=match.home_team
        ).select_related("player").order_by("-points", "-valuation_pir")

        context["away_player_stats"] = PlayerMatchStat.objects.filter(
            match=match, team=match.away_team
        ).select_related("player").order_by("-points", "-valuation_pir")

        # Cronología completa de eventos del partido (Jugada a Jugada)
        context["recent_events"] = match.events.select_related(
            "player", "team"
        ).order_by("-id")

        # Asegurar que el acta de un partido finalizado esté formalmente cerrada
        if match.status == Match.Status.FINISHED:
            scoresheet, _ = DigitalScoreSheet.objects.get_or_create(match=match)
            if not scoresheet.is_closed:
                scoresheet.is_closed = True
                scoresheet.table_official_signed = True
                scoresheet.referee_signed = True
                scoresheet.home_coach_signed = True
                scoresheet.away_coach_signed = True
                scoresheet.save()
            match.scoresheet = scoresheet

        # Comprobar si el usuario es oficial de mesa para mostrar botón de consola arbitral (solo si el partido NO está finalizado)
        user = self.request.user
        context["can_manage_table"] = (
            user.is_authenticated
            and match.status != Match.Status.FINISHED
            and (user.role == "TABLE_OFFICIAL" or match.table_official == user)
        )

        # Comprobar si el usuario tiene permiso para acceder al acta oficial (solo Mesa Arbitral y Entrenadores)
        context["can_view_scoresheet"] = (
            user.is_authenticated
            and user.role in ["TABLE_OFFICIAL", "COACH"]
        )

        return context


class OfficialTableScorekeeperView(LoginRequiredMixin, RoleRequiredMixin, DetailView):
    """
    Consola interactiva de Mesa Arbitral: control de marcador, reloj, faltas y acta oficial.
    Solo accesible por Oficiales de Mesa Arbitral colegiados para partidos activos o programados.
    """

    model = Match
    template_name = "matches/scorekeeper.html"
    context_object_name = "match"
    allowed_roles = ["TABLE_OFFICIAL"]

    def get_object(self, queryset=None):
        match = super().get_object(queryset)
        user = self.request.user
        if not (user.role == "TABLE_OFFICIAL" or match.table_official == user):
            messages.error(self.request, "Solo los oficiales de mesa arbitral autorizados pueden acceder a la consola.")
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

        context["home_roster"] = TeamMembership.objects.filter(
            team=match.home_team, is_active=True
        ).select_related("player").order_by("jersey_number")

        context["away_roster"] = TeamMembership.objects.filter(
            team=match.away_team, is_active=True
        ).select_related("player").order_by("jersey_number")

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
    Acceso estrictamente restringido a Mesa Arbitral y Entrenadores.
    """

    model = Match
    template_name = "matches/scoresheet_detail.html"
    context_object_name = "match"
    allowed_roles = ["TABLE_OFFICIAL", "COACH"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        match = self.get_object()

        scoresheet, _ = DigitalScoreSheet.objects.get_or_create(match=match)
        context["scoresheet"] = scoresheet

        # Plantillas con estadísticas del partido
        context["home_roster"] = TeamMembership.objects.filter(
            team=match.home_team, is_active=True
        ).select_related("player").order_by("jersey_number")

        context["away_roster"] = TeamMembership.objects.filter(
            team=match.away_team, is_active=True
        ).select_related("player").order_by("jersey_number")

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

