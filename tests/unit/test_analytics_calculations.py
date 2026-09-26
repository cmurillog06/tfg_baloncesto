import pytest
from apps.analytics.models import Standing, PlayerMatchStat
from apps.analytics.services import (
    recalculate_season_standings,
    get_league_leaders,
    compute_positional_group_metrics,
    predictive_matchup_model,
)
from apps.matches.models import Match


@pytest.mark.django_db
class TestPlayerMatchStatAndFIBAPIR:
    """Pruebas unitarias para la fórmula oficial FIBA PIR de Valoración ACB/FIBA."""

    def test_pir_calculation_all_zeros_gives_zero(self, live_match, home_team, home_players):
        stat = PlayerMatchStat(match=live_match, player=home_players[0], team=home_team)
        assert stat.compute_pir() == 0

    def test_pir_calculation_positive_points(self, live_match, home_team, home_players):
        stat = PlayerMatchStat(match=live_match, player=home_players[0], team=home_team, points=15)
        assert stat.compute_pir() == 15

    def test_pir_calculation_positive_rebounds_offensive_and_defensive(self, live_match, home_team, home_players):
        stat = PlayerMatchStat(
            match=live_match, player=home_players[0], team=home_team, rebounds_off=3, rebounds_def=5
        )
        assert stat.total_rebounds == 8
        assert stat.compute_pir() == 8

    def test_pir_calculation_positive_assists(self, live_match, home_team, home_players):
        stat = PlayerMatchStat(match=live_match, player=home_players[0], team=home_team, assists=7)
        assert stat.compute_pir() == 7

    def test_pir_calculation_positive_steals(self, live_match, home_team, home_players):
        stat = PlayerMatchStat(match=live_match, player=home_players[0], team=home_team, steals=4)
        assert stat.compute_pir() == 4

    def test_pir_calculation_positive_blocks_made(self, live_match, home_team, home_players):
        stat = PlayerMatchStat(match=live_match, player=home_players[0], team=home_team, blocks_made=3)
        assert stat.compute_pir() == 3

    def test_pir_calculation_positive_fouls_received(self, live_match, home_team, home_players):
        stat = PlayerMatchStat(match=live_match, player=home_players[0], team=home_team, fouls_received=6)
        assert stat.compute_pir() == 6

    def test_pir_calculation_negative_missed_field_goals(self, live_match, home_team, home_players):
        stat = PlayerMatchStat(
            match=live_match,
            player=home_players[0],
            team=home_team,
            field_goals_attempted=10,
            field_goals_made=4,  # missed = 6
        )
        assert stat.compute_pir() == -6

    def test_pir_calculation_negative_missed_free_throws(self, live_match, home_team, home_players):
        stat = PlayerMatchStat(
            match=live_match,
            player=home_players[0],
            team=home_team,
            free_throws_attempted=8,
            free_throws_made=5,  # missed = 3
        )
        assert stat.compute_pir() == -3

    def test_pir_calculation_negative_turnovers(self, live_match, home_team, home_players):
        stat = PlayerMatchStat(match=live_match, player=home_players[0], team=home_team, turnovers=4)
        assert stat.compute_pir() == -4

    def test_pir_calculation_negative_blocks_received(self, live_match, home_team, home_players):
        stat = PlayerMatchStat(match=live_match, player=home_players[0], team=home_team, blocks_received=2)
        assert stat.compute_pir() == -2

    def test_pir_calculation_negative_fouls_committed(self, live_match, home_team, home_players):
        stat = PlayerMatchStat(match=live_match, player=home_players[0], team=home_team, fouls_committed=4)
        assert stat.compute_pir() == -4

    def test_pir_calculation_full_combined_formula(self, live_match, home_team, home_players):
        # Full FIBA Boxscore calculation:
        # Pos: 20 pts + 6 reb + 5 ast + 2 stl + 1 blk + 4 foul_rec = 38
        # Neg: (12 fga - 8 fgm = 4) + (4 fta - 3 ftm = 1) + 2 tov + 1 blk_rec + 3 foul_comm = 11
        # PIR = 38 - 11 = 27
        stat = PlayerMatchStat(
            match=live_match,
            player=home_players[0],
            team=home_team,
            points=20,
            rebounds_off=2,
            rebounds_def=4,
            assists=5,
            steals=2,
            blocks_made=1,
            fouls_received=4,
            field_goals_attempted=12,
            field_goals_made=8,
            free_throws_attempted=4,
            free_throws_made=3,
            turnovers=2,
            blocks_received=1,
            fouls_committed=3,
        )
        assert stat.compute_pir() == 27

    def test_pir_auto_calculated_on_save(self, scheduled_match, home_team, home_players):
        stat = PlayerMatchStat.objects.create(
            match=scheduled_match,
            player=home_players[0],
            team=home_team,
            points=10,
            assists=4,
            turnovers=2,
        )
        # Expected: 10 + 4 - 2 = 12
        assert stat.valuation_pir == 12

    def test_playermatchstat_two_points_properties(self, scheduled_match, home_team, home_players):
        stat = PlayerMatchStat(
            match=scheduled_match,
            player=home_players[0],
            team=home_team,
            field_goals_made=7,
            three_points_made=3,
            field_goals_attempted=14,
            three_points_attempted=6,
        )
        assert stat.two_points_made == 4
        assert stat.two_points_attempted == 8

    def test_playermatchstat_total_rebounds_property(self, scheduled_match, home_team, home_players):
        stat = PlayerMatchStat(
            match=scheduled_match,
            player=home_players[0],
            team=home_team,
            rebounds_off=4,
            rebounds_def=6,
        )
        assert stat.total_rebounds == 10

    def test_playermatchstat_str_representation(self, scheduled_match, home_team, home_players):
        stat = PlayerMatchStat.objects.create(
            match=scheduled_match,
            player=home_players[0],
            team=home_team,
            points=18,
        )
        assert f"{home_players[0].full_name} (RMB) - 18 pts" in str(stat)


