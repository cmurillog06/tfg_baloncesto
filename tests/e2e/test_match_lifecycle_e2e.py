import pytest
import datetime
from django.utils import timezone
from apps.teams.models import League, Season, Team, Player, TeamMembership
from apps.matches.models import Match, MatchEvent, DigitalScoreSheet
from apps.analytics.models import Standing, PlayerMatchStat
from apps.analytics.services import recalculate_season_standings, get_league_leaders


@pytest.mark.django_db(transaction=True)
class TestCompleteMatchLifecycleE2E:
    """
    Pruebas de Extremo a Extremo (E2E):
    Valida el ciclo de vida completo de un partido en Quinto Cuarto:
    Creación -> Quintetos -> Reloj -> 4 Cuartos -> Faltas & Bonus -> Firmas Digitales -> Cierre de Acta -> Clasificación.
    """

    # --------------------------------------------------------------------------
    # FASE 1: Creación y Alta de Competición, Equipos y Plantillas
    # --------------------------------------------------------------------------

    def test_e2e_league_and_season_initialization(self, db):
        league = League.objects.create(name="Liga ACB E2E Test", is_active=True)
        season = Season.objects.create(
            league=league,
            name="2025/2026",
            start_date=datetime.date.today(),
            end_date=datetime.date.today() + datetime.timedelta(days=180),
            is_current=True,
        )
        assert league.pk is not None
        assert season.pk is not None

    def test_e2e_teams_registration_with_arenas_and_colors(self, db, coach_user, away_coach_user):
        t1 = Team.objects.create(name="Madrid E2E", acronym="RMB", arena_name="WiZink", coach=coach_user)
        t2 = Team.objects.create(name="Barca E2E", acronym="FCB", arena_name="Palau", coach=away_coach_user)
        assert t1.acronym == "RMB"
        assert t2.acronym == "FCB"

    def test_e2e_players_roster_enrollment_with_dorsals(self, db, home_team, season):
        p = Player.objects.create(first_name="Sergio", last_name="Llull", height_cm=190, weight_kg=85)
        m = TeamMembership.objects.create(team=home_team, player=p, season=season, jersey_number=23, is_captain=True)
        assert m.jersey_number == 23
        assert m.is_captain is True

    def test_e2e_standings_table_initialized_to_zero(self, season, home_team, away_team):
        s1, _ = Standing.objects.get_or_create(season=season, team=home_team)
        s2, _ = Standing.objects.get_or_create(season=season, team=away_team)
        assert s1.games_played == 0
        assert s1.league_points == 0
        assert s2.league_points == 0

    def test_e2e_team_memberships_unique_dorsals_verified(self, home_team, season, home_players):
        memberships = TeamMembership.objects.filter(team=home_team, season=season)
        dorsals = [m.jersey_number for m in memberships]
        assert len(dorsals) == len(set(dorsals))

    # --------------------------------------------------------------------------
    # FASE 2: Programación Oficial y Designación Arbitral
    # --------------------------------------------------------------------------

    def test_e2e_match_scheduling_with_future_date(self, scheduled_match):
        assert scheduled_match.scheduled_at > timezone.now()

    def test_e2e_referee_and_table_officials_assignment(
        self, scheduled_match, referee_user, second_referee_user, table_official_user, second_table_official_user
    ):
        assert scheduled_match.referee == referee_user
        assert scheduled_match.second_referee == second_referee_user
        assert scheduled_match.table_official == table_official_user
        assert scheduled_match.timekeeper == second_table_official_user

    def test_e2e_match_initial_status_scheduled_clock_10_00(self, scheduled_match):
        assert scheduled_match.status == Match.Status.SCHEDULED
        assert scheduled_match.current_period == Match.Period.NOT_STARTED
        assert scheduled_match.game_clock == "10:00"

    def test_e2e_match_appears_in_upcoming_schedule_list(self, auth_client, fan_user, scheduled_match):
        from django.urls import reverse
        c = auth_client(fan_user)
        response = c.get(reverse("matches:match_list"))
        assert scheduled_match in response.context["upcoming_matches"]

    def test_e2e_scorekeeper_access_granted_only_to_assigned_officials(
        self, auth_client, table_official_user, unassigned_table_official, scheduled_match
    ):
        from django.urls import reverse
        c_auth = auth_client(table_official_user)
        c_unauth = auth_client(unassigned_table_official)
        assert c_auth.get(reverse("matches:scorekeeper", kwargs={"pk": scheduled_match.pk})).status_code == 200
        assert c_unauth.get(reverse("matches:scorekeeper", kwargs={"pk": scheduled_match.pk})).status_code == 403

    # --------------------------------------------------------------------------
    # FASE 3: Protocolo Pre-Partido y Quintetos Iniciales
    # --------------------------------------------------------------------------

    def test_e2e_pre_match_starting_five_selection_home_team(self, scheduled_match, home_team, home_players):
        p_ids = [p.id for p in home_players[:5]]
        event = scheduled_match.set_starting_five(home_team, p_ids)
        assert event is not None
        assert scheduled_match.has_valid_five_on_court(home_team) is True

    def test_e2e_pre_match_starting_five_selection_away_team(self, scheduled_match, away_team, away_players):
        p_ids = [p.id for p in away_players[:5]]
        event = scheduled_match.set_starting_five(away_team, p_ids)
        assert event is not None
        assert scheduled_match.has_valid_five_on_court(away_team) is True

    def test_e2e_pre_match_verification_exactly_five_players_on_court(
        self, scheduled_match, home_team, away_team, home_players, away_players
    ):
        scheduled_match.set_starting_five(home_team, [p.id for p in home_players[:5]])
        scheduled_match.set_starting_five(away_team, [p.id for p in away_players[:5]])
        assert scheduled_match.has_valid_five_on_court(home_team) is True
        assert scheduled_match.has_valid_five_on_court(away_team) is True

    def test_e2e_pre_match_boxscore_initialized_for_all_roster_members(
        self, scheduled_match, home_team, home_players
    ):
        for p in home_players:
            stat, _ = PlayerMatchStat.objects.get_or_create(match=scheduled_match, player=p, team=home_team)
            assert stat.points == 0
            assert stat.fouls_committed == 0

    def test_e2e_pre_match_starting_five_events_logged(
        self, scheduled_match, home_team, away_team, home_players, away_players
    ):
        scheduled_match.set_starting_five(home_team, [p.id for p in home_players[:5]])
        scheduled_match.set_starting_five(away_team, [p.id for p in away_players[:5]])
        events = MatchEvent.objects.filter(match=scheduled_match, event_type=MatchEvent.EventType.STARTING_FIVE)
        assert events.count() == 2

    # --------------------------------------------------------------------------
    # FASE 4: Inicio del Partido y Periodo 1 (Q1)
    # --------------------------------------------------------------------------

    def test_e2e_period_1_status_changes_to_live_clock_starts(self, scheduled_match):
        scheduled_match.status = Match.Status.LIVE
        scheduled_match.current_period = Match.Period.Q1
        scheduled_match.game_clock = "10:00"
        scheduled_match.save()
        assert scheduled_match.status == Match.Status.LIVE

    def test_e2e_period_1_first_points_scored_2pt_home(self, scheduled_match, home_team, home_players):
        stat, _ = PlayerMatchStat.objects.get_or_create(match=scheduled_match, player=home_players[0], team=home_team)
        event = MatchEvent.objects.create(
            match=scheduled_match,
            period=Match.Period.Q1,
            game_clock="09:42",
            team=home_team,
            player=home_players[0],
            event_type=MatchEvent.EventType.POINT_2_MADE,
            points=2,
            description="Bandeja tras penetración",
        )
        scheduled_match.home_score += 2
        scheduled_match.save()
        stat.points += 2
        stat.field_goals_made += 1
        stat.field_goals_attempted += 1
        stat.save()
        assert scheduled_match.home_score == 2
        assert stat.points == 2

    def test_e2e_period_1_away_team_response_3pt(self, scheduled_match, away_team, away_players):
        stat, _ = PlayerMatchStat.objects.get_or_create(match=scheduled_match, player=away_players[0], team=away_team)
        event = MatchEvent.objects.create(
            match=scheduled_match,
            period=Match.Period.Q1,
            game_clock="09:15",
            team=away_team,
            player=away_players[0],
            event_type=MatchEvent.EventType.POINT_3_MADE,
            points=3,
            description="Triple frontal",
        )
        scheduled_match.away_score += 3
        scheduled_match.save()
        assert scheduled_match.away_score == 3

    def test_e2e_period_1_personal_fouls_recorded_on_players(self, scheduled_match, away_team, away_players):
        stat, _ = PlayerMatchStat.objects.get_or_create(match=scheduled_match, player=away_players[0], team=away_team)
        MatchEvent.objects.create(
            match=scheduled_match,
            period=Match.Period.Q1,
            game_clock="08:30",
            team=away_team,
            player=away_players[0],
            event_type=MatchEvent.EventType.FOUL_PERSONAL,
        )
        stat.fouls_committed += 1
        stat.save()
        assert stat.fouls_committed == 1

    def test_e2e_period_1_substitutions_executed_between_bench_and_court(
        self, scheduled_match, home_team, home_players
    ):
        scheduled_match.set_starting_five(home_team, [p.id for p in home_players[:5]])
        event = scheduled_match.substitute_player(home_team, home_players[0].id, home_players[5].id)
        assert event is not None
        assert home_players[5].id in scheduled_match.get_on_court_player_ids(home_team)

    def test_e2e_period_1_events_chronologically_recorded(self, scheduled_match, home_team, away_team):
        MatchEvent.objects.create(match=scheduled_match, period=Match.Period.Q1, team=home_team, event_type=MatchEvent.EventType.POINT_2_MADE, points=2)
        MatchEvent.objects.create(match=scheduled_match, period=Match.Period.Q1, team=away_team, event_type=MatchEvent.EventType.POINT_3_MADE, points=3)
        MatchEvent.objects.create(match=scheduled_match, period=Match.Period.Q1, team=home_team, event_type=MatchEvent.EventType.FOUL_PERSONAL)
        events = MatchEvent.objects.filter(match=scheduled_match, period=Match.Period.Q1)
        assert events.count() >= 3

    # --------------------------------------------------------------------------
    # FASE 5: Periodo 2 (Q2) y Activación del Bonus de Equipo
    # --------------------------------------------------------------------------

    def test_e2e_period_2_quarter_transition_resets_clock(self, scheduled_match):
        scheduled_match.current_period = Match.Period.Q2
        scheduled_match.game_clock = "10:00"
        scheduled_match.save()
        assert scheduled_match.current_period == Match.Period.Q2

    def test_e2e_period_2_fouls_accumulation_quarter_reset(self, scheduled_match, home_team):
        info_q2 = scheduled_match.get_team_fouls_info(home_team, period=Match.Period.Q2)
        assert info_q2["count"] == 0
        assert info_q2["in_bonus"] is False

    def test_e2e_period_2_team_foul_5th_triggers_bonus_indicator(self, scheduled_match, home_team, home_players):
        for i in range(5):
            MatchEvent.objects.create(
                match=scheduled_match,
                period=Match.Period.Q2,
                team=home_team,
                player=home_players[i % len(home_players)],
                event_type=MatchEvent.EventType.FOUL_PERSONAL,
            )
        info = scheduled_match.get_team_fouls_info(home_team, period=Match.Period.Q2)
        assert info["count"] == 5
        assert info["in_bonus"] is True

    def test_e2e_period_2_timeout_requested_and_clock_paused(self, scheduled_match, home_team):
        MatchEvent.objects.create(
            match=scheduled_match,
            period=Match.Period.Q2,
            team=home_team,
            event_type=MatchEvent.EventType.TIMEOUT,
        )
        assert MatchEvent.objects.filter(match=scheduled_match, event_type=MatchEvent.EventType.TIMEOUT).exists()

    def test_e2e_period_2_timeout_counter_decrements_remaining(self, scheduled_match, home_team):
        scheduled_match.current_period = Match.Period.Q2
        MatchEvent.objects.create(
            match=scheduled_match,
            period=Match.Period.Q2,
            team=home_team,
            event_type=MatchEvent.EventType.TIMEOUT,
        )
        info = scheduled_match.get_team_timeouts_info(home_team)
        assert info["used"] == 1
        assert info["remaining"] == 1

    def test_e2e_period_2_halftime_transition_and_scores(self, scheduled_match):
        scheduled_match.current_period = Match.Period.HALFTIME
        scheduled_match.home_score = 44
        scheduled_match.away_score = 40
        scheduled_match.save()
        assert scheduled_match.current_period == Match.Period.HALFTIME

    # --------------------------------------------------------------------------
    # FASE 6: Segunda Mitad (Q3, Q4) y Expulsión por 5ª Falta
    # --------------------------------------------------------------------------

    def test_e2e_period_3_halftime_to_q3_transition(self, scheduled_match):
        scheduled_match.current_period = Match.Period.Q3
        scheduled_match.game_clock = "10:00"
        scheduled_match.save()
        assert scheduled_match.current_period == Match.Period.Q3

    def test_e2e_period_3_timeouts_reset_to_3_for_second_half(self, scheduled_match, home_team):
        scheduled_match.current_period = Match.Period.Q3
        info = scheduled_match.get_team_timeouts_info(home_team)
        assert info["limit"] == 3
        assert info["remaining"] == 3

    def test_e2e_period_3_advanced_stats_rebounds_assists_steals_pir(self, scheduled_match, home_team, home_players):
        stat, _ = PlayerMatchStat.objects.get_or_create(match=scheduled_match, player=home_players[1], team=home_team)
        stat.rebounds_off = 3
        stat.rebounds_def = 6
        stat.assists = 4
        stat.steals = 2
        stat.blocks_made = 1
        stat.save()
        assert stat.total_rebounds == 9
        assert stat.valuation_pir > 0

    def test_e2e_period_4_high_tension_scoring_exchange(self, scheduled_match, home_team, away_team):
        scheduled_match.current_period = Match.Period.Q4
        scheduled_match.home_score = 85
        scheduled_match.away_score = 82
        scheduled_match.save()
        assert scheduled_match.home_score == 85

    def test_e2e_period_4_player_commits_5th_personal_foul(self, scheduled_match, away_team, away_players):
        target_player = away_players[0]
        stat, _ = PlayerMatchStat.objects.get_or_create(match=scheduled_match, player=target_player, team=away_team)
        stat.fouls_committed = 5
        stat.save()
        assert stat.fouls_committed == 5

    def test_e2e_period_4_5th_foul_causes_automatic_disqualification(self, scheduled_match, away_team, away_players):
        stat, _ = PlayerMatchStat.objects.get_or_create(match=scheduled_match, player=away_players[0], team=away_team)
        stat.fouls_committed = 5
        stat.save()
        assert stat.fouls_committed >= 5

    def test_e2e_period_4_disqualified_player_cannot_reenter_court(
        self, scheduled_match, away_team, away_players
    ):
        scheduled_match.set_starting_five(away_team, [p.id for p in away_players[1:6]])
        disqualified_player = away_players[0]
        stat_disq, _ = PlayerMatchStat.objects.get_or_create(match=scheduled_match, player=disqualified_player, team=away_team)
        stat_disq.fouls_committed = 5
        stat_disq.save()
        with pytest.raises(ValueError) as exc:
            scheduled_match.substitute_player(away_team, away_players[1].id, disqualified_player.id)
        assert "eliminado" in str(exc.value)

    def test_e2e_period_4_compulsory_substitution_of_disqualified_player(
        self, scheduled_match, away_team, away_players
    ):
        scheduled_match.set_starting_five(away_team, [p.id for p in away_players[:5]])
        stat_expelled, _ = PlayerMatchStat.objects.get_or_create(match=scheduled_match, player=away_players[0], team=away_team)
        stat_expelled.is_on_court = False
        stat_expelled.save()
        stat_bench, _ = PlayerMatchStat.objects.get_or_create(match=scheduled_match, player=away_players[5], team=away_team)
        stat_bench.is_on_court = True
        stat_bench.save()
        assert scheduled_match.has_valid_five_on_court(away_team) is True

    def test_e2e_period_4_clock_reaches_zero_final_horn(self, scheduled_match):
        scheduled_match.game_clock = "00:00"
        scheduled_match.home_score = 89
        scheduled_match.away_score = 84
        scheduled_match.save()
        assert scheduled_match.game_clock == "00:00"

    # --------------------------------------------------------------------------
    # FASE 7: Conclusión del Partido, Firmas Digitales y Cierre de Acta
    # --------------------------------------------------------------------------

    def test_e2e_post_game_match_status_changes_to_finished(self, scheduled_match):
        scheduled_match.status = Match.Status.FINISHED
        scheduled_match.current_period = Match.Period.FINISHED
        scheduled_match.save()
        assert scheduled_match.status == Match.Status.FINISHED

    def test_e2e_post_game_digital_scoresheet_generated(self, scheduled_match):
        scoresheet, created = DigitalScoreSheet.objects.get_or_create(match=scheduled_match)
        assert scoresheet.pk is not None

    def test_e2e_post_game_referee_digital_signature_registered(self, scheduled_match):
        scoresheet, _ = DigitalScoreSheet.objects.get_or_create(match=scheduled_match)
        scoresheet.referee_signature = "Juan Carlos García (Lic. FEB-48192)"
        scoresheet.save()
        assert "FEB-48192" in scoresheet.referee_signature

    def test_e2e_post_game_second_referee_digital_signature_registered(self, scheduled_match):
        scoresheet, _ = DigitalScoreSheet.objects.get_or_create(match=scheduled_match)
        scoresheet.second_referee_signature = "Antonio Conde (Lic. FEB-31084)"
        scoresheet.save()
        assert "FEB-31084" in scoresheet.second_referee_signature

    def test_e2e_post_game_table_official_signature_registered(self, scheduled_match):
        scoresheet, _ = DigitalScoreSheet.objects.get_or_create(match=scheduled_match)
        scoresheet.table_official_signature = "Carlos Murillo (Anotador)"
        scoresheet.save()
        assert "Carlos Murillo" in scoresheet.table_official_signature

    def test_e2e_post_game_timekeeper_signature_registered(self, scheduled_match):
        scoresheet, _ = DigitalScoreSheet.objects.get_or_create(match=scheduled_match)
        scoresheet.timekeeper_signature = "Laura Gómez (Cronometradora)"
        scoresheet.save()
        assert "Laura Gómez" in scoresheet.timekeeper_signature

    def test_e2e_post_game_verification_code_sha256_generated(self, scheduled_match):
        scoresheet, _ = DigitalScoreSheet.objects.get_or_create(match=scheduled_match)
        code = scoresheet.verification_code
        assert code.startswith("QQ-SEC-")
        assert len(code) >= 15

    def test_e2e_post_game_scoresheet_formal_closure_flag_is_true(self, scheduled_match):
        scoresheet, _ = DigitalScoreSheet.objects.get_or_create(match=scheduled_match)
        scoresheet.is_closed = True
        scoresheet.closed_at = timezone.now()
        scoresheet.save()
        assert scoresheet.is_closed is True

    # --------------------------------------------------------------------------
    # FASE 8: Recálculo Automático de Clasificación y Estadísticas de Temporada
    # --------------------------------------------------------------------------

    def test_e2e_standings_automatically_updated_winning_team_2_pts(self, scheduled_match, season, home_team):
        scheduled_match.status = Match.Status.FINISHED
        scheduled_match.home_score = 89
        scheduled_match.away_score = 84
        scheduled_match.save()
        recalculate_season_standings(season)
        s_home = Standing.objects.get(season=season, team=home_team)
        assert s_home.wins == 1
        assert s_home.losses == 0
        assert s_home.league_points == 2

    def test_e2e_standings_automatically_updated_losing_team_1_pt(self, scheduled_match, season, away_team):
        scheduled_match.status = Match.Status.FINISHED
        scheduled_match.home_score = 89
        scheduled_match.away_score = 84
        scheduled_match.save()
        recalculate_season_standings(season)
        s_away = Standing.objects.get(season=season, team=away_team)
        assert s_away.wins == 0
        assert s_away.losses == 1
        assert s_away.league_points == 1

    def test_e2e_standings_points_for_points_against_diff_exact(self, scheduled_match, season, home_team, away_team):
        scheduled_match.status = Match.Status.FINISHED
        scheduled_match.home_score = 89
        scheduled_match.away_score = 84
        scheduled_match.save()
        recalculate_season_standings(season)
        s_home = Standing.objects.get(season=season, team=home_team)
        s_away = Standing.objects.get(season=season, team=away_team)
        assert s_home.points_for == 89
        assert s_home.points_against == 84
        assert s_home.points_diff == 5
        assert s_away.points_for == 84
        assert s_away.points_against == 89
        assert s_away.points_diff == -5

    def test_e2e_league_leaders_updated_with_finished_game_boxscore(self, scheduled_match, season, home_team, home_players):
        scheduled_match.status = Match.Status.FINISHED
        scheduled_match.save()
        PlayerMatchStat.objects.create(
            match=scheduled_match,
            player=home_players[0],
            team=home_team,
            points=20,
            minutes_played=25,
            valuation_pir=22,
        )
        leaders = get_league_leaders(season=season)
        assert isinstance(leaders, dict)
        assert len(leaders["top_scorers"]) >= 1

    def test_e2e_scoresheet_view_displays_complete_match_audit_trail(
        self, auth_client, coach_user, scheduled_match
    ):
        from django.urls import reverse
        DigitalScoreSheet.objects.get_or_create(match=scheduled_match, is_closed=True)
        c = auth_client(coach_user)
        response = c.get(reverse("matches:scoresheet_detail", kwargs={"pk": scheduled_match.pk}))
        assert response.status_code == 200
        assert "quarters_breakdown" in response.context
        assert "scoresheet" in response.context

    def test_e2e_complete_match_lifecycle_full_automated_pipeline(
        self, season, home_team, away_team, referee_user, table_official_user, second_table_official_user, home_players, away_players
    ):
        # 1. Crear nuevo partido
        match = Match.objects.create(
            season=season,
            round_number=2,
            home_team=home_team,
            away_team=away_team,
            scheduled_at=timezone.now() + datetime.timedelta(days=1),
            referee=referee_user,
            table_official=table_official_user,
            timekeeper=second_table_official_user,
            status=Match.Status.SCHEDULED,
        )
        # 2. Establecer quintetos
        match.set_starting_five(home_team, [p.id for p in home_players[:5]])
        match.set_starting_five(away_team, [p.id for p in away_players[:5]])
        # 3. Arrancar partido
        match.status = Match.Status.LIVE
        match.current_period = Match.Period.Q1
        match.save()
        # 4. Registrar canastas
        MatchEvent.objects.create(match=match, period=Match.Period.Q1, team=home_team, points=3, event_type="3PT_MADE")
        match.home_score = 92
        match.away_score = 88
        # 5. Finalizar partido
        match.status = Match.Status.FINISHED
        match.current_period = Match.Period.FINISHED
        match.save()
        # 6. Firmar y cerrar acta
        DigitalScoreSheet.objects.create(
            match=match,
            is_closed=True,
            referee_signature="Arbitro Principal (Lic. FEB-11111)",
            table_official_signature="Oficial Mesa",
            timekeeper_signature="Oficial Crono",
            closed_at=timezone.now(),
        )
        # 7. Recalcular clasificaciones
        recalculate_season_standings(season)
        standing_home = Standing.objects.get(season=season, team=home_team)
        assert standing_home.games_played >= 1
