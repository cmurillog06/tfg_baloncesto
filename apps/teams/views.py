from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import ListView, DetailView, View

from .models import League, Season, Team, Player, TeamMembership
from .forms import TeamMembershipForm, PlayerForm, TeamForm
from apps.matches.models import Match
from apps.analytics.models import Standing
from apps.accounts.permissions import RoleRequiredMixin


class LeagueListView(ListView):
    """
    Lista pública de ligas y competiciones activas.
    """

    model = League
    template_name = "teams/league_list.html"
    context_object_name = "leagues"

    def get_queryset(self):
        return League.objects.filter(is_active=True).prefetch_related("seasons")


class LeagueDetailView(DetailView):
    """
    Vista detallada de una liga: clasificación, temporadas y calendario de jornadas.
    """

    model = League
    template_name = "teams/league_detail.html"
    context_object_name = "league"
    slug_field = "slug"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        league = self.get_object()

        # Obtener temporada activa o la más reciente
        season = (
            league.seasons.filter(is_current=True).first()
            or league.seasons.first()
        )
        context["current_season"] = season

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


class TeamListView(ListView):
    """
    Directorio de equipos federados con información de ciudad, pabellón y entrenador.
    """

    model = Team
    template_name = "teams/team_list.html"
    context_object_name = "teams"

    def get_queryset(self):
        return Team.objects.all().select_related("coach")


class TeamDetailView(DetailView):
    """
    Ficha de equipo: plantilla de jugadores con dorsales, cuerpo técnico, pabellón y próximos partidos.
    """

    model = Team
    template_name = "teams/team_detail.html"
    context_object_name = "team"
    slug_field = "slug"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        team = self.get_object()

        # Plantilla activa con jugadores y dorsales ordenados
        context["memberships"] = TeamMembership.objects.filter(
            team=team, is_active=True
        ).select_related("player", "season").order_by("jersey_number")

        # Partidos recientes y próximos del equipo
        context["upcoming_matches"] = (
            Match.objects.filter(home_team=team) | Match.objects.filter(away_team=team)
        ).filter(status__in=[Match.Status.SCHEDULED, Match.Status.LIVE]).select_related(
            "home_team", "away_team", "season__league"
        ).order_by("scheduled_at")[:5]

        # Verificar si el usuario autenticado es el entrenador del equipo o admin
        user = self.request.user
        context["can_manage_roster"] = (
            user.is_authenticated
            and (user == team.coach or user.is_superuser or user.role == "ADMIN")
        )

        return context


class PlayerDetailView(DetailView):
    """
    Ficha individual de jugador: biometría (altura, peso), posición FIBA, dorsal y equipos.
    """

    model = Player
    template_name = "teams/player_detail.html"
    context_object_name = "player"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        player = self.get_object()

        # Membresías históricas y actuales del jugador
        context["memberships"] = TeamMembership.objects.filter(
            player=player
        ).select_related("team", "season").order_by("-is_active", "-season__start_date")

        return context


