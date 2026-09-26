import pytest
import datetime
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.matches.models import Match, MatchEvent, DigitalScoreSheet
from apps.teams.models import Team, Player
from apps.analytics.models import PlayerMatchStat


@pytest.mark.django_db
class TestMatchModelAndSchedulingRules:
    """Pruebas unitarias para Match y reglas de programación."""

    def test_match_creation_and_fields(self, scheduled_match):
        assert scheduled_match.pk is not None
        assert scheduled_match.status == Match.Status.SCHEDULED
        assert scheduled_match.home_score == 0
        assert scheduled_match.away_score == 0

    def test_match_str_representation(self, scheduled_match):
        assert "RMB 0 - 0 FCB (Programado)" in str(scheduled_match)

    def test_match_clean_same_team_raises_validation_error(self, home_team, season):
        future = timezone.now() + datetime.timedelta(days=2)
        match = Match(
            season=season,
            home_team=home_team,
            away_team=home_team,
            scheduled_at=future,
        )
        with pytest.raises(ValidationError) as exc:
            match.clean()
        assert "away_team" in exc.value.message_dict

    def test_match_clean_past_scheduled_date_raises_validation_error(self, home_team, away_team, season):
        past = timezone.now() - datetime.timedelta(days=2)
        match = Match(
            season=season,
            home_team=home_team,
            away_team=away_team,
            scheduled_at=past,
        )
        with pytest.raises(ValidationError) as exc:
            match.clean()
        assert "scheduled_at" in exc.value.message_dict

    def test_match_clean_team_not_in_season_raises_validation_error(self, home_team, season, home_players):
        other_team = Team.objects.create(name="Equipo Forastero", acronym="EFO")
        future = timezone.now() + datetime.timedelta(days=2)
        match = Match(
            season=season,
            home_team=home_team,
            away_team=other_team,
            scheduled_at=future,
        )
        with pytest.raises(ValidationError) as exc:
            match.clean()
        assert "away_team" in exc.value.message_dict


@pytest.mark.django_db
class TestFIBATimeoutRules:
    """Pruebas unitarias para las reglas de tiempos muertos según reglamento FIBA."""

    def test_timeouts_info_q1_initial_state_limit_2(self, live_match, home_team):
        live_match.current_period = Match.Period.Q1
        info = live_match.get_team_timeouts_info(home_team)
        assert info["limit"] == 2
        assert info["used"] == 0
        assert info["remaining"] == 2
        assert info["can_request"] is True

    def test_timeouts_info_q2_shares_first_half_limit_2(self, live_match, home_team):
        live_match.current_period = Match.Period.Q2
        info = live_match.get_team_timeouts_info(home_team)
        assert info["limit"] == 2
        assert info["used"] == 0
        assert info["remaining"] == 2

    def test_timeouts_info_first_half_used_1_remaining_1(self, live_match, home_team):
        live_match.current_period = Match.Period.Q1
        MatchEvent.objects.create(
            match=live_match,
            period=Match.Period.Q1,
            team=home_team,
            event_type=MatchEvent.EventType.TIMEOUT,
        )
        info = live_match.get_team_timeouts_info(home_team)
        assert info["used"] == 1
        assert info["remaining"] == 1
        assert info["can_request"] is True

    def test_timeouts_info_first_half_used_2_remaining_0(self, live_match, home_team):
        live_match.current_period = Match.Period.Q2
        MatchEvent.objects.create(
            match=live_match, period=Match.Period.Q1, team=home_team, event_type=MatchEvent.EventType.TIMEOUT
        )
        MatchEvent.objects.create(
            match=live_match, period=Match.Period.Q2, team=home_team, event_type=MatchEvent.EventType.TIMEOUT
        )
        info = live_match.get_team_timeouts_info(home_team)
        assert info["used"] == 2
        assert info["remaining"] == 0
        assert info["can_request"] is False

    def test_timeouts_info_q3_second_half_limit_3(self, live_match, home_team):
        live_match.current_period = Match.Period.Q3
        info = live_match.get_team_timeouts_info(home_team)
        assert info["limit"] == 3
        assert info["remaining"] == 3

    def test_timeouts_info_q4_shares_second_half_limit_3(self, live_match, home_team):
        live_match.current_period = Match.Period.Q4
        info = live_match.get_team_timeouts_info(home_team)
        assert info["limit"] == 3

    def test_timeouts_info_second_half_used_2_remaining_1(self, live_match, home_team):
        live_match.current_period = Match.Period.Q4
        MatchEvent.objects.create(
            match=live_match, period=Match.Period.Q3, team=home_team, event_type=MatchEvent.EventType.TIMEOUT
        )
        MatchEvent.objects.create(
            match=live_match, period=Match.Period.Q4, team=home_team, event_type=MatchEvent.EventType.TIMEOUT
        )
        info = live_match.get_team_timeouts_info(home_team)
        assert info["used"] == 2
        assert info["remaining"] == 1
        assert info["can_request"] is True

    def test_timeouts_info_second_half_used_3_remaining_0(self, live_match, home_team):
        live_match.current_period = Match.Period.Q4
        MatchEvent.objects.create(
            match=live_match, period=Match.Period.Q3, team=home_team, event_type=MatchEvent.EventType.TIMEOUT
        )
        MatchEvent.objects.create(
            match=live_match, period=Match.Period.Q3, team=home_team, event_type=MatchEvent.EventType.TIMEOUT
        )
        MatchEvent.objects.create(
            match=live_match, period=Match.Period.Q4, team=home_team, event_type=MatchEvent.EventType.TIMEOUT
        )
        info = live_match.get_team_timeouts_info(home_team)
        assert info["used"] == 3
        assert info["remaining"] == 0
        assert info["can_request"] is False

    def test_timeouts_info_ot1_limit_1(self, live_match, home_team):
        live_match.current_period = Match.Period.OT1
        info = live_match.get_team_timeouts_info(home_team)
        assert info["limit"] == 1
        assert info["remaining"] == 1

    def test_timeouts_info_ot2_limit_1(self, live_match, home_team):
        live_match.current_period = Match.Period.OT2
        info = live_match.get_team_timeouts_info(home_team)
        assert info["limit"] == 1
        assert info["remaining"] == 1

    def test_timeouts_info_can_request_true_when_live_and_remaining(self, live_match, home_team):
        live_match.status = Match.Status.LIVE
        info = live_match.get_team_timeouts_info(home_team)
        assert info["can_request"] is True

    def test_timeouts_info_can_request_false_when_not_live(self, scheduled_match, home_team):
        info = scheduled_match.get_team_timeouts_info(home_team)
        assert info["can_request"] is False

    def test_timeouts_info_can_request_false_when_zero_remaining(self, live_match, home_team):
        live_match.current_period = Match.Period.Q1
        MatchEvent.objects.create(
            match=live_match, period=Match.Period.Q1, team=home_team, event_type=MatchEvent.EventType.TIMEOUT
        )
        MatchEvent.objects.create(
            match=live_match, period=Match.Period.Q1, team=home_team, event_type=MatchEvent.EventType.TIMEOUT
        )
        info = live_match.get_team_timeouts_info(home_team)
        assert info["can_request"] is False


