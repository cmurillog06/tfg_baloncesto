from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404
from django.views.generic import TemplateView, View
from django.db.models import Q

from .models import Standing, PlayerMatchStat
from .services import (
    get_league_leaders,
    compare_teams_head_to_head,
    compare_players_head_to_head,
    predictive_matchup_model,
)
from apps.teams.models import Team, Player, Season, League
from apps.matches.models import Match


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
        context["seasons"] = Season.objects.all().order_by("-start_date")
        context["selected_season"] = season
        context["leaders"] = get_league_leaders(season=season, limit=4)
        context["standings"] = (
            Standing.objects.filter(season=season)
            .select_related("team")
            .order_by("-league_points", "-points_diff", "-points_for")
            if season
            else []
        )
        context["top_teams"] = context["standings"][:5]
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

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        all_seasons = Season.objects.filter(is_current=True).select_related("league").order_by("league__name")
        season_val = request.POST.get("season") or request.GET.get("season")

        if season_val:
            if str(season_val).isdigit():
                current_season = Season.objects.filter(id=int(season_val)).first()
            else:
                current_season = Season.objects.filter(name=season_val).first()
        else:
            current_season = all_seasons.first() or Season.objects.first()

        if current_season:
            season_teams = Team.objects.filter(
                Q(standings__season=current_season)
                | Q(home_matches__season=current_season)
                | Q(away_matches__season=current_season)
            ).distinct().order_by("name")
            teams = season_teams if season_teams.exists() else Team.objects.all().order_by("name")
        else:
            teams = Team.objects.all().order_by("name")

        team_a_val = request.POST.get("team_a") or request.GET.get("team_a")
        team_b_val = request.POST.get("team_b") or request.GET.get("team_b")

        team_a = None
        if team_a_val:
            if str(team_a_val).isdigit():
                team_a = Team.objects.filter(id=int(team_a_val)).first()
            else:
                team_a = Team.objects.filter(slug=team_a_val).first()
        if not team_a:
            team_a = teams.first()

        other_teams = teams.exclude(id=team_a.id) if team_a else teams

        team_b = None
        if team_b_val:
            if str(team_b_val).isdigit():
                team_b = Team.objects.filter(id=int(team_b_val)).first()
            else:
                team_b = Team.objects.filter(slug=team_b_val).first()
        if not team_b or (team_a and team_b.id == team_a.id):
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

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        all_players = (
            Player.objects.filter(is_active=True)
            .prefetch_related("team_memberships__team", "team_memberships__season")
            .order_by("last_name")
        )

        player_a_val = request.POST.get("player_a") or request.GET.get("player_a")
        player_b_val = request.POST.get("player_b") or request.GET.get("player_b")

        player_a = None
        if player_a_val:
            if str(player_a_val).isdigit():
                player_a = all_players.filter(id=int(player_a_val)).first()
            else:
                player_a = all_players.filter(slug=player_a_val).first()
        if not player_a:
            player_a = all_players.first()

        other_players = all_players.exclude(id=player_a.id) if player_a else all_players

        player_b = None
        if player_b_val:
            if str(player_b_val).isdigit():
                player_b = all_players.filter(id=int(player_b_val)).first()
            else:
                player_b = all_players.filter(slug=player_b_val).first()
        if not player_b or (player_a and player_b.id == player_a.id):
            player_b = other_players.first()

        comparison_data = None
        if player_a and player_b:
            comparison_data = compare_players_head_to_head(player_a, player_b)

        return render(
            request,
            self.template_name,
            {
                "players": all_players,
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

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        all_seasons = Season.objects.filter(is_current=True).select_related("league").order_by("league__name")
        season_val = request.POST.get("season") or request.GET.get("season")

        if season_val:
            if str(season_val).isdigit():
                current_season = Season.objects.filter(id=int(season_val)).first()
            else:
                current_season = Season.objects.filter(name=season_val).first()
        else:
            current_season = all_seasons.first() or Season.objects.first()

        if current_season:
            season_teams = Team.objects.filter(
                Q(standings__season=current_season)
                | Q(home_matches__season=current_season)
                | Q(away_matches__season=current_season)
            ).distinct().order_by("name")
            teams = season_teams if season_teams.exists() else Team.objects.all().order_by("name")
        else:
            teams = Team.objects.all().order_by("name")

        team_a_val = request.POST.get("team_a") or request.GET.get("team_a")
        team_b_val = request.POST.get("team_b") or request.GET.get("team_b")

        team_a = None
        if team_a_val:
            if str(team_a_val).isdigit():
                team_a = Team.objects.filter(id=int(team_a_val)).first()
            else:
                team_a = Team.objects.filter(slug=team_a_val).first()
        if not team_a:
            team_a = teams.first()

        other_teams = teams.exclude(id=team_a.id) if team_a else teams

        team_b = None
        if team_b_val:
            if str(team_b_val).isdigit():
                team_b = Team.objects.filter(id=int(team_b_val)).first()
            else:
                team_b = Team.objects.filter(slug=team_b_val).first()
        if not team_b or (team_a and team_b.id == team_a.id):
            team_b = other_teams.first()

        # Parámetro matemático de ventaja de campo (Dean Oliver, 2004)
        try:
            hca_input = request.POST.get("hca") or request.GET.get("hca", "3.5")
            hca = float(hca_input)
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

        matches_qs = Match.objects.filter(
            season=current_season, status=Match.Status.SCHEDULED
        ).select_related("home_team", "away_team").order_by("scheduled_at") if current_season else Match.objects.none()

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
                "matches": matches_qs,
                "scheduled_matches": matches_qs,
            },
        )
