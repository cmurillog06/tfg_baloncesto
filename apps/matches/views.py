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

        # Eventos recientes
        context["recent_events"] = match.events.select_related(
            "player", "team"
        ).order_by("-created_at")[:25]

        # Comprobar si el usuario es oficial de mesa o admin para mostrar botón de mesa
        user = self.request.user
        context["can_manage_table"] = (
            user.is_authenticated
            and (
                user.is_superuser
                or user.role in ["ADMIN", "TABLE_OFFICIAL"]
                or match.table_official == user
            )
        )

        # Comprobar si el usuario tiene permiso para acceder al acta oficial
        context["can_view_scoresheet"] = (
            user.is_authenticated
            and (user.is_superuser or user.role in ["ADMIN", "TABLE_OFFICIAL", "COACH"])
        )

        return context


class OfficialTableScorekeeperView(LoginRequiredMixin, RoleRequiredMixin, DetailView):
    """
    Consola interactiva de Mesa Arbitral: control de marcador, reloj, faltas y acta oficial.
    Solo accesible por Oficiales de Mesa y Administradores.
    """

    model = Match
    template_name = "matches/scorekeeper.html"
    context_object_name = "match"
    allowed_roles = ["ADMIN", "TABLE_OFFICIAL"]

    def get_object(self, queryset=None):
        match = super().get_object(queryset)
        user = self.request.user
        if not (user.is_superuser or user.role == "ADMIN" or match.table_official == user or user.role == "TABLE_OFFICIAL"):
            messages.error(self.request, "Solo la mesa arbitral asignada o un administrador pueden acceder a la consola.")
            raise PermissionDenied
        return match

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
    Acceso restringido a Mesa Arbitral, Entrenadores y Administradores.
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
