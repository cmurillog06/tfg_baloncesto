import pytest
import datetime
from django.utils import timezone
from django.test import Client
from apps.accounts.models import CustomUser, Profile
from apps.teams.models import League, Season, Team, Player, TeamMembership
from apps.matches.models import Match, MatchEvent, DigitalScoreSheet
from apps.analytics.models import Standing, PlayerMatchStat


@pytest.fixture
def admin_user(db):
    user = CustomUser.objects.create_superuser(
        username="admin_test",
        email="admin_test@quintocuarto.es",
        password="AdminPassword123!",
        first_name="Admin",
        last_name="QuintoCuarto",
        role=CustomUser.Role.ADMIN,
    )
    return user


@pytest.fixture
def table_official_user(db):
    user = CustomUser.objects.create_user(
        username="mesa_anotador",
        email="mesa_anotador@quintocuarto.es",
        password="MesaPassword123!",
        first_name="Carlos",
        last_name="Anotador",
        role=CustomUser.Role.TABLE_OFFICIAL,
    )
    return user


@pytest.fixture
def second_table_official_user(db):
    user = CustomUser.objects.create_user(
        username="mesa_crono",
        email="mesa_crono@quintocuarto.es",
        password="CronoPassword123!",
        first_name="Laura",
        last_name="Cronometradora",
        role=CustomUser.Role.TABLE_OFFICIAL,
    )
    return user


@pytest.fixture
def unassigned_table_official(db):
    user = CustomUser.objects.create_user(
        username="mesa_externo",
        email="mesa_externo@quintocuarto.es",
        password="ExternoPassword123!",
        first_name="Oficial",
        last_name="Externo",
        role=CustomUser.Role.TABLE_OFFICIAL,
    )
    return user


@pytest.fixture
def referee_user(db):
    user = CustomUser.objects.create_user(
        username="arbitro_principal",
        email="arbitro_principal@quintocuarto.es",
        password="RefereePassword123!",
        first_name="Juan Carlos",
        last_name="García",
        role=CustomUser.Role.REFEREE,
    )
    return user


@pytest.fixture
def second_referee_user(db):
    user = CustomUser.objects.create_user(
        username="arbitro_auxiliar",
        email="arbitro_auxiliar@quintocuarto.es",
        password="Referee2Password123!",
        first_name="Antonio",
        last_name="Conde",
        role=CustomUser.Role.REFEREE,
    )
    return user


@pytest.fixture
def coach_user(db):
    user = CustomUser.objects.create_user(
        username="coach_local",
        email="coach_local@quintocuarto.es",
        password="CoachPassword123!",
        first_name="Pablo",
        last_name="Laso",
        role=CustomUser.Role.COACH,
    )
    return user


@pytest.fixture
def away_coach_user(db):
    user = CustomUser.objects.create_user(
        username="coach_visitante",
        email="coach_visitante@quintocuarto.es",
        password="CoachAwayPassword123!",
        first_name="Sarunas",
        last_name="Jasikevicius",
        role=CustomUser.Role.COACH,
    )
    return user


@pytest.fixture
def fan_user(db):
    user = CustomUser.objects.create_user(
        username="aficionado_fan",
        email="aficionado_fan@quintocuarto.es",
        password="FanPassword123!",
        first_name="Miguel",
        last_name="Aficionado",
        role=CustomUser.Role.FAN,
    )
    return user


@pytest.fixture
def league(db):
    return League.objects.create(
        name="Liga Senior Oro Test",
        description="Liga de prueba para el banco de pruebas automatizadas.",
        is_active=True,
    )


@pytest.fixture
def season(db, league):
    today = datetime.date.today()
    return Season.objects.create(
        league=league,
        name="Temporada 2025/2026",
        start_date=today - datetime.timedelta(days=60),
        end_date=today + datetime.timedelta(days=120),
        is_current=True,
    )


@pytest.fixture
def home_team(db, coach_user):
    return Team.objects.create(
        name="Real Madrid Baloncesto Test",
        acronym="RMB",
        city="Madrid",
        arena_name="WiZink Center Test",
        primary_color="#5D2A8A",
        secondary_color="#FFB81C",
        coach=coach_user,
    )


@pytest.fixture
def away_team(db, away_coach_user):
    return Team.objects.create(
        name="FC Barcelona Basket Test",
        acronym="FCB",
        city="Barcelona",
        arena_name="Palau Blaugrana Test",
        primary_color="#004D98",
        secondary_color="#A50044",
        coach=away_coach_user,
    )


@pytest.fixture
def home_players(db, home_team, season):
    positions = [
        Player.Position.POINT_GUARD,
        Player.Position.SHOOTING_GUARD,
        Player.Position.SMALL_FORWARD,
        Player.Position.POWER_FORWARD,
        Player.Position.CENTER,
        Player.Position.POINT_GUARD,
    ]
    dorsals = [7, 23, 5, 22, 11, 13]
    players = []
    for i in range(6):
        p = Player.objects.create(
            first_name=f"JugadorLocal{i+1}",
            last_name=f"Madrid{i+1}",
            birth_date=datetime.date(1995, 1, 10 + i),
            height_cm=185 + (i * 5),
            weight_kg=80.0 + (i * 4),
            position=positions[i],
            is_active=True,
        )
        TeamMembership.objects.create(
            team=home_team,
            player=p,
            season=season,
            jersey_number=dorsals[i],
            is_captain=(i == 0),
            is_active=True,
        )
        players.append(p)
    return players