@pytest.mark.django_db
class TestFIBATeamFoulsAndBonus:
    """Pruebas unitarias para faltas de equipo y activación de Bonus FIBA."""

    def test_team_fouls_initial_state_zero_fouls_no_bonus(self, live_match, home_team):
        info = live_match.get_team_fouls_info(home_team)
        assert info["count"] == 0
        assert info["in_bonus"] is False
        assert info["remaining_to_bonus"] == 5

    def test_team_fouls_1_foul_no_bonus(self, live_match, home_team, home_players):
        MatchEvent.objects.create(
            match=live_match,
            period=Match.Period.Q1,
            team=home_team,
            player=home_players[0],
            event_type=MatchEvent.EventType.FOUL_PERSONAL,
        )
        info = live_match.get_team_fouls_info(home_team)
        assert info["count"] == 1
        assert info["in_bonus"] is False
        assert info["remaining_to_bonus"] == 4

    def test_team_fouls_4_fouls_limit_reached_no_bonus_yet(self, live_match, home_team, home_players):
        for i in range(4):
            MatchEvent.objects.create(
                match=live_match,
                period=Match.Period.Q1,
                team=home_team,
                player=home_players[i % len(home_players)],
                event_type=MatchEvent.EventType.FOUL_PERSONAL,
            )
        info = live_match.get_team_fouls_info(home_team)
        assert info["count"] == 4
        assert info["in_bonus"] is False
        assert info["remaining_to_bonus"] == 1

    def test_team_fouls_5_fouls_triggers_bonus(self, live_match, home_team, home_players):
        for i in range(5):
            MatchEvent.objects.create(
                match=live_match,
                period=Match.Period.Q1,
                team=home_team,
                player=home_players[i % len(home_players)],
                event_type=MatchEvent.EventType.FOUL_PERSONAL,
            )
        info = live_match.get_team_fouls_info(home_team)
        assert info["count"] == 5
        assert info["in_bonus"] is True
        assert info["remaining_to_bonus"] == 0

    def test_team_fouls_6_fouls_remains_in_bonus(self, live_match, home_team, home_players):
        for i in range(6):
            MatchEvent.objects.create(
                match=live_match,
                period=Match.Period.Q1,
                team=home_team,
                player=home_players[i % len(home_players)],
                event_type=MatchEvent.EventType.FOUL_PERSONAL,
            )
        info = live_match.get_team_fouls_info(home_team)
        assert info["count"] == 6
        assert info["in_bonus"] is True

    def test_team_fouls_resets_per_quarter(self, live_match, home_team, home_players):
        for i in range(5):
            MatchEvent.objects.create(
                match=live_match,
                period=Match.Period.Q1,
                team=home_team,
                player=home_players[i % len(home_players)],
                event_type=MatchEvent.EventType.FOUL_PERSONAL,
            )
        # In Q1 is in bonus
        assert live_match.get_team_fouls_info(home_team, period=Match.Period.Q1)["in_bonus"] is True
        # In Q2 is 0 fouls, not in bonus
        assert live_match.get_team_fouls_info(home_team, period=Match.Period.Q2)["in_bonus"] is False
        assert live_match.get_team_fouls_info(home_team, period=Match.Period.Q2)["count"] == 0

    def test_team_fouls_includes_technical_and_unsportsmanlike(self, live_match, home_team, home_players):
        MatchEvent.objects.create(
            match=live_match,
            period=Match.Period.Q1,
            team=home_team,
            player=home_players[0],
            event_type=MatchEvent.EventType.FOUL_TECHNICAL,
        )
        MatchEvent.objects.create(
            match=live_match,
            period=Match.Period.Q1,
            team=home_team,
            player=home_players[1],
            event_type=MatchEvent.EventType.FOUL_UNSPORTSMANLIKE,
        )
        info = live_match.get_team_fouls_info(home_team, period=Match.Period.Q1)
        assert info["count"] == 2


