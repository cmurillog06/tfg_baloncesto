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