@pytest.fixture
def away_players(db, away_team, season):
    positions = [
        Player.Position.POINT_GUARD,
        Player.Position.SHOOTING_GUARD,
        Player.Position.SMALL_FORWARD,
        Player.Position.POWER_FORWARD,
        Player.Position.CENTER,
        Player.Position.CENTER,
    ]
    dorsals = [10, 21, 33, 14, 44, 9]
    players = []
    for i in range(6):
        p = Player.objects.create(
            first_name=f"JugadorVis{i+1}",
            last_name=f"Barca{i+1}",
            birth_date=datetime.date(1996, 2, 10 + i),
            height_cm=188 + (i * 4),
            weight_kg=82.0 + (i * 3.5),
            position=positions[i],
            is_active=True,
        )
        TeamMembership.objects.create(
            team=away_team,
            player=p,
            season=season,
            jersey_number=dorsals[i],
            is_captain=(i == 0),
            is_active=True,
        )
        players.append(p)
    return players


@pytest.fixture
def standings_setup(db, season, home_team, away_team, home_players, away_players):
    s1, _ = Standing.objects.get_or_create(
        season=season,
        team=home_team,
        defaults={"wins": 0, "losses": 0, "points_for": 0, "points_against": 0},
    )
    s2, _ = Standing.objects.get_or_create(
        season=season,
        team=away_team,
        defaults={"wins": 0, "losses": 0, "points_for": 0, "points_against": 0},
    )
    return s1, s2


@pytest.fixture
def scheduled_match(
    db,
    season,
    home_team,
    away_team,
    referee_user,
    second_referee_user,
    table_official_user,
    second_table_official_user,
    standings_setup,
):
    future_time = timezone.now() + datetime.timedelta(days=2)
    return Match.objects.create(
        season=season,
        round_number=1,
        home_team=home_team,
        away_team=away_team,
        scheduled_at=future_time,
        location=home_team.arena_name,
        status=Match.Status.SCHEDULED,
        current_period=Match.Period.NOT_STARTED,
        game_clock="10:00",
        home_score=0,
        away_score=0,
        referee=referee_user,
        second_referee=second_referee_user,
        table_official=table_official_user,
        timekeeper=second_table_official_user,
    )


@pytest.fixture
def live_match(
    db,
    season,
    home_team,
    away_team,
    referee_user,
    second_referee_user,
    table_official_user,
    second_table_official_user,
    home_players,
    away_players,
    standings_setup,
):
    now_time = timezone.now() + datetime.timedelta(hours=1)
    match = Match.objects.create(
        season=season,
        round_number=1,
        home_team=home_team,
        away_team=away_team,
        scheduled_at=now_time,
        location=home_team.arena_name,
        status=Match.Status.LIVE,
        current_period=Match.Period.Q1,
        game_clock="08:30",
        home_score=12,
        away_score=8,
        referee=referee_user,
        second_referee=second_referee_user,
        table_official=table_official_user,
        timekeeper=second_table_official_user,
    )
    # Configure starting 5 for home and away
    home_ids = [p.id for p in home_players[:5]]
    away_ids = [p.id for p in away_players[:5]]
    match.set_starting_five(home_team, home_ids)
    match.set_starting_five(away_team, away_ids)
    return match


@pytest.fixture
def finished_match(
    db,
    season,
    home_team,
    away_team,
    referee_user,
    second_referee_user,
    table_official_user,
    second_table_official_user,
    home_players,
    away_players,
    standings_setup,
):
    past_time = timezone.now() - datetime.timedelta(days=1)
    match = Match.objects.create(
        season=season,
        round_number=1,
        home_team=home_team,
        away_team=away_team,
        scheduled_at=past_time,
        location=home_team.arena_name,
        status=Match.Status.FINISHED,
        current_period=Match.Period.FINISHED,
        game_clock="00:00",
        home_score=88,
        away_score=82,
        referee=referee_user,
        second_referee=second_referee_user,
        table_official=table_official_user,
        timekeeper=second_table_official_user,
    )
    DigitalScoreSheet.objects.create(
        match=match,
        is_closed=True,
        referee_signature="Juan Carlos García (Lic. FEB-48192)",
        second_referee_signature="Antonio Conde (Lic. FEB-31084)",
        table_official_signature="Carlos Anotador (Mesa)",
        timekeeper_signature="Laura Crono (Mesa)",
        incidents_report="Sin incidencias en el encuentro.",
        closed_at=past_time + datetime.timedelta(hours=2),
    )
    return match


@pytest.fixture
def auth_client():
    def _auth_client(user):
        client = Client()
        client.force_login(user)
        return client
    return _auth_client