@pytest.mark.django_db
class TestFIBAPlayersOnCourtAndSubstitutions:
    """Pruebas unitarias para quintetos iniciales y sustituciones FIBA."""

    def test_get_on_court_player_ids_returns_active_players(self, live_match, home_team):
        ids = live_match.get_on_court_player_ids(home_team)
        assert len(ids) == 5

    def test_has_valid_five_on_court_true_when_five(self, live_match, home_team):
        assert live_match.has_valid_five_on_court(home_team) is True

    def test_has_valid_five_on_court_false_when_less_than_five(self, live_match, home_team):
        PlayerMatchStat.objects.filter(match=live_match, team=home_team).update(is_on_court=False)
        assert live_match.has_valid_five_on_court(home_team) is False

    def test_set_starting_five_success(self, scheduled_match, home_team, home_players):
        p_ids = [p.id for p in home_players[:5]]
        event = scheduled_match.set_starting_five(home_team, p_ids)
        assert event is not None
        assert scheduled_match.has_valid_five_on_court(home_team) is True

    def test_set_starting_five_invalid_count_raises_value_error(self, scheduled_match, home_team, home_players):
        p_ids = [p.id for p in home_players[:3]]  # Only 3
        with pytest.raises(ValueError):
            scheduled_match.set_starting_five(home_team, p_ids)

    def test_set_starting_five_creates_starting_five_event(self, scheduled_match, home_team, home_players):
        p_ids = [p.id for p in home_players[:5]]
        scheduled_match.set_starting_five(home_team, p_ids)
        event = MatchEvent.objects.filter(
            match=scheduled_match, event_type=MatchEvent.EventType.STARTING_FIVE
        ).first()
        assert event is not None
        assert "Quinteto" in event.description

    def test_substitute_player_success(self, live_match, home_team, home_players):
        on_court = home_players[0]
        on_bench = home_players[5]
        event = live_match.substitute_player(home_team, on_court.id, on_bench.id)
        assert event is not None
        assert on_bench.id in live_match.get_on_court_player_ids(home_team)
        assert on_court.id not in live_match.get_on_court_player_ids(home_team)

    def test_substitute_player_not_on_court_raises_value_error(self, live_match, home_team, home_players):
        on_bench = home_players[5]
        with pytest.raises(ValueError):
            live_match.substitute_player(home_team, on_bench.id, home_players[0].id)

    def test_substitute_player_already_on_court_raises_value_error(self, live_match, home_team, home_players):
        on_court1 = home_players[0]
        on_court2 = home_players[1]
        with pytest.raises(ValueError):
            live_match.substitute_player(home_team, on_court1.id, on_court2.id)

    def test_substitute_player_with_5_fouls_disqualified_raises_value_error(
        self, live_match, home_team, home_players
    ):
        on_court = home_players[0]
        on_bench = home_players[5]
        stat, _ = PlayerMatchStat.objects.get_or_create(match=live_match, player=on_bench, team=home_team)
        stat.fouls_committed = 5
        stat.save()
        with pytest.raises(ValueError) as exc:
            live_match.substitute_player(home_team, on_court.id, on_bench.id)
        assert "eliminado" in str(exc.value)

    def test_substitute_player_creates_substitution_event(self, live_match, home_team, home_players):
        on_court = home_players[0]
        on_bench = home_players[5]
        live_match.substitute_player(home_team, on_court.id, on_bench.id)
        event = MatchEvent.objects.filter(
            match=live_match, event_type=MatchEvent.EventType.SUBSTITUTION
        ).first()
        assert event is not None
        assert "Sustitución" in event.description


