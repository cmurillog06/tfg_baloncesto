import pytest
import datetime
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from apps.teams.models import League, Season, Team, Player, TeamMembership
from apps.teams.forms import (
    PlayerForm,
    TeamMembershipForm,
    CoachPlayerCreateForm,
    CoachPlayerEditForm,
    TeamForm,
)


@pytest.mark.django_db
class TestLeagueAndSeasonModels:
    """Pruebas unitarias para League y Season."""

    def test_league_creation_and_fields(self, league):
        assert league.pk is not None
        assert league.name == "Liga Senior Oro Test"
        assert league.is_active is True

    def test_league_auto_slugification(self):
        l = League.objects.create(name="Liga Cadete Especial")
        assert l.slug == "liga-cadete-especial"

    def test_league_str_representation(self, league):
        assert str(league) == "Liga Senior Oro Test"

    def test_league_ordering(self, db):
        l2 = League.objects.create(name="AAA Liga Primera")
        l1 = League.objects.create(name="ZZZ Liga Ultima")
        leagues = list(League.objects.all())
        assert leagues[0].name == "AAA Liga Primera"

    def test_season_creation_and_fields(self, season, league):
        assert season.pk is not None
        assert season.league == league
        assert season.is_current is True

    def test_season_str_representation(self, season):
        assert f"{season.league.name} - {season.name}" == str(season)

    def test_season_unique_together_league_and_name(self, season, league):
        with pytest.raises(IntegrityError):
            Season.objects.create(
                league=league,
                name=season.name,
                start_date=datetime.date(2025, 1, 1),
                end_date=datetime.date(2025, 12, 31),
            )


@pytest.mark.django_db
class TestTeamModel:
    """Pruebas unitarias para el modelo Team."""

    def test_team_creation_and_fields(self, home_team):
        assert home_team.pk is not None
        assert home_team.name == "Real Madrid Baloncesto Test"
        assert home_team.acronym == "RMB"

    def test_team_acronym_uppercase_auto(self):
        team = Team.objects.create(name="Valencia Basket Test", acronym="vbc")
        assert team.acronym == "VBC"

    def test_team_auto_slugification(self):
        team = Team.objects.create(name="Unicaja Baloncesto Málaga", acronym="UNI")
        assert team.slug == "unicaja-baloncesto-malaga"

    def test_team_arena_property(self, home_team):
        assert home_team.arena == "WiZink Center Test"

    def test_team_str_representation(self, home_team):
        assert str(home_team) == "Real Madrid Baloncesto Test (RMB)"


@pytest.mark.django_db
class TestPlayerModelAndValidations:
    """Pruebas unitarias y validaciones reglamentarias de Player."""

    def test_player_creation_valid(self, db):
        p = Player.objects.create(
            first_name="Facundo",
            last_name="Campazzo",
            birth_date=datetime.date(1991, 3, 23),
            height_cm=180,
            weight_kg=84.0,
            position=Player.Position.POINT_GUARD,
        )
        assert p.pk is not None
        p.full_clean()

    def test_player_full_name_property(self, home_players):
        p = home_players[0]
        assert p.full_name == f"{p.first_name} {p.last_name}"

    def test_player_str_representation(self, home_players):
        p = home_players[0]
        assert f"{p.full_name} ({p.get_position_display()})" == str(p)

    def test_player_clean_short_first_name_raises_validation_error(self):
        p = Player(first_name="A", last_name="Navarro", height_cm=190, weight_kg=80)
        with pytest.raises(ValidationError) as exc:
            p.clean()
        assert "first_name" in exc.value.message_dict

    def test_player_clean_short_last_name_raises_validation_error(self):
        p = Player(first_name="Juan", last_name="N", height_cm=190, weight_kg=80)
        with pytest.raises(ValidationError) as exc:
            p.clean()
        assert "last_name" in exc.value.message_dict

    def test_player_clean_height_under_120_raises_validation_error(self):
        p = Player(first_name="Juan", last_name="Navarro", height_cm=115, weight_kg=80)
        with pytest.raises(ValidationError) as exc:
            p.clean()
        assert "height_cm" in exc.value.message_dict

    def test_player_clean_height_over_245_raises_validation_error(self):
        p = Player(first_name="Juan", last_name="Navarro", height_cm=250, weight_kg=80)
        with pytest.raises(ValidationError) as exc:
            p.clean()
        assert "height_cm" in exc.value.message_dict

    def test_player_clean_weight_under_40_raises_validation_error(self):
        p = Player(first_name="Juan", last_name="Navarro", height_cm=185, weight_kg=35.0)
        with pytest.raises(ValidationError) as exc:
            p.clean()
        assert "weight_kg" in exc.value.message_dict

    def test_player_clean_weight_over_190_raises_validation_error(self):
        p = Player(first_name="Juan", last_name="Navarro", height_cm=185, weight_kg=195.0)
        with pytest.raises(ValidationError) as exc:
            p.clean()
        assert "weight_kg" in exc.value.message_dict

    def test_player_clean_future_birth_date_raises_validation_error(self):
        future = datetime.date.today() + datetime.timedelta(days=10)
        p = Player(first_name="Juan", last_name="Navarro", height_cm=185, weight_kg=80, birth_date=future)
        with pytest.raises(ValidationError) as exc:
            p.clean()
        assert "birth_date" in exc.value.message_dict

    def test_player_clean_age_under_12_raises_validation_error(self):
        too_young = datetime.date.today() - datetime.timedelta(days=365 * 10)
        p = Player(first_name="Juan", last_name="Navarro", height_cm=185, weight_kg=80, birth_date=too_young)
        with pytest.raises(ValidationError) as exc:
            p.clean()
        assert "birth_date" in exc.value.message_dict

    def test_player_clean_age_over_65_raises_validation_error(self):
        too_old = datetime.date.today() - datetime.timedelta(days=365 * 70)
        p = Player(first_name="Juan", last_name="Navarro", height_cm=185, weight_kg=80, birth_date=too_old)
        with pytest.raises(ValidationError) as exc:
            p.clean()
        assert "birth_date" in exc.value.message_dict

    def test_player_current_membership_property(self, home_players):
        p = home_players[0]
        assert p.current_membership is not None
        assert p.current_membership.jersey_number == 7

    def test_player_current_team_property(self, home_players, home_team):
        p = home_players[0]
        assert p.current_team == home_team


