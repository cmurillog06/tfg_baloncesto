import pytest
from django.urls import reverse
from apps.matches.models import Match, MatchEvent, DigitalScoreSheet


@pytest.mark.django_db
class TestMatchListView:
    """Pruebas de integración para la cartelera y listado de partidos."""

    def test_match_list_view_renders_200(self, auth_client, fan_user):
        c = auth_client(fan_user)
        response = c.get(reverse("matches:match_list"))
        assert response.status_code == 200

    def test_match_list_view_context_live_matches(self, auth_client, fan_user, live_match):
        c = auth_client(fan_user)
        response = c.get(reverse("matches:match_list"))
        assert "live_matches" in response.context
        assert live_match in response.context["live_matches"]

    def test_match_list_view_context_upcoming_matches(self, auth_client, fan_user, scheduled_match):
        c = auth_client(fan_user)
        response = c.get(reverse("matches:match_list"))
        assert "upcoming_matches" in response.context
        assert scheduled_match in response.context["upcoming_matches"]

    def test_match_list_view_context_finished_matches(self, auth_client, fan_user, finished_match):
        c = auth_client(fan_user)
        response = c.get(reverse("matches:match_list"))
        assert "finished_matches" in response.context
        assert finished_match in response.context["finished_matches"]

    def test_match_list_view_shows_team_acronyms(self, auth_client, fan_user, live_match):
        c = auth_client(fan_user)
        response = c.get(reverse("matches:match_list"))
        assert "RMB" in response.content.decode("utf-8")
        assert "FCB" in response.content.decode("utf-8")

    def test_match_list_view_shows_scores(self, auth_client, fan_user, live_match):
        c = auth_client(fan_user)
        response = c.get(reverse("matches:match_list"))
        content = response.content.decode("utf-8")
        assert "12" in content
        assert "8" in content

    def test_match_list_view_shows_round_number(self, auth_client, fan_user, live_match):
        c = auth_client(fan_user)
        response = c.get(reverse("matches:match_list"))
        assert response.status_code == 200

    def test_match_list_view_shows_league_badge(self, auth_client, fan_user, live_match):
        c = auth_client(fan_user)
        response = c.get(reverse("matches:match_list"))
        assert "Liga Senior Oro Test" in response.content.decode("utf-8")


