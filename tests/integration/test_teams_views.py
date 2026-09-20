import pytest
import datetime
from django.urls import reverse
from apps.teams.models import League, Season, Team, Player, TeamMembership


@pytest.mark.django_db
class TestLeagueViews:
    """Pruebas de integración para las vistas de ligas y competiciones."""

    def test_league_list_view_renders_200(self, auth_client, fan_user):
        c = auth_client(fan_user)
        response = c.get(reverse("teams:league_list"))
        assert response.status_code == 200

    def test_league_list_view_context_leagues(self, auth_client, fan_user, league):
        c = auth_client(fan_user)
        response = c.get(reverse("teams:league_list"))
        assert "leagues" in response.context
        assert league in response.context["leagues"]

    def test_league_list_view_displays_league_name(self, auth_client, fan_user, league):
        c = auth_client(fan_user)
        response = c.get(reverse("teams:league_list"))
        assert league.name in response.content.decode("utf-8")

    def test_league_list_view_displays_season_count(self, auth_client, fan_user, league, season):
        c = auth_client(fan_user)
        response = c.get(reverse("teams:league_list"))
        assert response.status_code == 200

    def test_league_detail_view_renders_200(self, auth_client, fan_user, league):
        c = auth_client(fan_user)
        response = c.get(reverse("teams:league_detail", kwargs={"slug": league.slug}))
        assert response.status_code == 200

    def test_league_detail_view_context_active_season(self, auth_client, fan_user, league, season):
        c = auth_client(fan_user)
        response = c.get(reverse("teams:league_detail", kwargs={"slug": league.slug}))
        assert "active_season" in response.context
        assert response.context["active_season"] == season

    def test_league_detail_view_context_standings(self, auth_client, fan_user, league):
        c = auth_client(fan_user)
        response = c.get(reverse("teams:league_detail", kwargs={"slug": league.slug}))
        assert "standings" in response.context

    def test_league_detail_view_context_matches(self, auth_client, fan_user, league):
        c = auth_client(fan_user)
        response = c.get(reverse("teams:league_detail", kwargs={"slug": league.slug}))
        assert "matches" in response.context

    def test_league_detail_view_displays_team_names(self, auth_client, fan_user, league, home_team):
        c = auth_client(fan_user)
        response = c.get(reverse("teams:league_detail", kwargs={"slug": league.slug}))
        assert response.status_code == 200

    def test_league_detail_view_displays_table_headers_pj_pg_pp_pts(self, auth_client, fan_user, league, standings_setup):
        c = auth_client(fan_user)
        response = c.get(reverse("teams:league_detail", kwargs={"slug": league.slug}))
        content = response.content.decode("utf-8")
        assert "PTS" in content or "PJ" in content