class CoachRosterManageView(LoginRequiredMixin, RoleRequiredMixin, View):
    """
    Panel protegido para que un entrenador gestione las altas, bajas y dorsales de su plantilla.
    """

    allowed_roles = ["ADMIN", "COACH"]
    template_name = "teams/roster_manage.html"

    def get_team(self, slug):
        team = get_object_or_404(Team, slug=slug)
        user = self.request.user
        if not (user == team.coach or user.is_superuser or user.role == "ADMIN"):
            messages.error(
                self.request,
                "Solo el entrenador asignado o un administrador pueden gestionar esta plantilla.",
            )
            raise PermissionDenied
        return team

    def get_current_season(self):
        # Seleccionar temporada actual de la Liga Endesa ACB o la primera disponible
        return (
            Season.objects.filter(is_current=True, league__name__icontains="Endesa").first()
            or Season.objects.filter(is_current=True).first()
            or Season.objects.first()
        )

    def get(self, request, slug):
        team = self.get_team(slug)
        current_season = self.get_current_season()

        memberships = TeamMembership.objects.filter(
            team=team, is_active=True
        ).select_related("player", "season").order_by("jersey_number")

        form = TeamMembershipForm(team=team, season=current_season)
        player_form = PlayerForm()

        return render(
            request,
            self.template_name,
            {
                "team": team,
                "current_season": current_season,
                "memberships": memberships,
                "form": form,
                "player_form": player_form,
            },
        )

    def post(self, request, slug):
        team = self.get_team(slug)
        current_season = self.get_current_season()
        action = request.POST.get("action")

        # Acción: Inscribir jugador existente en plantilla
        if action == "add_membership":
            form = TeamMembershipForm(request.POST, team=team, season=current_season)
            if form.is_valid():
                player = form.cleaned_data["player"]
                jersey_number = form.cleaned_data["jersey_number"]
                is_captain = form.cleaned_data.get("is_captain", False)

                # 1. Comprobar si el dorsal ya está ocupado por otro jugador activo
                taken = TeamMembership.objects.filter(
                    team=team, season=current_season, jersey_number=jersey_number, is_active=True
                ).exclude(player=player).first()

                if taken:
                    messages.error(
                        request,
                        f"El dorsal #{jersey_number} ya está asignado a {taken.player.full_name} en esta plantilla.",
                    )
                    return redirect("teams:roster_manage", slug=team.slug)

                # 2. Si ya existía una ficha previa (inactiva o histórica) para este equipo y temporada, reactivarla
                existing_membership = TeamMembership.objects.filter(
                    team=team, season=current_season, player=player
                ).first()

                if existing_membership:
                    existing_membership.jersey_number = jersey_number
                    existing_membership.is_captain = is_captain
                    existing_membership.is_active = True
                    existing_membership.save()
                else:
                    TeamMembership.objects.create(
                        team=team,
                        season=current_season,
                        player=player,
                        jersey_number=jersey_number,
                        is_captain=is_captain,
                        is_active=True,
                    )

                messages.success(
                    request,
                    f"¡Jugador {player.full_name} inscrito con éxito en la plantilla (Dorsal #{jersey_number})!",
                )
                return redirect("teams:roster_manage", slug=team.slug)
            else:
                messages.error(
                    request, "Error al inscribir jugador. Comprueba que hayas seleccionado un jugador y un dorsal válido."
                )

        # Acción: Crear nuevo jugador desde cero e inscribirlo
        elif action == "create_player_and_add":
            player_form = PlayerForm(request.POST, request.FILES)
            jersey_number = request.POST.get("jersey_number")
            if player_form.is_valid() and jersey_number:
                jersey_num = int(jersey_number)

                # Verificar dorsal
                taken = TeamMembership.objects.filter(
                    team=team, season=current_season, jersey_number=jersey_num, is_active=True
                ).first()
                if taken:
                    messages.error(
                        request,
                        f"El dorsal #{jersey_num} ya está asignado a {taken.player.full_name}.",
                    )
                    return redirect("teams:roster_manage", slug=team.slug)

                player = player_form.save()
                TeamMembership.objects.create(
                    team=team,
                    player=player,
                    season=current_season,
                    jersey_number=jersey_num,
                    is_active=True,
                )
                messages.success(
                    request,
                    f"¡Nuevo jugador {player.full_name} creado e inscrito con éxito (Dorsal #{jersey_num})!",
                )
                return redirect("teams:roster_manage", slug=team.slug)
            else:
                messages.error(
                    request, "Error al crear jugador. Completa todos los campos obligatorios."
                )

        # Acción: Dar de baja de la plantilla
        elif action == "remove_membership":
            membership_id = request.POST.get("membership_id")
            membership = get_object_or_404(TeamMembership, id=membership_id, team=team)
            membership.is_active = False
            membership.save()
            messages.info(
                request,
                f"El jugador {membership.player.full_name} ha sido dado de baja de la plantilla activa.",
            )
            return redirect("teams:roster_manage", slug=team.slug)

        return redirect("teams:roster_manage", slug=team.slug)
