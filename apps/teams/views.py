from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.db.models import Prefetch
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, View

from .models import League, Season, Team, Player, TeamMembership
from apps.analytics.models import Standing
from .forms import TeamMembershipForm, CoachPlayerCreateForm, CoachPlayerEditForm
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
            season = league.seasons.first() or Season.objects.filter(league=league).first()

        context["active_season"] = season
        context["season"] = season
        context["standings"] = []
        context["matches"] = []

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

        # Obtener temporada oficial activa
        from apps.teams.models import Season
        current_season = Season.objects.filter(is_current=True).first()
        if not current_season:
            current_season = Season.objects.order_by("-start_date").first()

        # Plantilla activa de la temporada actual ordenada por dorsal
        memberships_qs = TeamMembership.objects.filter(
            team=team,
            is_active=True
        )
        if current_season:
            memberships_qs = memberships_qs.filter(season=current_season)

        context["memberships"] = memberships_qs.select_related("player", "season").order_by("jersey_number")
        context["current_season"] = current_season

        # Comprobar si el usuario actual es estrictamente el entrenador asignado a este equipo
        user = self.request.user
        context["can_manage_roster"] = (
            user.is_authenticated and user.role == "COACH" and team.coach == user
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

        # Historial de membresías
        memberships = TeamMembership.objects.filter(
            player=player
        ).select_related("team", "season", "season__league").order_by("-season__start_date", "-is_active")
        context["memberships"] = memberships

        # Equipo actual activo
        current_membership = memberships.filter(is_active=True).first()
        context["current_membership"] = current_membership

        # Estadísticas agregadas del jugador en partidos oficiales finalizados donde disputó minutos
        from apps.analytics.models import PlayerMatchStat
        from django.db.models import Avg, Sum, F

        base_stats = PlayerMatchStat.objects.filter(
            player=player,
            match__status="FINISHED",
            minutes_played__gt=0
        )
        
        # Obtener competiciones/temporadas donde el jugador tiene partidos disputados
        player_season_ids = base_stats.values_list("match__season_id", flat=True).distinct()
        available_seasons = Season.objects.filter(id__in=player_season_ids).select_related("league").order_by("league__name")
        context["available_seasons"] = available_seasons

        season_id = self.request.GET.get("season")
        selected_season = available_seasons.filter(id=season_id).first() if season_id else None
        context["selected_season"] = selected_season

        # Filtrar estadísticas para el bloque principal
        stats = base_stats.filter(match__season=selected_season) if selected_season else base_stats
        games_played = stats.count()
        if games_played > 0:
            agg = stats.aggregate(
                avg_pts=Avg("points"),
                avg_reb_off=Avg("rebounds_off"),
                avg_reb_def=Avg("rebounds_def"),
                avg_ast=Avg("assists"),
                avg_pir=Avg("valuation_pir"),
                avg_min=Avg("minutes_played"),
                total_pts=Sum("points"),
            )
            avg_reb = round((agg["avg_reb_off"] or 0) + (agg["avg_reb_def"] or 0), 1)
            context["stats_summary"] = {
                "games_played": games_played,
                "avg_points": round(agg["avg_pts"] or 0, 1),
                "avg_rebounds": avg_reb,
                "avg_assists": round(agg["avg_ast"] or 0, 1),
                "avg_pir": round(agg["avg_pir"] or 0, 1),
                "avg_minutes": round(agg["avg_min"] or 0, 1),
                "total_points": agg["total_pts"] or 0,
            }
        else:
            context["stats_summary"] = None

        # Desglose estadístico individual por cada competición
        competition_breakdown = []
        for s in available_seasons:
            s_stats = base_stats.filter(match__season=s)
            s_games = s_stats.count()
            if s_games > 0:
                s_agg = s_stats.aggregate(
                    avg_pts=Avg("points"),
                    avg_reb_off=Avg("rebounds_off"),
                    avg_reb_def=Avg("rebounds_def"),
                    avg_ast=Avg("assists"),
                    avg_pir=Avg("valuation_pir"),
                    avg_min=Avg("minutes_played"),
                    total_pts=Sum("points"),
                )
                competition_breakdown.append({
                    "season": s,
                    "games_played": s_games,
                    "total_points": s_agg["total_pts"] or 0,
                    "avg_points": round(s_agg["avg_pts"] or 0, 1),
                    "avg_rebounds": round((s_agg["avg_reb_off"] or 0) + (s_agg["avg_reb_def"] or 0), 1),
                    "avg_assists": round(s_agg["avg_ast"] or 0, 1),
                    "avg_pir": round(s_agg["avg_pir"] or 0, 1),
                    "avg_minutes": round(s_agg["avg_min"] or 0, 1),
                })
        context["competition_breakdown"] = competition_breakdown

        return context


class CoachRosterManageView(LoginRequiredMixin, RoleRequiredMixin, View):
    """
    Panel de gestión de plantilla para entrenadores: Altas, Bajas y Asignación de Dorsales.
    Solo accesible por el entrenador oficial asignado a este equipo o administradores.
    """

    allowed_roles = ["COACH", "ADMIN"]
    template_name = "teams/roster_manage.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        self.team = get_object_or_404(Team, slug=kwargs.get("slug"))
        user = request.user

        # Verificar que sea estrictamente el entrenador oficial asignado a este equipo o administrador
        is_admin = user.is_superuser or getattr(user, "role", None) == "ADMIN"
        is_coach = getattr(user, "role", None) == "COACH" and self.team.coach == user
        if not (is_admin or is_coach):
            messages.error(request, "Solo el entrenador oficial asignado a este club puede gestionar su plantilla.")
            raise PermissionDenied

        # Obtener temporada activa
        self.season = (
            Season.objects.filter(is_current=True).first()
            or Season.objects.order_by("-start_date").first()
            or Season.objects.first()
        )
        if not self.season:
            import datetime
            league = League.objects.first()
            if not league:
                league = League.objects.create(
                    name="Liga Principal", slug="liga-principal"
                )
            self.season = Season.objects.create(
                league=league,
                name="Temporada Actual",
                start_date=datetime.date.today() - datetime.timedelta(days=30),
                end_date=datetime.date.today() + datetime.timedelta(days=180),
                is_current=True,
            )

        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        membership_form = TeamMembershipForm(team=self.team, season=self.season)
        player_create_form = CoachPlayerCreateForm(team=self.team, season=self.season)
        memberships = TeamMembership.objects.filter(
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
                "current_season": self.season,
                "form": membership_form,
                "membership_form": membership_form,
                "player_create_form": player_create_form,
                "memberships": memberships,
                "active_memberships": memberships,
            },
        )

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")

        # 1. Dar de baja a un jugador de la plantilla activa
        if action in ["deactivate", "remove_membership", "deactivate_member"]:
            membership_id = request.POST.get("membership_id")
            player_id = request.POST.get("player_id")
            if membership_id:
                membership = get_object_or_404(TeamMembership, id=membership_id, team=self.team)
            elif player_id:
                membership = get_object_or_404(TeamMembership, player_id=player_id, team=self.team)
            else:
                membership = None

            if membership:
                player_name = membership.player.full_name
                membership.is_active = False
                membership.save()
                messages.success(request, f"{player_name} ha sido dado de baja de la plantilla activa.")
            return redirect("teams:roster_manage", slug=self.team.slug)

        # 2. Conmutar capitanía de un jugador
        elif action == "toggle_captain":
            membership_id = request.POST.get("membership_id")
            player_id = request.POST.get("player_id")
            if membership_id:
                membership = get_object_or_404(TeamMembership, id=membership_id, team=self.team)
            elif player_id:
                membership = get_object_or_404(TeamMembership, player_id=player_id, team=self.team)
            else:
                membership = None

            if membership:
                membership.is_captain = not membership.is_captain
                membership.save()
                messages.success(request, f"Capitanía de {membership.player.full_name} actualizada.")
            return redirect("teams:roster_manage", slug=self.team.slug)

        # 3. Crear un jugador nuevo directamente desde el panel del entrenador
        elif action == "create_player":
            create_form = CoachPlayerCreateForm(
                request.POST, request.FILES, team=self.team, season=self.season
            )
            if create_form.is_valid():
                player = create_form.save()
                jersey_number = create_form.cleaned_data["jersey_number"]
                is_captain = create_form.cleaned_data.get("is_captain", False)

                TeamMembership.objects.create(
                    team=self.team,
                    player=player,
                    season=self.season,
                    jersey_number=jersey_number,
                    is_captain=is_captain,
                    is_active=True,
                )
                messages.success(
                    request,
                    f"¡Jugador {player.full_name} añadido con éxito con el dorsal #{jersey_number}!"
                )
                return redirect("teams:roster_manage", slug=self.team.slug)
            else:
                membership_form = TeamMembershipForm(team=self.team, season=self.season)
                memberships = TeamMembership.objects.filter(
                    team=self.team,
                    season=self.season,
                    is_active=True
                ).select_related("player").order_by("jersey_number")
                messages.error(request, "Por favor, corrige los errores en los datos del jugador.")
                return render(
                    request,
                    self.template_name,
                    {
                        "team": self.team,
                        "season": self.season,
                        "current_season": self.season,
                        "form": membership_form,
                        "membership_form": membership_form,
                        "player_create_form": create_form,
                        "memberships": memberships,
                        "active_memberships": memberships,
                        "active_tab": "new",
                    },
                    status=200,
                )

        # 4. Modificar datos biométricos, dorsal, posición o fotografía de un jugador existente
        elif action == "edit_player":
            membership_id = request.POST.get("membership_id")
            player_id = request.POST.get("player_id")
            if membership_id:
                membership = get_object_or_404(TeamMembership, id=membership_id, team=self.team)
            elif player_id:
                membership = TeamMembership.objects.filter(player_id=player_id, team=self.team).first()
                if not membership:
                    player = get_object_or_404(Player, id=player_id)
                    membership = TeamMembership.objects.create(
                        team=self.team,
                        player=player,
                        season=self.season,
                        jersey_number=int(request.POST.get("jersey_number", 0) or 0),
                    )
            else:
                membership = None

            if not membership:
                messages.error(request, "Jugador no encontrado.")
                return redirect("teams:roster_manage", slug=self.team.slug)

            player = membership.player
            edit_form = CoachPlayerEditForm(
                request.POST,
                request.FILES,
                instance=player,
                team=self.team,
                season=self.season,
                membership=membership,
            )
            if edit_form.is_valid():
                edit_form.save()
                membership.jersey_number = edit_form.cleaned_data["jersey_number"]
                membership.is_captain = edit_form.cleaned_data.get("is_captain", False)
                membership.save()
                messages.success(
                    request,
                    f"Datos biométricos y ficha de {player.full_name} actualizados correctamente.",
                )
                return redirect("teams:roster_manage", slug=self.team.slug)
            else:
                err_list = []
                for field, errs in edit_form.errors.items():
                    err_list.extend(errs)
                messages.error(request, "Error al actualizar: " + " ".join(err_list))
                membership_form = TeamMembershipForm(team=self.team, season=self.season)
                player_create_form = CoachPlayerCreateForm(team=self.team, season=self.season)
                memberships = TeamMembership.objects.filter(
                    team=self.team,
                    season=self.season,
                    is_active=True,
                ).select_related("player").order_by("jersey_number")
                return render(
                    request,
                    self.template_name,
                    {
                        "team": self.team,
                        "season": self.season,
                        "current_season": self.season,
                        "form": membership_form,
                        "membership_form": membership_form,
                        "player_create_form": player_create_form,
                        "edit_form": edit_form,
                        "memberships": memberships,
                        "active_memberships": memberships,
                        "active_tab": "existing",
                    },
                    status=200,
                )

        # 5. Inscribir un jugador existente de la base de datos federada
        else:
            form = TeamMembershipForm(request.POST, team=self.team, season=self.season)
            if form.is_valid():
                player = form.cleaned_data["player"]
                jersey_number = form.cleaned_data["jersey_number"]
                is_captain = form.cleaned_data.get("is_captain", False)

                existing_membership = TeamMembership.objects.filter(
                    team=self.team,
                    season=self.season,
                    player=player
                ).first()

                active_in_other = TeamMembership.objects.filter(
                    season=self.season,
                    player=player,
                    is_active=True
                ).exclude(team=self.team).select_related("team").first()

                if active_in_other:
                    messages.error(
                        request,
                        f"{player.full_name} no puede ser inscrito porque ya tiene ficha activa en {active_in_other.team.name} para esta temporada."
                    )
                    return redirect("teams:roster_manage", slug=self.team.slug)

                dorsal_busy = TeamMembership.objects.filter(
                    team=self.team,
                    season=self.season,
                    jersey_number=jersey_number,
                    is_active=True
                ).exclude(player=player).exists()

                if dorsal_busy:
                    messages.error(
                        request,
                        f"El dorsal #{jersey_number} ya está en uso por otro jugador activo en la plantilla."
                    )
                    return redirect("teams:roster_manage", slug=self.team.slug)

                if existing_membership:
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

                messages.success(
                    request,
                    f"{player.full_name} ha sido inscrito en la plantilla con el dorsal #{jersey_number}."
                )
                return redirect("teams:roster_manage", slug=self.team.slug)

            memberships = TeamMembership.objects.filter(
                team=self.team,
                season=self.season,
                is_active=True
            ).select_related("player").order_by("jersey_number")
            player_create_form = CoachPlayerCreateForm(team=self.team, season=self.season)

            return render(
                request,
                self.template_name,
                {
                    "team": self.team,
                    "season": self.season,
                    "current_season": self.season,
                    "form": form,
                    "membership_form": form,
                    "player_create_form": player_create_form,
                    "memberships": memberships,
                    "active_memberships": memberships,
                    "active_tab": "existing",
                },
                status=200,
            )