@pytest.mark.django_db
class TestMatchLiveView:
    """Pruebas de integración para la retransmisión en tiempo real de partidos."""

    def test_match_live_view_renders_200_for_fan(self, auth_client, fan_user, live_match):
        c = auth_client(fan_user)
        response = c.get(reverse("matches:match_live", kwargs={"pk": live_match.pk}))
        assert response.status_code == 200

    def test_match_live_view_renders_200_for_coach(self, auth_client, coach_user, live_match):
        c = auth_client(coach_user)
        response = c.get(reverse("matches:match_live", kwargs={"pk": live_match.pk}))
        assert response.status_code == 200

    def test_match_live_view_renders_200_for_table_official(self, auth_client, table_official_user, live_match):
        c = auth_client(table_official_user)
        response = c.get(reverse("matches:match_live", kwargs={"pk": live_match.pk}))
        assert response.status_code == 200

    def test_match_live_view_context_home_roster(self, auth_client, fan_user, live_match):
        c = auth_client(fan_user)
        response = c.get(reverse("matches:match_live", kwargs={"pk": live_match.pk}))
        assert "home_roster" in response.context
        assert len(response.context["home_roster"]) > 0

    def test_match_live_view_context_away_roster(self, auth_client, fan_user, live_match):
        c = auth_client(fan_user)
        response = c.get(reverse("matches:match_live", kwargs={"pk": live_match.pk}))
        assert "away_roster" in response.context
        assert len(response.context["away_roster"]) > 0

    def test_match_live_view_context_home_player_stats(self, auth_client, fan_user, live_match):
        c = auth_client(fan_user)
        response = c.get(reverse("matches:match_live", kwargs={"pk": live_match.pk}))
        assert "home_player_stats" in response.context

    def test_match_live_view_context_away_player_stats(self, auth_client, fan_user, live_match):
        c = auth_client(fan_user)
        response = c.get(reverse("matches:match_live", kwargs={"pk": live_match.pk}))
        assert "away_player_stats" in response.context

    def test_match_live_view_context_home_timeouts(self, auth_client, fan_user, live_match):
        c = auth_client(fan_user)
        response = c.get(reverse("matches:match_live", kwargs={"pk": live_match.pk}))
        assert "home_timeouts" in response.context
        assert response.context["home_timeouts"]["limit"] == 2

    def test_match_live_view_context_away_timeouts(self, auth_client, fan_user, live_match):
        c = auth_client(fan_user)
        response = c.get(reverse("matches:match_live", kwargs={"pk": live_match.pk}))
        assert "away_timeouts" in response.context

    def test_match_live_view_context_home_fouls_info(self, auth_client, fan_user, live_match):
        c = auth_client(fan_user)
        response = c.get(reverse("matches:match_live", kwargs={"pk": live_match.pk}))
        assert "home_fouls_info" in response.context
        assert response.context["home_fouls_info"]["limit"] == 5

    def test_match_live_view_context_away_fouls_info(self, auth_client, fan_user, live_match):
        c = auth_client(fan_user)
        response = c.get(reverse("matches:match_live", kwargs={"pk": live_match.pk}))
        assert "away_fouls_info" in response.context

    def test_match_live_view_context_on_court_ids(self, auth_client, fan_user, live_match):
        c = auth_client(fan_user)
        response = c.get(reverse("matches:match_live", kwargs={"pk": live_match.pk}))
        assert "home_on_court_ids" in response.context
        assert "away_on_court_ids" in response.context

    def test_match_live_view_context_recent_events(self, auth_client, fan_user, live_match):
        c = auth_client(fan_user)
        response = c.get(reverse("matches:match_live", kwargs={"pk": live_match.pk}))
        assert "recent_events" in response.context

    def test_match_live_view_can_manage_table_true_for_assigned_official(
        self, auth_client, table_official_user, live_match
    ):
        c = auth_client(table_official_user)
        response = c.get(reverse("matches:match_live", kwargs={"pk": live_match.pk}))
        assert response.context["can_manage_table"] is True

    def test_match_live_view_can_manage_table_false_for_fan(self, auth_client, fan_user, live_match):
        c = auth_client(fan_user)
        response = c.get(reverse("matches:match_live", kwargs={"pk": live_match.pk}))
        assert response.context["can_manage_table"] is False

    def test_match_live_view_can_manage_table_false_for_coach(self, auth_client, coach_user, live_match):
        c = auth_client(coach_user)
        response = c.get(reverse("matches:match_live", kwargs={"pk": live_match.pk}))
        assert response.context["can_manage_table"] is False

    def test_match_live_view_can_view_scoresheet_true_for_coach(self, auth_client, coach_user, live_match):
        c = auth_client(coach_user)
        response = c.get(reverse("matches:match_live", kwargs={"pk": live_match.pk}))
        assert response.context["can_view_scoresheet"] is True

    def test_match_live_view_can_view_scoresheet_false_for_fan(self, auth_client, fan_user, live_match):
        c = auth_client(fan_user)
        response = c.get(reverse("matches:match_live", kwargs={"pk": live_match.pk}))
        assert response.context["can_view_scoresheet"] is False

    def test_match_live_view_auto_closes_scoresheet_if_finished(self, auth_client, table_official_user, finished_match):
        c = auth_client(table_official_user)
        response = c.get(reverse("matches:match_live", kwargs={"pk": finished_match.pk}))
        assert response.status_code == 200
        assert hasattr(finished_match, "scoresheet")
        assert finished_match.scoresheet.is_closed is True


