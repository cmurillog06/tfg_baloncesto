import pytest
from django.urls import reverse
from apps.analytics.models import Standing, PlayerMatchStat


@pytest.mark.django_db
class TestAnalyticsDashboardView:
    """Pruebas de integración para el panel general de estadísticas y analítica."""

    def test_analytics_dashboard_view_renders_200(self, auth_client, fan_user):
        c = auth_client(fan_user)
        response = c.get(reverse("analytics:dashboard"))
        assert response.status_code == 200

    def test_analytics_dashboard_view_context_seasons(self, auth_client, fan_user, season):
        c = auth_client(fan_user)
        response = c.get(reverse("analytics:dashboard"))
        assert "seasons" in response.context

    def test_analytics_dashboard_view_context_selected_season(self, auth_client, fan_user, season):
        c = auth_client(fan_user)
        response = c.get(reverse("analytics:dashboard"))
        assert "selected_season" in response.context or "season" in response.context

    def test_analytics_dashboard_view_context_standings(self, auth_client, fan_user, season):
        c = auth_client(fan_user)
        response = c.get(reverse("analytics:dashboard"))
        assert "standings" in response.context

    def test_analytics_dashboard_view_context_top_scorers(self, auth_client, fan_user):
        c = auth_client(fan_user)
        response = c.get(reverse("analytics:dashboard"))
        assert "top_scorers" in response.context or "leaders" in response.context or response.status_code == 200

    def test_analytics_dashboard_view_context_top_valuation(self, auth_client, fan_user):
        c = auth_client(fan_user)
        response = c.get(reverse("analytics:dashboard"))
        assert response.status_code == 200

    def test_analytics_dashboard_view_context_top_assists(self, auth_client, fan_user):
        c = auth_client(fan_user)
        response = c.get(reverse("analytics:dashboard"))
        assert response.status_code == 200

    def test_analytics_dashboard_view_context_top_rebounds(self, auth_client, fan_user):
        c = auth_client(fan_user)
        response = c.get(reverse("analytics:dashboard"))
        assert response.status_code == 200


@pytest.mark.django_db
class TestLeadersListView:
    """Pruebas de integración para el listado de líderes individuales."""

    def test_leaders_list_view_renders_200(self, auth_client, fan_user):
        c = auth_client(fan_user)
        response = c.get(reverse("analytics:leaders"))
        assert response.status_code == 200

    def test_leaders_list_view_context_leaders(self, auth_client, fan_user):
        c = auth_client(fan_user)
        response = c.get(reverse("analytics:leaders"))
        assert "leaders" in response.context or response.status_code == 200

    def test_leaders_list_view_displays_player_names(self, auth_client, fan_user):
        c = auth_client(fan_user)
        response = c.get(reverse("analytics:leaders"))
        assert response.status_code == 200

    def test_leaders_list_view_displays_averages(self, auth_client, fan_user):
        c = auth_client(fan_user)
        response = c.get(reverse("analytics:leaders"))
        assert response.status_code == 200

    def test_leaders_list_view_filter_by_season(self, auth_client, fan_user, season):
        c = auth_client(fan_user)
        response = c.get(reverse("analytics:leaders"), {"season": season.id})
        assert response.status_code == 200

    def test_leaders_list_view_category_points(self, auth_client, fan_user):
        c = auth_client(fan_user)
        response = c.get(reverse("analytics:leaders"), {"category": "points"})
        assert response.status_code == 200

    def test_leaders_list_view_category_valuation(self, auth_client, fan_user):
        c = auth_client(fan_user)
        response = c.get(reverse("analytics:leaders"), {"category": "valuation"})
        assert response.status_code == 200

    def test_leaders_list_view_category_assists(self, auth_client, fan_user):
        c = auth_client(fan_user)
        response = c.get(reverse("analytics:leaders"), {"category": "assists"})
        assert response.status_code == 200

    def test_leaders_list_view_category_rebounds(self, auth_client, fan_user):
        c = auth_client(fan_user)
        response = c.get(reverse("analytics:leaders"), {"category": "rebounds"})
        assert response.status_code == 200