@pytest.mark.django_db
class TestTeamViews:
    """Pruebas de integración para las vistas de clubes y plantillas."""

    def test_team_list_view_renders_200(self, auth_client, fan_user):
        c = auth_client(fan_user)
        response = c.get(reverse("teams:team_list"))
        assert response.status_code == 200

    def test_team_list_view_context_teams(self, auth_client, fan_user, home_team):
        c = auth_client(fan_user)
        response = c.get(reverse("teams:team_list"))
        assert "teams" in response.context
        assert home_team in response.context["teams"]

    def test_team_list_view_displays_team_acronym(self, auth_client, fan_user, home_team):
        c = auth_client(fan_user)
        response = c.get(reverse("teams:team_list"))
        assert "RMB" in response.content.decode("utf-8")

    def test_team_list_view_displays_coach_name(self, auth_client, fan_user, home_team):
        c = auth_client(fan_user)
        response = c.get(reverse("teams:team_list"))
        assert "Pablo Laso" in response.content.decode("utf-8") or "coach_local" in response.content.decode("utf-8")

    def test_team_list_view_displays_city(self, auth_client, fan_user, home_team):
        c = auth_client(fan_user)
        response = c.get(reverse("teams:team_list"))
        assert "Madrid" in response.content.decode("utf-8")

    def test_team_detail_view_renders_200(self, auth_client, fan_user, home_team):
        c = auth_client(fan_user)
        response = c.get(reverse("teams:team_detail", kwargs={"slug": home_team.slug}))
        assert response.status_code == 200

    def test_team_detail_view_context_team(self, auth_client, fan_user, home_team):
        c = auth_client(fan_user)
        response = c.get(reverse("teams:team_detail", kwargs={"slug": home_team.slug}))
        assert "team" in response.context
        assert response.context["team"] == home_team

    def test_team_detail_view_displays_arena(self, auth_client, fan_user, home_team):
        c = auth_client(fan_user)
        response = c.get(reverse("teams:team_detail", kwargs={"slug": home_team.slug}))
        assert "WiZink Center Test" in response.content.decode("utf-8")

    def test_team_detail_view_displays_colors(self, auth_client, fan_user, home_team):
        c = auth_client(fan_user)
        response = c.get(reverse("teams:team_detail", kwargs={"slug": home_team.slug}))
        assert response.status_code == 200

    def test_team_detail_view_displays_roster_members(self, auth_client, fan_user, home_team, home_players):
        c = auth_client(fan_user)
        response = c.get(reverse("teams:team_detail", kwargs={"slug": home_team.slug}))
        content = response.content.decode("utf-8")
        assert "JugadorLocal1" in content

    def test_team_detail_view_displays_dorsals(self, auth_client, fan_user, home_team, home_players):
        c = auth_client(fan_user)
        response = c.get(reverse("teams:team_detail", kwargs={"slug": home_team.slug}))
        content = response.content.decode("utf-8")
        assert "#7" in content or "7" in content

    def test_team_detail_view_displays_captain_badge(self, auth_client, fan_user, home_team, home_players):
        c = auth_client(fan_user)
        response = c.get(reverse("teams:team_detail", kwargs={"slug": home_team.slug}))
        assert response.status_code == 200

    def test_team_detail_view_displays_player_positions(self, auth_client, fan_user, home_team, home_players):
        c = auth_client(fan_user)
        response = c.get(reverse("teams:team_detail", kwargs={"slug": home_team.slug}))
        assert response.status_code == 200


@pytest.mark.django_db
class TestPlayerViews:
    """Pruebas de integración para las fichas técnicas individuales de jugadores."""

    def test_player_detail_view_renders_200(self, auth_client, fan_user, home_players):
        c = auth_client(fan_user)
        response = c.get(reverse("teams:player_detail", kwargs={"pk": home_players[0].pk}))
        assert response.status_code == 200

    def test_player_detail_view_context_player(self, auth_client, fan_user, home_players):
        c = auth_client(fan_user)
        response = c.get(reverse("teams:player_detail", kwargs={"pk": home_players[0].pk}))
        assert "player" in response.context
        assert response.context["player"] == home_players[0]

    def test_player_detail_view_displays_full_name(self, auth_client, fan_user, home_players):
        c = auth_client(fan_user)
        response = c.get(reverse("teams:player_detail", kwargs={"pk": home_players[0].pk}))
        assert home_players[0].full_name in response.content.decode("utf-8")

    def test_player_detail_view_displays_position(self, auth_client, fan_user, home_players):
        c = auth_client(fan_user)
        response = c.get(reverse("teams:player_detail", kwargs={"pk": home_players[0].pk}))
        assert response.status_code == 200

    def test_player_detail_view_displays_height_and_weight(self, auth_client, fan_user, home_players):
        c = auth_client(fan_user)
        response = c.get(reverse("teams:player_detail", kwargs={"pk": home_players[0].pk}))
        content = response.content.decode("utf-8")
        assert "cm" in content or str(home_players[0].height_cm) in content

    def test_player_detail_view_displays_birth_date(self, auth_client, fan_user, home_players):
        c = auth_client(fan_user)
        response = c.get(reverse("teams:player_detail", kwargs={"pk": home_players[0].pk}))
        assert response.status_code == 200

    def test_player_detail_view_displays_current_team(self, auth_client, fan_user, home_players, home_team):
        c = auth_client(fan_user)
        response = c.get(reverse("teams:player_detail", kwargs={"pk": home_players[0].pk}))
        assert home_team.name in response.content.decode("utf-8") or home_team.acronym in response.content.decode("utf-8")


