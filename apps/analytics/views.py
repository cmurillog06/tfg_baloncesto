from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404
from django.views.generic import TemplateView, View

from .models import Standing, PlayerMatchStat
from .services import (
    get_league_leaders,
    compare_teams_head_to_head,
    compare_players_head_to_head,
    predictive_matchup_model,
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
        context["all_players"] = (
            Player.objects.filter(is_active=True)
            .prefetch_related("team_memberships__team", "team_memberships__season")
            .order_by("last_name")
        )

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
        context["all_seasons"] = Season.objects.filter(is_current=True).select_related("league").order_by("league__name")
        context["leaders"] = get_league_leaders(season=season, limit=5)

        return context


class TeamComparatorView(LoginRequiredMixin, View):
    """
    Comparador visual cara a cara (Head-to-Head) entre dos clubes dentro de una misma competición.
    """

    template_name = "analytics/compare_teams.html"

    def get(self, request, *args, **kwargs):
        from django.db.models import Q

        all_seasons = Season.objects.filter(is_current=True).select_related("league").order_by("league__name")
        season_id = request.GET.get("season")

        if season_id:
            current_season = all_seasons.filter(id=season_id).first() or Season.objects.filter(id=season_id).first()
        else:
            current_season = all_seasons.first() or Season.objects.first()

        if current_season:
            teams = Team.objects.filter(
                Q(standings__season=current_season) |
                Q(home_matches__season=current_season) |
                Q(away_matches__season=current_season)
            ).distinct().order_by("name")
        else:
            teams = Team.objects.none()

        team_a_slug = request.GET.get("team_a")
        team_b_slug = request.GET.get("team_b")

        team_a = teams.filter(slug=team_a_slug).first() if team_a_slug else teams.first()

        other_teams = teams.exclude(id=team_a.id) if team_a else teams
        if team_b_slug and team_b_slug != (team_a.slug if team_a else None):
            team_b = other_teams.filter(slug=team_b_slug).first() or other_teams.first()
        else:
            team_b = other_teams.first()

        comparison_data = None
        if team_a and team_b:
            comparison_data = compare_teams_head_to_head(team_a, team_b, season=current_season)

        return render(
            request,
            self.template_name,
            {
                "all_seasons": all_seasons,
                "current_season": current_season,
                "teams": teams,
                "team_a": team_a,
                "team_b": team_b,
                "comparison": comparison_data,
            },
        )


class PlayerComparatorView(LoginRequiredMixin, View):
    """
    Comparador visual de métricas y rendimiento entre dos jugadores.
    """

    template_name = "analytics/compare_players.html"

    def get(self, request, *args, **kwargs):
        all_players = (
            Player.objects.filter(is_active=True)
            .prefetch_related("team_memberships__team", "team_memberships__season")
            .order_by("last_name")
        )

        player_a_id = request.GET.get("player_a")
        player_b_id = request.GET.get("player_b")

        player_a = all_players.filter(id=player_a_id).first() if player_a_id else all_players.first()

        other_players = all_players.exclude(id=player_a.id) if player_a else all_players
        if player_b_id and str(player_b_id) != str(player_a.id if player_a else ""):
            player_b = all_players.filter(id=player_b_id).first() or other_players.first()
        else:
            player_b = other_players.first()

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


class PredictiveModelView(LoginRequiredMixin, View):
    """
    Modelo Matemático Predictivo de Partidos y Demarcaciones Posicionales.
    Permite proyectar probabilidades de victoria y marcador final (Expectativa Pitagórica, Índices Posicionales, Diferencial Neto).
    """

    template_name = "analytics/predictive_model.html"

    def get(self, request, *args, **kwargs):
        from django.db.models import Q

        all_seasons = Season.objects.filter(is_current=True).select_related("league").order_by("league__name")
        season_id = request.GET.get("season")

        if season_id:
            current_season = all_seasons.filter(id=season_id).first() or Season.objects.filter(id=season_id).first()
        else:
            current_season = all_seasons.first() or Season.objects.first()

        if current_season:
            teams = Team.objects.filter(
                Q(standings__season=current_season) |
                Q(home_matches__season=current_season) |
                Q(away_matches__season=current_season)
            ).distinct().order_by("name")
        else:
            teams = Team.objects.none()

        team_a_slug = request.GET.get("team_a")
        team_b_slug = request.GET.get("team_b")

        team_a = teams.filter(slug=team_a_slug).first() if team_a_slug else teams.first()

        other_teams = teams.exclude(id=team_a.id) if team_a else teams
        if team_b_slug and team_b_slug != (team_a.slug if team_a else None):
            team_b = other_teams.filter(slug=team_b_slug).first() or other_teams.first()
        else:
            team_b = other_teams.first()

        # Parámetro matemático de ventaja de campo (Dean Oliver, 2004)
        try:
            hca = float(request.GET.get("hca", "3.5"))
        except (ValueError, TypeError):
            hca = 3.5

        prediction_data = None
        if team_a and team_b:
            prediction_data = predictive_matchup_model(
                team_a=team_a,
                team_b=team_b,
                season=current_season,
                home_court_advantage=hca,
            )

        return render(
            request,
            self.template_name,
            {
                "all_seasons": all_seasons,
                "current_season": current_season,
                "teams": teams,
                "team_a": team_a,
                "team_b": team_b,
                "hca": hca,
                "prediction": prediction_data,
            },
        )