@pytest.mark.django_db
class TestTeamMembershipModelAndRules:
    """Pruebas unitarias para TeamMembership y reglas de asignación."""

    def test_teammembership_creation_valid(self, home_players, home_team, season):
        m = TeamMembership.objects.filter(player=home_players[0], team=home_team, season=season).first()
        assert m is not None
        assert m.jersey_number == 7
        assert m.is_captain is True

    def test_teammembership_str_representation(self, home_players, home_team, season):
        m = TeamMembership.objects.filter(player=home_players[0], team=home_team, season=season).first()
        assert f"#{m.jersey_number} {m.player.full_name} - {home_team.name} ({season.name})" == str(m)

    def test_teammembership_dorsal_negative_raises_validation_error(self, home_players, home_team, season):
        m = TeamMembership(player=home_players[0], team=home_team, season=season, jersey_number=-1)
        with pytest.raises(ValidationError) as exc:
            m.clean()
        assert "jersey_number" in exc.value.message_dict

    def test_teammembership_dorsal_over_99_raises_validation_error(self, home_players, home_team, season):
        m = TeamMembership(player=home_players[0], team=home_team, season=season, jersey_number=100)
        with pytest.raises(ValidationError) as exc:
            m.clean()
        assert "jersey_number" in exc.value.message_dict

    def test_teammembership_duplicate_dorsal_same_team_season_raises_validation_error(
        self, db, home_team, season, home_players
    ):
        p_new = Player.objects.create(first_name="Sergio", last_name="Llull", height_cm=190, weight_kg=85)
        # Dorsal 7 is already used by home_players[0]
        m = TeamMembership(player=p_new, team=home_team, season=season, jersey_number=7, is_active=True)
        with pytest.raises(ValidationError) as exc:
            m.clean()
        assert "jersey_number" in exc.value.message_dict

    def test_teammembership_same_player_multiple_active_teams_same_season_raises_validation_error(
        self, home_players, away_team, season
    ):
        p = home_players[0]  # Already active in home_team
        m = TeamMembership(player=p, team=away_team, season=season, jersey_number=99, is_active=True)
        with pytest.raises(ValidationError) as exc:
            m.clean()
        assert "ya está dado de alta" in str(exc.value)

    def test_teammembership_same_player_same_team_duplicate_active_raises_validation_error(
        self, home_players, home_team, season
    ):
        p = home_players[0]
        m = TeamMembership(player=p, team=home_team, season=season, jersey_number=99, is_active=True)
        with pytest.raises(ValidationError) as exc:
            m.clean()
        assert "ya tiene una ficha activa" in str(exc.value)