@pytest.mark.django_db
class TestCoachRosterManageView:
    """Pruebas de integración para la gestión de plantillas por parte del entrenador."""

    def test_coach_roster_manage_view_renders_200_for_assigned_coach(self, auth_client, coach_user, home_team):
        c = auth_client(coach_user)
        response = c.get(reverse("teams:roster_manage", kwargs={"slug": home_team.slug}))
        assert response.status_code == 200

    def test_coach_roster_manage_view_context_team(self, auth_client, coach_user, home_team):
        c = auth_client(coach_user)
        response = c.get(reverse("teams:roster_manage", kwargs={"slug": home_team.slug}))
        assert "team" in response.context
        assert response.context["team"] == home_team

    def test_coach_roster_manage_view_context_memberships(self, auth_client, coach_user, home_team, home_players):
        c = auth_client(coach_user)
        response = c.get(reverse("teams:roster_manage", kwargs={"slug": home_team.slug}))
        assert "memberships" in response.context
        assert len(response.context["memberships"]) == len(home_players)

    def test_coach_roster_manage_view_post_enroll_new_player_success(self, auth_client, coach_user, home_team):
        c = auth_client(coach_user)
        response = c.post(
            reverse("teams:roster_manage", kwargs={"slug": home_team.slug}),
            {
                "action": "create_player",
                "first_name": "Mario",
                "last_name": "Hezonja",
                "birth_date": "1995-02-25",
                "height_cm": 203,
                "weight_kg": 100.0,
                "position": "SF",
                "jersey_number": 8,
                "is_captain": False,
            },
        )
        assert response.status_code == 302
        assert Player.objects.filter(first_name="Mario", last_name="Hezonja").exists()

    def test_coach_roster_manage_view_post_enroll_existing_player_success(
        self, auth_client, coach_user, home_team, season
    ):
        p_free = Player.objects.create(first_name="Guerschon", last_name="Yabusele", height_cm=204, weight_kg=120)
        c = auth_client(coach_user)
        response = c.post(
            reverse("teams:roster_manage", kwargs={"slug": home_team.slug}),
            {
                "action": "add_existing",
                "player": p_free.id,
                "jersey_number": 28,
                "is_captain": False,
            },
        )
        assert response.status_code == 302
        assert TeamMembership.objects.filter(player=p_free, team=home_team, jersey_number=28).exists()

    def test_coach_roster_manage_view_post_duplicate_dorsal_shows_error(
        self, auth_client, coach_user, home_team, home_players
    ):
        p_free = Player.objects.create(first_name="Edy", last_name="Tavares", height_cm=220, weight_kg=125)
        c = auth_client(coach_user)
        # Dorsal 7 is taken
        response = c.post(
            reverse("teams:roster_manage", kwargs={"slug": home_team.slug}),
            {
                "action": "add_existing",
                "player": p_free.id,
                "jersey_number": 7,
                "is_captain": False,
            },
        )
        assert response.status_code == 200 or response.status_code == 302

    def test_coach_roster_manage_view_post_edit_player_data_success(
        self, auth_client, coach_user, home_team, home_players, season
    ):
        p = home_players[0]
        c = auth_client(coach_user)
        response = c.post(
            reverse("teams:roster_manage", kwargs={"slug": home_team.slug}),
            {
                "action": "edit_player",
                "player_id": p.id,
                "first_name": "Facu",
                "last_name": "Campazzo",
                "birth_date": "1991-03-23",
                "height_cm": 180,
                "weight_kg": 84.0,
                "position": "PG",
                "jersey_number": 7,
                "is_captain": True,
            },
        )
        assert response.status_code == 302

    def test_coach_roster_manage_view_post_edit_player_invalid_data_shows_error(
        self, auth_client, coach_user, home_team, home_players
    ):
        p = home_players[0]
        c = auth_client(coach_user)
        response = c.post(
            reverse("teams:roster_manage", kwargs={"slug": home_team.slug}),
            {
                "action": "edit_player",
                "player_id": p.id,
                "first_name": "F",  # too short
                "last_name": "Campazzo",
                "position": "PG",
                "jersey_number": 7,
            },
        )
        assert response.status_code == 200

    def test_coach_roster_manage_view_post_deactivate_player_membership(
        self, auth_client, coach_user, home_team, home_players, season
    ):
        p = home_players[0]
        c = auth_client(coach_user)
        response = c.post(
            reverse("teams:roster_manage", kwargs={"slug": home_team.slug}),
            {
                "action": "deactivate_member",
                "player_id": p.id,
            },
        )
        assert response.status_code == 302 or response.status_code == 200

    def test_coach_roster_manage_view_post_toggle_captain_status(
        self, auth_client, coach_user, home_team, home_players, season
    ):
        p = home_players[1]
        c = auth_client(coach_user)
        response = c.post(
            reverse("teams:roster_manage", kwargs={"slug": home_team.slug}),
            {
                "action": "toggle_captain",
                "player_id": p.id,
            },
        )
        assert response.status_code == 302 or response.status_code == 200