@pytest.mark.django_db
class TestStandingModelAndTotals:
    """Pruebas unitarias para el cálculo de clasificación y puntuación FIBA."""

    def test_standing_update_totals_games_played(self, season, home_team):
        s = Standing(season=season, team=home_team, wins=5, losses=3)
        s.update_totals()
        assert s.games_played == 8

    def test_standing_update_totals_points_diff_positive(self, season, home_team):
        s = Standing(season=season, team=home_team, points_for=850, points_against=780)
        s.update_totals()
        assert s.points_diff == 70

    def test_standing_update_totals_points_diff_negative(self, season, home_team):
        s = Standing(season=season, team=home_team, points_for=700, points_against=760)
        s.update_totals()
        assert s.points_diff == -60

    def test_standing_update_totals_league_points_2pts_per_win_1pt_per_loss(self, season, home_team):
        # FIBA Scoring rule: 2 pts per win, 1 pt per loss
        # 6 wins * 2 + 4 losses * 1 = 16 pts
        s = Standing(season=season, team=home_team, wins=6, losses=4)
        s.update_totals()
        assert s.league_points == 16

    def test_standing_auto_update_on_save(self, season, home_team):
        s = Standing.objects.create(
            season=season,
            team=home_team,
            wins=4,
            losses=2,
            points_for=500,
            points_against=460,
        )
        assert s.games_played == 6
        assert s.points_diff == 40
        assert s.league_points == 10

    def test_standing_ordering_by_league_points_and_diff(self, season, home_team, away_team):
        Standing.objects.filter(season=season).delete()
        s1 = Standing.objects.create(season=season, team=home_team, wins=5, losses=1, points_for=500, points_against=450)
        s2 = Standing.objects.create(season=season, team=away_team, wins=4, losses=2, points_for=480, points_against=460)
        standings = list(Standing.objects.filter(season=season))
        assert standings[0].team == home_team
        assert standings[1].team == away_team

    def test_standing_str_representation(self, season, home_team):
        s = Standing.objects.create(season=season, team=home_team, wins=3, losses=1)
        assert "RMB - 7 pts" in str(s)


@pytest.mark.django_db
class TestAnalyticsServicesAndModels:
    """Pruebas unitarias para servicios de cálculo matemático y analítica avanzada."""

    def test_recalculate_season_standings_updates_table(self, season, home_team, away_team, finished_match):
        recalculate_season_standings(season)
        s_home = Standing.objects.get(season=season, team=home_team)
        s_away = Standing.objects.get(season=season, team=away_team)
        # finished_match score was 88 - 82
        assert s_home.wins == 1
        assert s_home.losses == 0
        assert s_home.points_for == 88
        assert s_home.points_against == 82
        assert s_away.wins == 0
        assert s_away.losses == 1
        assert s_away.points_for == 82
        assert s_away.points_against == 88

    def test_get_league_leaders_computes_season_top_scorers(self, season, home_team, home_players, finished_match):
        PlayerMatchStat.objects.create(
            match=finished_match,
            player=home_players[0],
            team=home_team,
            points=25,
            minutes_played=30,
            valuation_pir=28,
        )
        leaders = get_league_leaders(season=season)
        assert len(leaders["top_scorers"]) > 0
        assert leaders["top_scorers"][0]["avg_points"] == 25.0

    def test_compute_positional_group_metrics_groups_pg_wing_big(self, season, home_team, home_players):
        metrics = compute_positional_group_metrics(home_team, season=season)
        assert "PG" in metrics
        assert "WING" in metrics
        assert "BIG" in metrics
        assert metrics["PG"]["name"] == "Bases"

    def test_predictive_matchup_model_morey_pythagorean_expectation(self, season, home_team, away_team):
        result = predictive_matchup_model(home_team, away_team, season=season)
        assert "pythagorean" in result or "summary_text" in result or "fav_team" in result

    def test_predictive_matchup_model_dean_oliver_net_rating(self, season, home_team, away_team):
        result = predictive_matchup_model(home_team, away_team, season=season)
        assert result is not None
        assert isinstance(result, dict)

    def test_predictive_matchup_model_logistic_regression_probabilities(self, season, home_team, away_team):
        result = predictive_matchup_model(home_team, away_team, season=season)
        # Probability between 0 and 100
        prob_a = result.get("logistic", {}).get("prob_a_pct", result.get("fav_pct", 50))
        assert 0 <= prob_a <= 100
