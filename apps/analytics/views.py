from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404
from django.views.generic import TemplateView, View

from .models import Standing, PlayerMatchStat
from .services import (
    get_league_leaders,
    compare_teams_head_to_head,
    compare_players_head_to_head,
)
from apps.teams.models import Team, Player, Season, League


class AnalyticsDashboardView(LoginRequiredMixin, TemplateView):
    """
    Panel central de analítica y estadísticas avanzadas de Quinto Cuarto.
    """

    template_name = "analytics/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        season = Season.objects.filter(is_current=True).first()
        if not season:
            season = Season.objects.first()

        context["season"] = season
        context["leaders"] = get_league_leaders(season=season, limit=4)
        context["top_teams"] = Standing.objects.filter(season=season).select_related("team")[:5] if season else []
        context["all_teams"] = Team.objects.all().order_by("name")
        context["all_players"] = Player.objects.filter(is_active=True).order_by("last_name")

        return context


class LeadersListView(LoginRequiredMixin, TemplateView):
    """
    Tablas completas de líderes estadísticos (Anotación, Valoración PIR, Asistencias, Rebotes).
    """

    template_name = "analytics/leaders.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        season_id = self.request.GET.get("season")
        
        if season_id:
            season = Season.objects.filter(id=season_id).first()
        else:
            season = Season.objects.filter(is_current=True).first() or Season.objects.first()

        context["current_season"] = season
        context["all_seasons"] = Season.objects.all().order_by("-start_date")
        context["leaders"] = get_league_leaders(season=season, limit=10)

        return context


class TeamComparatorView(LoginRequiredMixin, View):
    """
    Comparador visual cara a cara (Head-to-Head) entre dos clubes.
    """

    template_name = "analytics/compare_teams.html"

    def get(self, request, *args, **kwargs):
        all_teams = Team.objects.all().order_by("name")
        
        team_a_slug = request.GET.get("team_a")
        team_b_slug = request.GET.get("team_b")

        team_a = Team.objects.filter(slug=team_a_slug).first() if team_a_slug else all_teams.first()
        
        # Seleccionar segundo equipo distinto por defecto
        if team_b_slug:
            team_b = Team.objects.filter(slug=team_b_slug).first()
        else:
            team_b = all_teams.exclude(id=team_a.id).first() if team_a else None

        comparison_data = None
        if team_a and team_b:
            comparison_data = compare_teams_head_to_head(team_a, team_b)

        return render(
            request,
            self.template_name,
            {
                "all_teams": all_teams,
                "team_a": team_a,
                "team_b": team_b,
                "comparison": comparison_data,
            },
        )


class PlayerComparatorView(LoginRequiredMixin, View):
    """
    Comparador visual de métricas y rendimiento entre dos atletas.
    """

    template_name = "analytics/compare_players.html"

    def get(self, request, *args, **kwargs):
        all_players = Player.objects.filter(is_active=True).order_by("last_name")

        player_a_id = request.GET.get("player_a")
        player_b_id = request.GET.get("player_b")

        player_a = Player.objects.filter(id=player_a_id).first() if player_a_id else all_players.first()
        
        if player_b_id:
            player_b = Player.objects.filter(id=player_b_id).first()
        else:
            player_b = all_players.exclude(id=player_a.id).first() if player_a else None

        comparison_data = None
        if player_a and player_b:
            comparison_data = compare_players_head_to_head(player_a, player_b)

        return render(
            request,
            self.template_name,
            {
                "all_players": all_players,
                "player_a": player_a,
                "player_b": player_b,
                "comparison": comparison_data,
            },
        )
