import pytest
from django.urls import reverse
from apps.accounts.models import CustomUser


@pytest.mark.django_db
class TestUnauthenticatedAccessRedirects:
    """Pruebas de integración: redirección al login para vistas protegidas."""

    def test_unauthenticated_user_accessing_match_list_redirects_to_login(self, client):
        response = client.get(reverse("matches:match_list"))
        assert response.status_code == 302
        assert reverse("accounts:login") in response.url

    def test_unauthenticated_user_accessing_match_live_redirects_to_login(self, client, live_match):
        response = client.get(reverse("matches:match_live", kwargs={"pk": live_match.pk}))
        assert response.status_code == 302
        assert reverse("accounts:login") in response.url

    def test_unauthenticated_user_accessing_scorekeeper_redirects_to_login(self, client, live_match):
        response = client.get(reverse("matches:scorekeeper", kwargs={"pk": live_match.pk}))
        assert response.status_code == 302
        assert reverse("accounts:login") in response.url

    def test_unauthenticated_user_accessing_scoresheet_redirects_to_login(self, client, finished_match):
        response = client.get(reverse("matches:scoresheet_detail", kwargs={"pk": finished_match.pk}))
        assert response.status_code == 302
        assert reverse("accounts:login") in response.url

    def test_unauthenticated_user_accessing_league_list_redirects_to_login(self, client):
        response = client.get(reverse("teams:league_list"))
        assert response.status_code == 302
        assert reverse("accounts:login") in response.url

    def test_unauthenticated_user_accessing_league_detail_redirects_to_login(self, client, league):
        response = client.get(reverse("teams:league_detail", kwargs={"slug": league.slug}))
        assert response.status_code == 302
        assert reverse("accounts:login") in response.url

    def test_unauthenticated_user_accessing_team_list_redirects_to_login(self, client):
        response = client.get(reverse("teams:team_list"))
        assert response.status_code == 302
        assert reverse("accounts:login") in response.url

    def test_unauthenticated_user_accessing_team_detail_redirects_to_login(self, client, home_team):
        response = client.get(reverse("teams:team_detail", kwargs={"slug": home_team.slug}))
        assert response.status_code == 302
        assert reverse("accounts:login") in response.url

    def test_unauthenticated_user_accessing_player_detail_redirects_to_login(self, client, home_players):
        response = client.get(reverse("teams:player_detail", kwargs={"pk": home_players[0].pk}))
        assert response.status_code == 302
        assert reverse("accounts:login") in response.url

    def test_unauthenticated_user_accessing_roster_manage_redirects_to_login(self, client, home_team):
        response = client.get(reverse("teams:roster_manage", kwargs={"slug": home_team.slug}))
        assert response.status_code == 302
        assert reverse("accounts:login") in response.url

    def test_unauthenticated_user_accessing_analytics_dashboard_redirects_to_login(self, client):
        response = client.get(reverse("analytics:dashboard"))
        assert response.status_code == 302
        assert reverse("accounts:login") in response.url

    def test_unauthenticated_user_accessing_leaders_redirects_to_login(self, client):
        response = client.get(reverse("analytics:leaders"))
        assert response.status_code == 302
        assert reverse("accounts:login") in response.url

    def test_unauthenticated_user_accessing_team_comparator_redirects_to_login(self, client):
        response = client.get(reverse("analytics:compare_teams"))
        assert response.status_code == 302
        assert reverse("accounts:login") in response.url

    def test_unauthenticated_user_accessing_player_comparator_redirects_to_login(self, client):
        response = client.get(reverse("analytics:compare_players"))
        assert response.status_code == 302
        assert reverse("accounts:login") in response.url

    def test_unauthenticated_user_accessing_predictive_model_redirects_to_login(self, client):
        response = client.get(reverse("analytics:predictive_model"))
        assert response.status_code == 302
        assert reverse("accounts:login") in response.url

    def test_unauthenticated_user_accessing_profile_redirects_to_login(self, client):
        response = client.get(reverse("accounts:profile"))
        assert response.status_code == 302
        assert reverse("accounts:login") in response.url