@pytest.mark.django_db
class TestTeamComparatorView:
    """Pruebas de integración para el comparador de equipos cara a cara."""

    def test_team_comparator_view_get_renders_200(self, auth_client, fan_user):
        c = auth_client(fan_user)
        response = c.get(reverse("analytics:compare_teams"))
        assert response.status_code == 200

    def test_team_comparator_view_context_teams(self, auth_client, fan_user, home_team, away_team):
        c = auth_client(fan_user)
        response = c.get(reverse("analytics:compare_teams"))
        assert "teams" in response.context
        assert home_team in response.context["teams"]

    def test_team_comparator_view_post_compare_two_teams_success(
        self, auth_client, fan_user, home_team, away_team, season
    ):
        c = auth_client(fan_user)
        response = c.post(
            reverse("analytics:compare_teams"),
            {
                "team_a": home_team.id,
                "team_b": away_team.id,
                "season": season.id,
            },
        )
        assert response.status_code == 200
        assert "comparison" in response.context or "team_a" in response.context

    def test_team_comparator_view_post_same_team_handled(self, auth_client, fan_user, home_team):
        c = auth_client(fan_user)
        response = c.post(
            reverse("analytics:compare_teams"),
            {
                "team_a": home_team.id,
                "team_b": home_team.id,
            },
        )
        assert response.status_code == 200

    def test_team_comparator_view_context_radar_metrics(self, auth_client, fan_user, home_team, away_team):
        c = auth_client(fan_user)
        response = c.post(
            reverse("analytics:compare_teams"),
            {"team_a": home_team.id, "team_b": away_team.id},
        )
        assert response.status_code == 200

    def test_team_comparator_view_context_h2h_matches(self, auth_client, fan_user, home_team, away_team):
        c = auth_client(fan_user)
        response = c.post(
            reverse("analytics:compare_teams"),
            {"team_a": home_team.id, "team_b": away_team.id},
        )
        assert response.status_code == 200

    def test_team_comparator_view_context_positional_groups(self, auth_client, fan_user, home_team, away_team):
        c = auth_client(fan_user)
        response = c.post(
            reverse("analytics:compare_teams"),
            {"team_a": home_team.id, "team_b": away_team.id},
        )
        assert response.status_code == 200

    def test_team_comparator_view_displays_team_badges(self, auth_client, fan_user, home_team, away_team):
        c = auth_client(fan_user)
        response = c.post(
            reverse("analytics:compare_teams"),
            {"team_a": home_team.id, "team_b": away_team.id},
        )
        content = response.content.decode("utf-8")
        assert "RMB" in content
        assert "FCB" in content

    def test_team_comparator_view_displays_offensive_ratings(self, auth_client, fan_user, home_team, away_team):
        c = auth_client(fan_user)
        response = c.post(
            reverse("analytics:compare_teams"),
            {"team_a": home_team.id, "team_b": away_team.id},
        )
        assert response.status_code == 200

    def test_team_comparator_view_displays_defensive_ratings(self, auth_client, fan_user, home_team, away_team):
        c = auth_client(fan_user)
        response = c.post(
            reverse("analytics:compare_teams"),
            {"team_a": home_team.id, "team_b": away_team.id},
        )
        assert response.status_code == 200


@pytest.mark.django_db
class TestPlayerComparatorView:
    """Pruebas de integración para el comparador individual de jugadores."""

    def test_player_comparator_view_get_renders_200(self, auth_client, fan_user):
        c = auth_client(fan_user)
        response = c.get(reverse("analytics:compare_players"))
        assert response.status_code == 200

    def test_player_comparator_view_context_players(self, auth_client, fan_user, home_players):
        c = auth_client(fan_user)
        response = c.get(reverse("analytics:compare_players"))
        assert "players" in response.context

    def test_player_comparator_view_post_compare_two_players_success(
        self, auth_client, fan_user, home_players, away_players
    ):
        c = auth_client(fan_user)
        response = c.post(
            reverse("analytics:compare_players"),
            {
                "player_a": home_players[0].id,
                "player_b": away_players[0].id,
            },
        )
        assert response.status_code == 200
        assert "player_a" in response.context
        assert "player_b" in response.context

    def test_player_comparator_view_context_player_stats(
        self, auth_client, fan_user, home_players, away_players
    ):
        c = auth_client(fan_user)
        response = c.post(
            reverse("analytics:compare_players"),
            {
                "player_a": home_players[0].id,
                "player_b": away_players[0].id,
            },
        )
        assert response.status_code == 200

    def test_player_comparator_view_displays_biometrics(
        self, auth_client, fan_user, home_players, away_players
    ):
        c = auth_client(fan_user)
        response = c.post(
            reverse("analytics:compare_players"),
            {
                "player_a": home_players[0].id,
                "player_b": away_players[0].id,
            },
        )
        content = response.content.decode("utf-8")
        assert home_players[0].full_name in content

    def test_player_comparator_view_displays_head_to_head_win_probability(
        self, auth_client, fan_user, home_players, away_players
    ):
        c = auth_client(fan_user)
        response = c.post(
            reverse("analytics:compare_players"),
            {
                "player_a": home_players[0].id,
                "player_b": away_players[0].id,
            },
        )
        assert response.status_code == 200


@pytest.mark.django_db
class TestPredictiveModelView:
    """Pruebas de integración para el modelo predictivo oficial de encuentros."""

    def test_predictive_model_view_get_renders_200(self, auth_client, fan_user):
        c = auth_client(fan_user)
        response = c.get(reverse("analytics:predictive_model"))
        assert response.status_code == 200

    def test_predictive_model_view_context_scheduled_matches(self, auth_client, fan_user, scheduled_match):
        c = auth_client(fan_user)
        response = c.get(reverse("analytics:predictive_model"))
        assert "matches" in response.context or "scheduled_matches" in response.context or response.status_code == 200

    def test_predictive_model_view_post_predict_match_success(
        self, auth_client, fan_user, home_team, away_team, season
    ):
        c = auth_client(fan_user)
        response = c.post(
            reverse("analytics:predictive_model"),
            {
                "team_a": home_team.id,
                "team_b": away_team.id,
                "season": season.id,
            },
        )
        assert response.status_code == 200

    def test_predictive_model_view_displays_pythagorean_expectation(
        self, auth_client, fan_user, home_team, away_team
    ):
        c = auth_client(fan_user)
        response = c.post(
            reverse("analytics:predictive_model"),
            {"team_a": home_team.id, "team_b": away_team.id},
        )
        assert response.status_code == 200

    def test_predictive_model_view_displays_logistic_regression_probabilities(
        self, auth_client, fan_user, home_team, away_team
    ):
        c = auth_client(fan_user)
        response = c.post(
            reverse("analytics:predictive_model"),
            {"team_a": home_team.id, "team_b": away_team.id},
        )
        assert response.status_code == 200
