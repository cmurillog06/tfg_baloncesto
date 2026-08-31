from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.db.models import Prefetch
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, View

from .models import League, Season, Team, Player, TeamMembership
from apps.analytics.models import Standing
from .forms import TeamMembershipForm
from apps.matches.models import Match
from apps.accounts.permissions import RoleRequiredMixin


class LeagueListView(LoginRequiredMixin, ListView):
    """
    Lista de todas las ligas federadas activas en la plataforma.
    Requiere que el usuario haya iniciado sesión.
    """

    model = League
    template_name = "teams/league_list.html"
    context_object_name = "leagues"

    def get_queryset(self):
        return League.objects.filter(is_active=True).prefetch_related("seasons")


class LeagueDetailView(LoginRequiredMixin, DetailView):
    """
    Vista detallada de una liga: clasificación oficial y calendario de partidos.
    Requiere que el usuario haya iniciado sesión.
    """

    model = League
    template_name = "teams/league_detail.html"
    context_object_name = "league"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        league = self.get_object()

        # Obtener temporada activa
        season = league.seasons.filter(is_current=True).first()
        if not season:
            season = league.seasons.first()

        context["active_season"] = season

        if season:
            # Clasificación ordenada por puntos y diferencia
            context["standings"] = Standing.objects.filter(
                season=season
            ).select_related("team").order_by("-league_points", "-points_diff", "-points_for")

            # Partidos de la temporada agrupados por jornada y fecha
            context["matches"] = Match.objects.filter(
                season=season
            ).select_related("home_team", "away_team").order_by("round_number", "scheduled_at")

        return context


class TeamListView(LoginRequiredMixin, ListView):
    """
    Directorio de clubes de baloncesto registrados.
    Requiere que el usuario haya iniciado sesión.
    """

    model = Team
    template_name = "teams/team_list.html"
    context_object_name = "teams"

    def get_queryset(self):
        return Team.objects.select_related("coach").prefetch_related("roster_memberships")


class TeamDetailView(LoginRequiredMixin, DetailView):
    """
    Ficha oficial de un equipo y su plantilla activa actual.
    Requiere que el usuario haya iniciado sesión.
    """

    model = Team
    template_name = "teams/team_detail.html"
    context_object_name = "team"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        team = self.get_object()

        # Plantilla activa ordenada por dorsal
        memberships = TeamMembership.objects.filter(
            team=team,
            is_active=True
        ).select_related("player").order_by("jersey_number")

        context["memberships"] = memberships

        # Comprobar si el usuario actual es entrenador de este equipo o administrador
        user = self.request.user
        context["can_manage_roster"] = (
            user.is_authenticated and (
                user.is_superuser or
                user.role == "ADMIN" or
                (user.role == "COACH" and team.coach == user)
            )
        )

        return context


class PlayerDetailView(LoginRequiredMixin, DetailView):
    """
    Pasaporte deportivo / Ficha individual de un atleta.
    Requiere que el usuario haya iniciado sesión.
    """

    model = Player
    template_name = "teams/player_detail.html"
    context_object_name = "player"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        player = self.get_object()

        # Historial de equipos del jugador
        context["history"] = TeamMembership.objects.filter(
            player=player
        ).select_related("team", "season").order_by("-season__start_date", "-is_active")

        # Equipo actual activo
        context["current_membership"] = TeamMembership.objects.filter(
            player=player,
            is_active=True
        ).select_related("team", "season").first()

        return context


class CoachRosterManageView(LoginRequiredMixin, RoleRequiredMixin, View):
    """
    Panel de gestión de plantilla para entrenadores: Altas, Bajas y Asignación de Dorsales.
    Solo accesible por el entrenador asignado al equipo o administradores.
    """

    allowed_roles = ["COACH", "ADMIN"]
    template_name = "teams/roster_manage.html"

    def dispatch(self, request, *args, **kwargs):
        self.team = get_object_or_404(Team, slug=kwargs.get("slug"))
        user = request.user

        # Verificar que sea el entrenador de este equipo o un administrador
        if not (user.is_superuser or user.role == "ADMIN" or self.team.coach == user):
            messages.error(request, "No tienes permisos para gestionar la plantilla de este equipo.")
            raise PermissionDenied

        # Obtener temporada activa
        self.season = Season.objects.filter(is_current=True).first()
        if not self.season:
            self.season = Season.objects.first()

        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        form = TeamMembershipForm(team=self.team, season=self.season)
        active_memberships = TeamMembership.objects.filter(
            team=self.team,
            season=self.season,
            is_active=True
        ).select_related("player").order_by("jersey_number")

        return render(
            request,
            self.template_name,
            {
                "team": self.team,
                "season": self.season,
                "form": form,
                "active_memberships": active_memberships,
            },
        )

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")

        # 1. Dar de baja a un jugador de la plantilla activa
        if action == "deactivate":
            membership_id = request.POST.get("membership_id")
            membership = get_object_or_404(
                TeamMembership,
                id=membership_id,
                team=self.team
            )
            player_name = membership.player.full_name
            membership.is_active = False
            membership.save()
            messages.success(request, f"{player_name} ha sido dado de baja de la plantilla activa.")
            return redirect("teams:roster_manage", slug=self.team.slug)

        # 2. Inscribir / Dar de alta a un jugador
        form = TeamMembershipForm(request.POST, team=self.team, season=self.season)
        if form.is_valid():
            player = form.cleaned_data["player"]
            jersey_number = form.cleaned_data["jersey_number"]
            is_captain = form.cleaned_data.get("is_captain", False)

            # Comprobar si ya existe un registro histórico para este jugador en este equipo y temporada
            existing_membership = TeamMembership.objects.filter(
                team=self.team,
                season=self.season,
                player=player
            ).first()

            # Comprobar si el dorsal ya está ocupado por otro jugador ACTIVO
            dorsal_busy = TeamMembership.objects.filter(
                team=self.team,
                season=self.season,
                jersey_number=jersey_number,
                is_active=True
            ).exclude(player=player).exists()

            if dorsal_busy:
                messages.error(request, f"El dorsal #{jersey_number} ya está en uso por otro jugador activo en la plantilla.")
                return redirect("teams:roster_manage", slug=self.team.slug)

            if existing_membership:
                # Reactivar membresía existente
                existing_membership.jersey_number = jersey_number
                existing_membership.is_captain = is_captain
                existing_membership.is_active = True
                existing_membership.save()
            else:
                membership = form.save(commit=False)
                membership.team = self.team
                membership.season = self.season
                membership.is_active = True
                membership.save()

            messages.success(request, f"{player.full_name} ha sido inscrito en la plantilla con el dorsal #{jersey_number}.")
            return redirect("teams:roster_manage", slug=self.team.slug)

        active_memberships = TeamMembership.objects.filter(
            team=self.team,
            season=self.season,
            is_active=True
        ).select_related("player").order_by("jersey_number")

        return render(
            request,
            self.template_name,
            {
                "team": self.team,
                "season": self.season,
                "form": form,
                "active_memberships": active_memberships,
            },
        )