@pytest.mark.django_db
class TestAuthenticationViews:
    """Pruebas de integración para login, registro, logout y perfil."""

    def test_login_view_get_renders_form(self, client):
        response = client.get(reverse("accounts:login"))
        assert response.status_code == 200
        assert "form" in response.context

    def test_login_view_post_valid_credentials_logs_in(self, client, fan_user):
        response = client.post(
            reverse("accounts:login"),
            {"username": fan_user.username, "password": "FanPassword123!"},
        )
        assert response.status_code == 302

    def test_login_view_post_invalid_password_shows_error(self, client, fan_user):
        response = client.post(
            reverse("accounts:login"),
            {"username": fan_user.username, "password": "WrongPassword99!"},
        )
        assert response.status_code == 200
        assert "form" in response.context
        assert response.context["form"].errors

    def test_login_view_authenticated_user_redirected(self, auth_client, fan_user):
        c = auth_client(fan_user)
        response = c.get(reverse("accounts:login"))
        assert response.status_code == 302

    def test_register_view_get_renders_form(self, client):
        response = client.get(reverse("accounts:register"))
        assert response.status_code == 200
        assert "form" in response.context

    def test_register_view_post_valid_creates_and_logs_in(self, client):
        response = client.post(
            reverse("accounts:register"),
            {
                "username": "nuevo_aficionado",
                "email": "nuevo_aficionado@correo.com",
                "password1": "PasswordSegura123!",
                "password2": "PasswordSegura123!",
            },
        )
        assert response.status_code == 302
        assert CustomUser.objects.filter(username="nuevo_aficionado").exists()

    def test_register_view_post_invalid_redisplays_errors(self, client):
        response = client.post(
            reverse("accounts:register"),
            {
                "username": "123",  # all digits
                "email": "invalido",
                "password1": "Pass",
                "password2": "Diff",
            },
        )
        assert response.status_code == 200
        assert "form" in response.context
        assert response.context["form"].errors

    def test_register_view_authenticated_user_redirected(self, auth_client, fan_user):
        c = auth_client(fan_user)
        response = c.get(reverse("accounts:register"))
        assert response.status_code == 302

    def test_logout_view_post_logs_out_and_redirects(self, auth_client, fan_user):
        c = auth_client(fan_user)
        response = c.post(reverse("accounts:logout"))
        assert response.status_code == 302

    def test_logout_view_get_logs_out_and_redirects(self, auth_client, fan_user):
        c = auth_client(fan_user)
        response = c.get(reverse("accounts:logout"))
        assert response.status_code == 302

    def test_profile_view_get_renders_user_data(self, auth_client, fan_user):
        c = auth_client(fan_user)
        response = c.get(reverse("accounts:profile"))
        assert response.status_code == 200
        assert "user_form" in response.context
        assert "profile_form" in response.context

    def test_profile_view_post_updates_user_and_profile(self, auth_client, fan_user):
        c = auth_client(fan_user)
        response = c.post(
            reverse("accounts:profile"),
            {
                "username": "fan_perfil_nuevo",
                "email": "fan_perfil_nuevo@test.com",
                "phone": "+34 654 987 321",
                "bio": "Bio actualizada con exito.",
            },
        )
        assert response.status_code == 302
        fan_user.refresh_from_db()
        assert fan_user.username == "fan_perfil_nuevo"
        assert fan_user.profile.phone == "+34 654 987 321"

    def test_profile_view_post_invalid_shows_errors(self, auth_client, fan_user):
        c = auth_client(fan_user)
        response = c.post(
            reverse("accounts:profile"),
            {
                "username": "12",  # short
                "email": "not-an-email",
            },
        )
        assert response.status_code == 200
        assert response.context["user_form"].errors