@pytest.mark.django_db
class TestMatchEventsAndScoresheet:
    """Pruebas unitarias para MatchEvent y DigitalScoreSheet."""

    def test_match_event_creation_and_fields(self, live_match, home_team, home_players):
        event = MatchEvent.objects.create(
            match=live_match,
            period=Match.Period.Q1,
            game_clock="05:20",
            team=home_team,
            player=home_players[0],
            event_type=MatchEvent.EventType.POINT_3_MADE,
            points=3,
            description="Triple anotado desde la esquina",
        )
        assert event.pk is not None
        assert event.points == 3

    def test_match_event_str_representation(self, live_match, home_team, home_players):
        event = MatchEvent.objects.create(
            match=live_match,
            period=Match.Period.Q1,
            game_clock="05:20",
            team=home_team,
            player=home_players[0],
            event_type=MatchEvent.EventType.POINT_2_MADE,
            points=2,
        )
        assert "RMB" in str(event)
        assert "Canasta de 2 Anotada" in str(event)

    def test_match_event_ordering(self, live_match, home_team):
        e1 = MatchEvent.objects.create(match=live_match, period=Match.Period.Q1, team=home_team, event_type=MatchEvent.EventType.POINT_2_MADE, points=2)
        e2 = MatchEvent.objects.create(match=live_match, period=Match.Period.Q1, team=home_team, event_type=MatchEvent.EventType.POINT_3_MADE, points=3)
        events = list(MatchEvent.objects.filter(match=live_match))
        assert events[0].id == e2.id  # Ordering -created_at

    def test_get_quarters_breakdown_with_recorded_events(self, live_match, home_team, away_team):
        MatchEvent.objects.create(match=live_match, period=Match.Period.Q1, team=home_team, points=20, event_type=MatchEvent.EventType.POINT_2_MADE)
        MatchEvent.objects.create(match=live_match, period=Match.Period.Q1, team=away_team, points=18, event_type=MatchEvent.EventType.POINT_2_MADE)
        breakdown = live_match.get_quarters_breakdown()
        assert len(breakdown["periods"]) >= 4
        q1 = breakdown["periods"][0]
        assert q1["home_pts"] == 20
        assert q1["away_pts"] == 18

    def test_get_quarters_breakdown_fallback_proportional(self, finished_match):
        breakdown = finished_match.get_quarters_breakdown()
        assert breakdown["home_total"] == 88
        assert breakdown["away_total"] == 82
        assert len(breakdown["periods"]) == 4

    def test_digital_scoresheet_creation_and_fields(self, finished_match):
        scoresheet = finished_match.scoresheet
        assert scoresheet.is_closed is True
        assert "FEB-48192" in scoresheet.referee_signature

    def test_digital_scoresheet_str_representation(self, finished_match):
        assert f"Acta Oficial - {finished_match}" == str(finished_match.scoresheet)

    def test_digital_scoresheet_referee_name_and_license_properties(self, finished_match):
        scoresheet = finished_match.scoresheet
        assert "Juan Carlos García" in scoresheet.referee_name
        assert "FEB-48192" in scoresheet.referee_license
        assert "Antonio Conde" in scoresheet.second_referee_name
        assert "FEB-31084" in scoresheet.second_referee_license

    def test_digital_scoresheet_verification_code_format(self, finished_match):
        code = finished_match.scoresheet.verification_code
        assert code.startswith("QQ-SEC-")
        assert len(code) > 10