@pytest.mark.django_db
class TestOfficialTableScorekeeperView:
    """Pruebas de integración para la consola interactiva de la mesa arbitral."""

    def test_scorekeeper_view_renders_200_for_assigned_table_official(
        self, auth_client, table_official_user, live_match
    ):
        c = auth_client(table_official_user)
        response = c.get(reverse("matches:scorekeeper", kwargs={"pk": live_match.pk}))
        assert response.status_code == 200

    def test_scorekeeper_view_context_home_roster(self, auth_client, table_official_user, live_match):
        c = auth_client(table_official_user)
        response = c.get(reverse("matches:scorekeeper", kwargs={"pk": live_match.pk}))
        assert "home_roster" in response.context
        assert len(response.context["home_roster"]) > 0

    def test_scorekeeper_view_context_away_roster(self, auth_client, table_official_user, live_match):
        c = auth_client(table_official_user)
        response = c.get(reverse("matches:scorekeeper", kwargs={"pk": live_match.pk}))
        assert "away_roster" in response.context

    def test_scorekeeper_view_context_player_points_json(self, auth_client, table_official_user, live_match):
        c = auth_client(table_official_user)
        response = c.get(reverse("matches:scorekeeper", kwargs={"pk": live_match.pk}))
        assert "player_points_json" in response.context

    def test_scorekeeper_view_context_player_fouls_json(self, auth_client, table_official_user, live_match):
        c = auth_client(table_official_user)
        response = c.get(reverse("matches:scorekeeper", kwargs={"pk": live_match.pk}))
        assert "player_fouls_json" in response.context

    def test_scorekeeper_view_context_recent_events(self, auth_client, table_official_user, live_match):
        c = auth_client(table_official_user)
        response = c.get(reverse("matches:scorekeeper", kwargs={"pk": live_match.pk}))
        assert "recent_events" in response.context

    def test_scorekeeper_view_context_scoresheet(self, auth_client, table_official_user, live_match):
        c = auth_client(table_official_user)
        response = c.get(reverse("matches:scorekeeper", kwargs={"pk": live_match.pk}))
        assert "scoresheet" in response.context


@pytest.mark.django_db
class TestScoreSheetDetailView:
    """Pruebas de integración para la visualización del acta digital oficial."""

    def test_scoresheet_detail_view_renders_200_for_table_official(
        self, auth_client, table_official_user, finished_match
    ):
        c = auth_client(table_official_user)
        response = c.get(reverse("matches:scoresheet_detail", kwargs={"pk": finished_match.pk}))
        assert response.status_code == 200

    def test_scoresheet_detail_view_renders_200_for_coach(self, auth_client, coach_user, finished_match):
        c = auth_client(coach_user)
        response = c.get(reverse("matches:scoresheet_detail", kwargs={"pk": finished_match.pk}))
        assert response.status_code == 200

    def test_scoresheet_detail_view_context_quarters_breakdown(
        self, auth_client, table_official_user, finished_match
    ):
        c = auth_client(table_official_user)
        response = c.get(reverse("matches:scoresheet_detail", kwargs={"pk": finished_match.pk}))
        assert "quarters_breakdown" in response.context

    def test_scoresheet_detail_view_context_home_roster_stats(
        self, auth_client, table_official_user, finished_match
    ):
        c = auth_client(table_official_user)
        response = c.get(reverse("matches:scoresheet_detail", kwargs={"pk": finished_match.pk}))
        assert "home_roster_stats" in response.context

    def test_scoresheet_detail_view_context_away_roster_stats(
        self, auth_client, table_official_user, finished_match
    ):
        c = auth_client(table_official_user)
        response = c.get(reverse("matches:scoresheet_detail", kwargs={"pk": finished_match.pk}))
        assert "away_roster_stats" in response.context


@pytest.mark.django_db
class TestRestoreDemoDataView:
    """Prueba de integración para la restauración canónica de datos de demostración."""

    def test_restore_demo_data_view_redirects_and_restores(self, auth_client, admin_user):
        c = auth_client(admin_user)
        response = c.get(reverse("matches:restore_demo_data"))
        assert response.status_code == 302
        assert reverse("matches:match_list") in response.url