@pytest.mark.django_db
class TestRoleBasedAccessControlRBAC:
    """Pruebas de integración para el control de acceso por roles (RBAC)."""

    def test_rbac_fan_accessing_scorekeeper_view_returns_403_forbidden(self, auth_client, fan_user, live_match):
        c = auth_client(fan_user)
        response = c.get(reverse("matches:scorekeeper", kwargs={"pk": live_match.pk}))
        assert response.status_code == 403

    def test_rbac_coach_accessing_scorekeeper_view_returns_403_forbidden(self, auth_client, coach_user, live_match):
        c = auth_client(coach_user)
        response = c.get(reverse("matches:scorekeeper", kwargs={"pk": live_match.pk}))
        assert response.status_code == 403

    def test_rbac_referee_accessing_scorekeeper_view_returns_403_forbidden(self, auth_client, referee_user, live_match):
        c = auth_client(referee_user)
        response = c.get(reverse("matches:scorekeeper", kwargs={"pk": live_match.pk}))
        assert response.status_code == 403

    def test_rbac_unassigned_table_official_accessing_scorekeeper_view_returns_403_forbidden(
        self, auth_client, unassigned_table_official, live_match
    ):
        c = auth_client(unassigned_table_official)
        response = c.get(reverse("matches:scorekeeper", kwargs={"pk": live_match.pk}))
        assert response.status_code == 403

    def test_rbac_assigned_table_official_accessing_scorekeeper_view_returns_200_ok(
        self, auth_client, table_official_user, live_match
    ):
        c = auth_client(table_official_user)
        response = c.get(reverse("matches:scorekeeper", kwargs={"pk": live_match.pk}))
        assert response.status_code == 200

    def test_rbac_assigned_timekeeper_accessing_scorekeeper_view_returns_200_ok(
        self, auth_client, second_table_official_user, live_match
    ):
        c = auth_client(second_table_official_user)
        response = c.get(reverse("matches:scorekeeper", kwargs={"pk": live_match.pk}))
        assert response.status_code == 200

    def test_rbac_admin_accessing_scorekeeper_view_returns_200_ok(self, auth_client, admin_user, live_match):
        c = auth_client(admin_user)
        response = c.get(reverse("matches:scorekeeper", kwargs={"pk": live_match.pk}))
        assert response.status_code == 200

    def test_rbac_scorekeeper_finished_match_redirects_to_scoresheet_detail(
        self, auth_client, table_official_user, finished_match
    ):
        c = auth_client(table_official_user)
        response = c.get(reverse("matches:scorekeeper", kwargs={"pk": finished_match.pk}))
        assert response.status_code == 302
        assert reverse("matches:scoresheet_detail", kwargs={"pk": finished_match.pk}) in response.url

    def test_rbac_fan_accessing_scoresheet_view_returns_403_forbidden(self, auth_client, fan_user, finished_match):
        c = auth_client(fan_user)
        response = c.get(reverse("matches:scoresheet_detail", kwargs={"pk": finished_match.pk}))
        assert response.status_code == 403

    def test_rbac_referee_accessing_scoresheet_view_returns_403_forbidden(self, auth_client, referee_user, finished_match):
        c = auth_client(referee_user)
        response = c.get(reverse("matches:scoresheet_detail", kwargs={"pk": finished_match.pk}))
        assert response.status_code == 403

    def test_rbac_coach_accessing_scoresheet_view_returns_200_ok(self, auth_client, coach_user, finished_match):
        c = auth_client(coach_user)
        response = c.get(reverse("matches:scoresheet_detail", kwargs={"pk": finished_match.pk}))
        assert response.status_code == 200

    def test_rbac_table_official_accessing_scoresheet_view_returns_200_ok(
        self, auth_client, table_official_user, finished_match
    ):
        c = auth_client(table_official_user)
        response = c.get(reverse("matches:scoresheet_detail", kwargs={"pk": finished_match.pk}))
        assert response.status_code == 200

    def test_rbac_admin_accessing_scoresheet_view_returns_200_ok(self, auth_client, admin_user, finished_match):
        c = auth_client(admin_user)
        response = c.get(reverse("matches:scoresheet_detail", kwargs={"pk": finished_match.pk}))
        assert response.status_code == 200

    def test_rbac_fan_accessing_roster_manage_returns_403_forbidden(self, auth_client, fan_user, home_team):
        c = auth_client(fan_user)
        response = c.get(reverse("teams:roster_manage", kwargs={"slug": home_team.slug}))
        assert response.status_code == 403

    def test_rbac_table_official_accessing_roster_manage_returns_403_forbidden(
        self, auth_client, table_official_user, home_team
    ):
        c = auth_client(table_official_user)
        response = c.get(reverse("teams:roster_manage", kwargs={"slug": home_team.slug}))
        assert response.status_code == 403

    def test_rbac_referee_accessing_roster_manage_returns_403_forbidden(
        self, auth_client, referee_user, home_team
    ):
        c = auth_client(referee_user)
        response = c.get(reverse("teams:roster_manage", kwargs={"slug": home_team.slug}))
        assert response.status_code == 403

    def test_rbac_other_coach_accessing_roster_manage_returns_403_forbidden(
        self, auth_client, away_coach_user, home_team
    ):
        c = auth_client(away_coach_user)
        response = c.get(reverse("teams:roster_manage", kwargs={"slug": home_team.slug}))
        assert response.status_code == 403

    def test_rbac_assigned_coach_accessing_roster_manage_returns_200_ok(
        self, auth_client, coach_user, home_team
    ):
        c = auth_client(coach_user)
        response = c.get(reverse("teams:roster_manage", kwargs={"slug": home_team.slug}))
        assert response.status_code == 200

    def test_rbac_admin_accessing_roster_manage_returns_200_ok(self, auth_client, admin_user, home_team):
        c = auth_client(admin_user)
        response = c.get(reverse("teams:roster_manage", kwargs={"slug": home_team.slug}))
        assert response.status_code == 200


@pytest.mark.django_db
class TestCoreViews:
    """Pruebas de integración para las páginas de inicio y portal público."""

    def test_core_home_view_public_access_200(self, client):
        response = client.get(reverse("core:home"))
        assert response.status_code == 200
        assert "leagues" in response.context

    def test_core_dashboard_view_public_access_200(self, client):
        response = client.get(reverse("core:dashboard"))
        assert response.status_code == 200