@pytest.mark.django_db
class TestScheduleGenerator:
    """Pruebas unitarias para el generador inteligente de calendarios deportivos oficiales."""

    def test_historical_season_cannot_generate_schedule(self, season):
        from apps.matches.generator import generate_season_schedule
        season.is_current = False
        season.save()
        with pytest.raises(ValueError) as exc:
            generate_season_schedule(season)
        assert "temporada histórica finalizada" in str(exc.value)

    def test_generate_schedule_new_season_full_rounds(self, season, home_team, away_team):
        from apps.matches.generator import generate_season_schedule
        from apps.analytics.models import Standing
        season.is_current = True
        season.save()
        Standing.objects.get_or_create(season=season, team=home_team, defaults={"points_for": 0, "points_against": 0})
        Standing.objects.get_or_create(season=season, team=away_team, defaults={"points_for": 0, "points_against": 0})

        result = generate_season_schedule(season, double_round=True, dry_run=False, clear_existing=True)
        assert result["total_teams"] == 2
        assert result["total_rounds"] == 2
        assert result["total_matches"] == 2
        assert result["already_played_rounds"] == 0

        matches = Match.objects.filter(season=season)
        assert matches.count() == 2
        assert matches.filter(round_number=1).count() == 1
        assert matches.filter(round_number=2).count() == 1

    def test_generate_schedule_in_progress_season_preserves_played_matches(self, season, home_team, away_team):
        from apps.matches.generator import generate_season_schedule
        from apps.analytics.models import Standing
        season.is_current = True
        season.save()
        t3 = Team.objects.create(name="Tercer Equipo", acronym="TER")
        t4 = Team.objects.create(name="Cuarto Equipo", acronym="CUA")
        for t in [home_team, away_team, t3, t4]:
            Standing.objects.get_or_create(season=season, team=t, defaults={"points_for": 0, "points_against": 0})

        # Simular Jornada 1 ya disputada (FINALIZADA)
        Match.objects.create(
            season=season,
            round_number=1,
            home_team=home_team,
            away_team=away_team,
            status=Match.Status.FINISHED,
            home_score=85,
            away_score=80,
            scheduled_at=timezone.now() - datetime.timedelta(days=7),
        )
        Match.objects.create(
            season=season,
            round_number=1,
            home_team=t3,
            away_team=t4,
            status=Match.Status.FINISHED,
            home_score=90,
            away_score=88,
            scheduled_at=timezone.now() - datetime.timedelta(days=7),
        )

        # Generar calendario para la temporada en curso
        result = generate_season_schedule(season, double_round=True, dry_run=False, clear_existing=True)
        assert result["already_played_rounds"] == 1
        assert result["already_played_matches_count"] == 2
        assert result["start_round_idx"] == 2
        assert result["total_rounds"] == 6

        # Jornada 1 debe seguir teniendo exactamente los 2 partidos finalizados (no mezclados ni duplicados)
        j1_matches = Match.objects.filter(season=season, round_number=1)
        assert j1_matches.count() == 2
        assert all(m.status == Match.Status.FINISHED for m in j1_matches)

        # Jornadas 2 a 6 deben tener sus partidos programados correspondientes
        for r in range(2, 7):
            j_matches = Match.objects.filter(season=season, round_number=r)
            assert j_matches.count() == 2
            assert all(m.status == Match.Status.SCHEDULED for m in j_matches)

        # Total de partidos en la temporada: 2 jugados + 10 programados = 12 partidos
        assert Match.objects.filter(season=season).count() == 12

    def test_generate_schedule_partially_played_round_4_teams(self, season, home_team, away_team):
        """
        Verifica que cuando una jornada solo tiene 1 partido disputado/en juego (ej. J1 con Barça vs Madrid),
        el generador complete la jornada 1 con el 2º partido restante y genere las 6 jornadas completas con 2 partidos cada una.
        """
        from apps.matches.generator import generate_season_schedule
        from apps.analytics.models import Standing
        season.is_current = True
        season.save()
        t3 = Team.objects.create(name="Tercer Equipo", acronym="TER")
        t4 = Team.objects.create(name="Cuarto Equipo", acronym="CUA")
        for t in [home_team, away_team, t3, t4]:
            Standing.objects.get_or_create(season=season, team=t, defaults={"points_for": 0, "points_against": 0})

        # Simular solo 1 partido en juego/en directo en la Jornada 1
        Match.objects.create(
            season=season,
            round_number=1,
            home_team=home_team,
            away_team=away_team,
            status=Match.Status.LIVE,
            current_period=Match.Period.Q1,
            game_clock="08:35",
            scheduled_at=timezone.now() - datetime.timedelta(days=1),
        )

        result = generate_season_schedule(season, double_round=True, dry_run=False, clear_existing=True, random_seed=42)
        assert result["total_rounds"] == 6
        assert result["already_played_matches_count"] == 1

        all_matches = Match.objects.filter(season=season).order_by("round_number")
        assert all_matches.count() == 12

        for r in range(1, 7):
            r_matches = list(all_matches.filter(round_number=r))
            assert len(r_matches) == 2, f"La Jornada {r} debe tener exactamente 2 partidos"
            teams_in_r = set()
            for m in r_matches:
                teams_in_r.add(m.home_team_id)
                teams_in_r.add(m.away_team_id)
            assert len(teams_in_r) == 4, f"La Jornada {r} debe incluir a los 4 equipos"

    def test_re_preview_generates_distinct_combinations_for_in_progress_season(self, season, home_team, away_team):
        """
        Verifica que al solicitar 'Probar Otra Combinación' con distintas semillas aleatorias,
        se generen combinaciones de calendario distintas para las jornadas restantes, cumpliendo todas las reglas.
        """
        from apps.matches.generator import generate_season_schedule
        from apps.analytics.models import Standing
        season.is_current = True
        season.save()
        t3 = Team.objects.create(name="Tercer Equipo", acronym="TER")
        t4 = Team.objects.create(name="Cuarto Equipo", acronym="CUA")
        for t in [home_team, away_team, t3, t4]:
            Standing.objects.get_or_create(season=season, team=t, defaults={"points_for": 0, "points_against": 0})

        # Jornada 1 con 1 partido jugado
        Match.objects.create(
            season=season,
            round_number=1,
            home_team=home_team,
            away_team=away_team,
            status=Match.Status.FINISHED,
            home_score=82,
            away_score=78,
            scheduled_at=timezone.now() - datetime.timedelta(days=7),
        )

        comb1 = generate_season_schedule(season, double_round=True, dry_run=True, random_seed=11111)
        comb2 = generate_season_schedule(season, double_round=True, dry_run=True, random_seed=99999)

        matches1 = [(m["round_number"], m["home_team"].id, m["away_team"].id) for m in comb1["matches"]]
        matches2 = [(m["round_number"], m["home_team"].id, m["away_team"].id) for m in comb2["matches"]]

        # Las dos combinaciones deben ser válidas pero no idénticas
        assert len(matches1) == 11
        assert len(matches2) == 11
        assert matches1 != matches2, "Semillas distintas deben producir combinaciones distintas de cruces/orden de jornadas"

    def test_generate_schedule_with_seed_is_deterministic(self, season, home_team, away_team):
        from apps.matches.generator import generate_season_schedule
        from apps.analytics.models import Standing
        season.is_current = True
        season.save()
        t3 = Team.objects.create(name="Equipo Tres", acronym="TR3")
        t4 = Team.objects.create(name="Equipo Cuatro", acronym="CU4")
        for t in [home_team, away_team, t3, t4]:
            Standing.objects.get_or_create(season=season, team=t, defaults={"points_for": 0, "points_against": 0})

        # Previsualizar con semilla fija
        preview = generate_season_schedule(season, dry_run=True, random_seed=42)
        # Guardar con la misma semilla fija
        saved = generate_season_schedule(season, dry_run=False, random_seed=42)

        preview_pairs = [(m["round_number"], m["home_team"].id, m["away_team"].id) for m in preview["matches"]]
        saved_pairs = [(m["round_number"], m["home_team"].id, m["away_team"].id) for m in saved["matches"]]
        assert preview_pairs == saved_pairs

    def test_conventional_two_leg_league_structure(self, season, home_team, away_team):
        from apps.matches.generator import generate_season_schedule
        from apps.analytics.models import Standing
        season.is_current = True
        season.save()
        t3 = Team.objects.create(name="Equipo Tres", acronym="TR3")
        t4 = Team.objects.create(name="Equipo Cuatro", acronym="CU4")
        for t in [home_team, away_team, t3, t4]:
            Standing.objects.get_or_create(season=season, team=t, defaults={"points_for": 0, "points_against": 0})

        result = generate_season_schedule(season, double_round=True, dry_run=True, random_seed=123)
        matches = result["matches"]

        # J1-J3: Primera Vuelta (todos se enfrentan 1 vez)
        first_leg_matches = [m for m in matches if m["round_number"] in [1, 2, 3]]
        first_leg_pairs = set((m["home_team"].id, m["away_team"].id) for m in first_leg_matches)
        assert len(first_leg_pairs) == 6

        # J4-J6: Segunda Vuelta (mismos cruces con local/visitante invertido)
        second_leg_matches = [m for m in matches if m["round_number"] in [4, 5, 6]]
        second_leg_pairs = set((m["home_team"].id, m["away_team"].id) for m in second_leg_matches)
        assert len(second_leg_pairs) == 6

        # Comprobar que cada partido de la segunda vuelta es exactamente el inverso de la primera vuelta
        for h_id, a_id in second_leg_pairs:
            assert (a_id, h_id) in first_leg_pairs

    def test_round_5_inverts_round_2_and_canonical_symmetry(self, season):
        from apps.matches.generator import generate_full_berger_rounds
        import random
        t0 = Team(id=1, name="Real Madrid", slug="real-madrid-baloncesto")
        t1 = Team(id=2, name="FC Barcelona", slug="fc-barcelona-basket")
        t2 = Team(id=3, name="Unicaja", slug="unicaja-malaga")
        t3 = Team(id=4, name="Valencia Basket", slug="valencia-basket")
        teams = [t0, t1, t2, t3]

        rng1 = random.Random(100)
        rounds1 = generate_full_berger_rounds(teams, double_round=True, rng=rng1)
        assert len(rounds1) == 6

        # Cada jornada de la 2ª vuelta (J4, J5, J6) es la inversión simétrica exacta de su correspondiente jornada de ida (J1, J2, J3)
        for i in range(3):
            j_ida = rounds1[i]
            j_vuelta = rounds1[i + 3]
            assert set((h.id, a.id) for h, a in j_vuelta) == set((a.id, h.id) for h, a in j_ida)

        # En la primera vuelta, todas las 6 parejas juegan exactamente 1 vez
        first_leg_pairs = [(min(h.id, a.id), max(h.id, a.id)) for r in rounds1[:3] for h, a in r]
        assert len(first_leg_pairs) == 6
        assert len(set(first_leg_pairs)) == 6

    def test_euroleague_6_teams_all_10_rules(self):
        """Verifica el cumplimiento estricto de las 10 reglas para EuroLeague (6 equipos)."""
        from apps.matches.generator import generate_full_berger_rounds
        import random
        teams = [Team(id=i, name=f"Team {i}") for i in range(1, 7)]
        rng = random.Random(42)
        rounds = generate_full_berger_rounds(teams, double_round=True, rng=rng)

        # Regla 8: Total jornadas = 2 * (6 - 1) = 10
        assert len(rounds) == 10

        # Regla 6: 1ª vuelta tiene 5 jornadas
        first_leg = rounds[:5]
        # Regla 7: 2ª vuelta tiene 5 jornadas
        second_leg = rounds[5:]

        all_season_matches = []
        home_counts = {t.id: 0 for t in teams}
        away_counts = {t.id: 0 for t in teams}

        for r_idx, r_matches in enumerate(rounds, start=1):
            # Regla 2: Cada jornada tiene N/2 = 3 partidos
            assert len(r_matches) == 3

            # Regla 1 y 3: Cada equipo juega exactamente una vez por jornada
            teams_in_round = [t.id for m in r_matches for t in m]
            assert len(teams_in_round) == 6
            assert len(set(teams_in_round)) == 6

            for h, a in r_matches:
                all_season_matches.append((h.id, a.id))
                home_counts[h.id] += 1
                away_counts[a.id] += 1

        # Regla 9: Total partidos = 6 * 5 = 30
        assert len(all_season_matches) == 30

        # Regla 4: Cada pareja se enfrenta exactamente 2 veces (1 local, 1 visitante)
        assert len(set(all_season_matches)) == 30

        # Regla 5: No se repite enfrentamiento en la misma vuelta
        first_leg_pairs = set((h.id, a.id) for r in first_leg for h, a in r)
        assert len(first_leg_pairs) == 15

        # Regla 7: La segunda vuelta invierte local y visitante
        for i in range(5):
            j_ida = first_leg[i]
            j_vuelta = second_leg[i]
            assert set((h.id, a.id) for h, a in j_vuelta) == set((a.id, h.id) for h, a in j_ida)

        # Regla 10: Cada equipo juega 5 partidos como local y 5 como visitante
        for t in teams:
            assert home_counts[t.id] == 5
            assert away_counts[t.id] == 5

    def test_euroleague_in_progress_season_no_duplicate_teams_in_any_round(self, season):
        """Verifica que al completar EuroLeague en curso (J1 y J2 disputadas), NINGÚN equipo juegue 2 veces en la misma jornada (ej. J8)."""
        from apps.matches.generator import generate_season_schedule
        from apps.analytics.models import Standing
        season.is_current = True
        season.save()

        teams = [Team.objects.create(name=f"EuroTeam {i}", acronym=f"ET{i}") for i in range(1, 7)]
        for t in teams:
            Standing.objects.get_or_create(season=season, team=t, defaults={"points_for": 0, "points_against": 0})

        # Jornada 1 disputada (3 partidos, todos los 6 equipos)
        Match.objects.create(season=season, round_number=1, home_team=teams[0], away_team=teams[5], status=Match.Status.FINISHED, home_score=88, away_score=85, scheduled_at=timezone.now() - datetime.timedelta(days=14))
        Match.objects.create(season=season, round_number=1, home_team=teams[1], away_team=teams[4], status=Match.Status.FINISHED, home_score=91, away_score=84, scheduled_at=timezone.now() - datetime.timedelta(days=14))
        Match.objects.create(season=season, round_number=1, home_team=teams[2], away_team=teams[3], status=Match.Status.FINISHED, home_score=79, away_score=74, scheduled_at=timezone.now() - datetime.timedelta(days=14))

        # Jornada 2 disputada (3 partidos, todos los 6 equipos)
        Match.objects.create(season=season, round_number=2, home_team=teams[5], away_team=teams[1], status=Match.Status.FINISHED, home_score=94, away_score=89, scheduled_at=timezone.now() - datetime.timedelta(days=7))
        Match.objects.create(season=season, round_number=2, home_team=teams[0], away_team=teams[2], status=Match.Status.FINISHED, home_score=86, away_score=82, scheduled_at=timezone.now() - datetime.timedelta(days=7))
        Match.objects.create(season=season, round_number=2, home_team=teams[3], away_team=teams[4], status=Match.Status.FINISHED, home_score=80, away_score=77, scheduled_at=timezone.now() - datetime.timedelta(days=7))

        result = generate_season_schedule(season, double_round=True, dry_run=False, clear_existing=True, random_seed=999)
        assert result["already_played_rounds"] == 2
        assert result["already_played_matches_count"] == 6
        assert result["total_rounds"] == 10

        all_matches = Match.objects.filter(season=season).order_by("round_number", "scheduled_at")
        assert all_matches.count() == 30

        # Verificar cada una de las 10 jornadas: CADA JORNADA TIENE EXACTAMENTE 3 PARTIDOS Y 6 EQUIPOS DISTINTOS
        for r in range(1, 11):
            r_matches = list(all_matches.filter(round_number=r))
            assert len(r_matches) == 3, f"La jornada {r} debe tener 3 partidos"
            teams_in_r = []
            for m in r_matches:
                teams_in_r.append(m.home_team_id)
                teams_in_r.append(m.away_team_id)
            assert len(teams_in_r) == 6, f"La jornada {r} debe involucrar a 6 equipos"
            assert len(set(teams_in_r)) == 6, f"La jornada {r} contiene equipos duplicados: {teams_in_r}"

    def test_get_team_roster_deduplication_across_multiple_seasons(self, season, home_team):
        """Verifica que un jugador con membresías en múltiples temporadas (ej. ACB y EuroLeague) solo aparezca 1 vez en el acta del partido."""
        from apps.teams.models import Player, TeamMembership, Season, League
        p1 = Player.objects.create(first_name="Kevin", last_name="Punter", is_active=True)
        p2 = Player.objects.create(first_name="Jan", last_name="Vesely", is_active=True)

        other_league = League.objects.create(name="Otra Liga", slug="otra-liga", is_active=True)
        other_season = Season.objects.create(league=other_league, name="Temp 2026", start_date=datetime.date(2026, 9, 1), end_date=datetime.date(2027, 6, 30), is_current=True)

        # Membresía en la temporada actual del partido
        TeamMembership.objects.create(team=home_team, player=p1, season=season, jersey_number=0, is_active=True)
        TeamMembership.objects.create(team=home_team, player=p2, season=season, jersey_number=6, is_active=True)

        # Membresía en otra temporada o competición (duplicado histórico o multiligas)
        TeamMembership.objects.create(team=home_team, player=p1, season=other_season, jersey_number=0, is_active=True)
        TeamMembership.objects.create(team=home_team, player=p2, season=other_season, jersey_number=6, is_active=True)

        away = Team.objects.create(name="Away Team", acronym="AWA")
        match = Match.objects.create(
            season=season,
            home_team=home_team,
            away_team=away,
            round_number=1,
            scheduled_at=timezone.now() + datetime.timedelta(days=1),
        )

        roster = match.get_team_roster(home_team)
        player_ids = [m.player_id for m in roster]

        # Debe tener exactamente 2 jugadores únicos, ninguno repetido
        assert len(player_ids) == 2
        assert len(set(player_ids)) == 2
        assert p1.id in player_ids
        assert p2.id in player_ids

    def test_substitute_player_accumulates_minutes_played(self, season, home_team, away_team):
        """
        Verifica que al realizar una sustitución a 08:51 en el 1º Cuarto,
        el jugador que sale (ej. Kevin Punter) acumule correctamente el tiempo disputado (1 minuto).
        """
        p_out = Player.objects.create(first_name="Kevin", last_name="Punter", is_active=True)
        p_in = Player.objects.create(first_name="Tomas", last_name="Satoransky", is_active=True)
        p3 = Player.objects.create(first_name="Jan", last_name="Vesely", is_active=True)
        p4 = Player.objects.create(first_name="Dario", last_name="Brizuela", is_active=True)
        p5 = Player.objects.create(first_name="Chimezie", last_name="Metu", is_active=True)
        p6 = Player.objects.create(first_name="Justin", last_name="Anderson", is_active=True)

        for p, j in [(p_out, 0), (p_in, 13), (p3, 6), (p4, 8), (p5, 10), (p6, 1)]:
            from apps.teams.models import TeamMembership
            TeamMembership.objects.create(team=home_team, player=p, season=season, jersey_number=j, is_active=True)

        match = Match.objects.create(
            season=season,
            home_team=home_team,
            away_team=away_team,
            round_number=1,
            status=Match.Status.LIVE,
            current_period=Match.Period.Q1,
            game_clock="10:00",
            scheduled_at=timezone.now() + datetime.timedelta(days=1),
        )

        # Establecer quinteto titular inicial con Kevin Punter en pista
        match.set_starting_five(home_team, [p_out.id, p3.id, p4.id, p5.id, p6.id])

        # Avanzar el reloj del partido a 08:51
        match.game_clock = "08:51"
        match.save()

        # Realizar sustitución: Entra Tomas Satoransky (#13), Sale Kevin Punter (#0)
        event = match.substitute_player(home_team, player_out_id=p_out.id, player_in_id=p_in.id)

        assert event is not None
        assert event.event_type == MatchEvent.EventType.SUBSTITUTION
        assert "Satoransky" in event.description and "Punter" in event.description

        # Comprobar las estadísticas de Kevin Punter
        stat_out = PlayerMatchStat.objects.get(match=match, player=p_out)
        assert stat_out.is_on_court is False
        # De 10:00 (600s) a 08:51 (531s) han transcurrido 69s -> round(69/60) = 1 minuto
        assert stat_out.minutes_played == 1

        # Comprobar que Tomas Satoransky ahora está en pista con 0 minutos acumulados todavía
        stat_in = PlayerMatchStat.objects.get(match=match, player=p_in)
        assert stat_in.is_on_court is True
        assert stat_in.minutes_played == 0

    def test_calculate_player_minutes_from_events_timeline(self, season, home_team, away_team):
        """
        Verifica la reconstrucción exacta de minutos disputados para todos los jugadores
        a partir de la cronología de eventos del partido (titulares, sustituciones y reloj actual).
        """
        p_punter = Player.objects.create(first_name="Kevin", last_name="Punter", is_active=True)
        p_satoransky = Player.objects.create(first_name="Tomas", last_name="Satoransky", is_active=True)
        p_metu = Player.objects.create(first_name="Chimezie", last_name="Metu", is_active=True)
        p_bench = Player.objects.create(first_name="Alex", last_name="Abrines", is_active=True)

        for p, j in [(p_punter, 0), (p_satoransky, 13), (p_metu, 10), (p_bench, 21)]:
            from apps.teams.models import TeamMembership
            TeamMembership.objects.create(team=home_team, player=p, season=season, jersey_number=j, is_active=True)

        match = Match.objects.create(
            season=season,
            home_team=home_team,
            away_team=away_team,
            round_number=1,
            status=Match.Status.LIVE,
            current_period=Match.Period.Q1,
            game_clock="08:35",
            scheduled_at=timezone.now() + datetime.timedelta(days=1),
        )

        # Estadísticas iniciales (simulando estado inicial con 0 minutos en DB)
        st_punter, _ = PlayerMatchStat.objects.get_or_create(match=match, player=p_punter, team=home_team, defaults={"is_starter": True, "is_on_court": False, "minutes_played": 0})
        st_metu, _ = PlayerMatchStat.objects.get_or_create(match=match, player=p_metu, team=home_team, defaults={"is_starter": True, "is_on_court": True, "minutes_played": 0})
        st_sato, _ = PlayerMatchStat.objects.get_or_create(match=match, player=p_satoransky, team=home_team, defaults={"is_starter": False, "is_on_court": True, "minutes_played": 0})
        st_bench, _ = PlayerMatchStat.objects.get_or_create(match=match, player=p_bench, team=home_team, defaults={"is_starter": False, "is_on_court": False, "minutes_played": 0})

        # Evento de quinteto titular (10:00)
        MatchEvent.objects.create(
            match=match,
            period=Match.Period.Q1,
            game_clock="10:00",
            team=home_team,
            event_type=MatchEvent.EventType.STARTING_FIVE,
            description="Quinteto en pista confirmado (BAR): #0 Punter, #10 Metu"
        )

        # Evento de sustitución a las 08:51: Entra Satoransky, Sale Punter
        MatchEvent.objects.create(
            match=match,
            period=Match.Period.Q1,
            game_clock="08:51",
            team=home_team,
            player=p_satoransky,
            event_type=MatchEvent.EventType.SUBSTITUTION,
            description="Sustitución: Entra #13 Tomas Satoransky, Sale #0 Kevin Punter"
        )

        # 1. Kevin Punter jugó de 10:00 a 08:51 = 69 segundos -> 1 minuto
        mins_punter = match.calculate_player_minutes(p_punter.id)
        assert mins_punter == 1

        # 2. Chimezie Metu empezó de titular (10:00) y sigue en pista a las 08:35 = 85 segundos -> 1 minuto
        mins_metu = match.calculate_player_minutes(p_metu.id)
        assert mins_metu == 1

        # 3. Tomas Satoransky entró a las 08:51 y está en pista a las 08:35 = 16 segundos (<30s) -> 0 minutos
        mins_sato = match.calculate_player_minutes(p_satoransky.id)
        assert mins_sato == 0

        # 4. Alex Abrines no ha entrado a pista -> 0 minutos
        mins_bench = match.calculate_player_minutes(p_bench.id)
        assert mins_bench == 0