@pytest.mark.django_db
class TestTeamForms:
    """Pruebas unitarias para los formularios de equipos y jugadores."""

    def test_player_form_valid(self):
        data = {
            "first_name": "Rudy",
            "last_name": "Fernandez",
            "birth_date": "1985-04-04",
            "height_cm": 196,
            "weight_kg": 83.5,
            "position": "SF",
            "is_active": True,
        }
        form = PlayerForm(data=data)
        assert form.is_valid()
        player = form.save()
        assert player.first_name == "Rudy"

    def test_player_form_numeric_first_name_invalid(self):
        data = {
            "first_name": "Rudy123",
            "last_name": "Fernandez",
            "position": "SF",
        }
        form = PlayerForm(data=data)
        assert not form.is_valid()
        assert "first_name" in form.errors

    def test_player_form_numeric_last_name_invalid(self):
        data = {
            "first_name": "Rudy",
            "last_name": "Fernandez99",
            "position": "SF",
        }
        form = PlayerForm(data=data)
        assert not form.is_valid()
        assert "last_name" in form.errors

    def test_player_form_invalid_height(self):
        data = {
            "first_name": "Rudy",
            "last_name": "Fernandez",
            "height_cm": 300,
            "position": "SF",
        }
        form = PlayerForm(data=data)
        assert not form.is_valid()
        assert "height_cm" in form.errors

    def test_player_form_invalid_weight(self):
        data = {
            "first_name": "Rudy",
            "last_name": "Fernandez",
            "weight_kg": 25.0,
            "position": "SF",
        }
        form = PlayerForm(data=data)
        assert not form.is_valid()
        assert "weight_kg" in form.errors

    def test_team_membership_form_valid(self, db, home_team, season):
        new_player = Player.objects.create(first_name="Willy", last_name="Hernangomez", height_cm=209, weight_kg=110)
        data = {
            "player": new_player.id,
            "jersey_number": 9,
            "is_captain": False,
        }
        form = TeamMembershipForm(data=data, team=home_team, season=season)
        assert form.is_valid()

    def test_team_membership_form_duplicate_dorsal_invalid(self, db, home_team, season, home_players):
        new_player = Player.objects.create(first_name="Willy", last_name="Hernangomez", height_cm=209, weight_kg=110)
        # Dorsal 7 is taken
        data = {
            "player": new_player.id,
            "jersey_number": 7,
            "is_captain": False,
        }
        form = TeamMembershipForm(data=data, team=home_team, season=season)
        assert not form.is_valid()
        assert "__all__" in form.errors or "jersey_number" in form.errors

    def test_team_membership_form_player_already_in_team_invalid(self, home_players, home_team, season):
        p = home_players[0]
        data = {
            "player": p.id,
            "jersey_number": 98,
            "is_captain": False,
        }
        form = TeamMembershipForm(data=data, team=home_team, season=season)
        assert not form.is_valid()
        assert "__all__" in form.errors or "player" in form.errors

    def test_team_membership_form_excludes_players_active_in_other_teams(self, db, home_team, away_team, season, home_players):
        # Crear un jugador activo en away_team y un jugador libre (sin equipo)
        away_player = Player.objects.create(first_name="Alberto", last_name="Diaz", height_cm=190, weight_kg=86)
        TeamMembership.objects.create(player=away_player, team=away_team, season=season, jersey_number=9, is_active=True)

        free_player = Player.objects.create(first_name="Jugador", last_name="Libre", height_cm=195, weight_kg=90)

        form = TeamMembershipForm(team=home_team, season=season)
        available_players = list(form.fields["player"].queryset)

        # El jugador libre DEBE estar disponible
        assert free_player in available_players
        # El jugador de away_team NO debe estar disponible en el desplegable
        assert away_player not in available_players
        # Los jugadores de home_team ya activos tampoco deben estar
        for hp in home_players:
            assert hp not in available_players

        # Intentar forzar la inscripción del jugador de away_team debe dar error de validación
        post_form = TeamMembershipForm(
            data={"player": away_player.id, "jersey_number": 33, "is_captain": False},
            team=home_team,
            season=season
        )
        assert not post_form.is_valid()
        assert "__all__" in post_form.errors or "player" in post_form.errors

    def test_coach_player_create_form_valid(self, home_team, season):
        data = {
            "first_name": "Alberto",
            "last_name": "Abalde",
            "birth_date": "1995-12-15",
            "height_cm": 202,
            "weight_kg": 95.0,
            "position": "SF",
            "jersey_number": 6,
            "is_captain": False,
        }
        form = CoachPlayerCreateForm(data=data, team=home_team, season=season)
        assert form.is_valid()

    def test_coach_player_create_form_duplicate_dorsal_invalid(self, home_team, season, home_players):
        data = {
            "first_name": "Alberto",
            "last_name": "Abalde",
            "birth_date": "1995-12-15",
            "height_cm": 202,
            "weight_kg": 95.0,
            "position": "SF",
            "jersey_number": 7,  # already taken by home_players[0]
            "is_captain": False,
        }
        form = CoachPlayerCreateForm(data=data, team=home_team, season=season)
        assert not form.is_valid()
        assert "jersey_number" in form.errors

    def test_coach_player_edit_form_valid(self, home_players, home_team, season):
        p = home_players[0]
        membership = TeamMembership.objects.filter(player=p, team=home_team, season=season).first()
        data = {
            "first_name": "Facundo",
            "last_name": "Campazzo",
            "birth_date": "1991-03-23",
            "height_cm": 180,
            "weight_kg": 84.0,
            "position": "PG",
            "jersey_number": 7,  # keeping same dorsal
            "is_captain": True,
        }
        form = CoachPlayerEditForm(data=data, team=home_team, season=season, membership=membership)
        assert form.is_valid()

    def test_team_form_valid(self, home_team):
        data = {
            "name": "Real Madrid Baloncesto Actualizado",
            "acronym": "RMB",
            "city": "Madrid Capital",
            "arena_name": "Palacio de los Deportes",
            "primary_color": "#FFFFFF",
            "secondary_color": "#0000FF",
        }
        form = TeamForm(data=data, instance=home_team)
        assert form.is_valid()
        team = form.save()
        assert team.city == "Madrid Capital"
