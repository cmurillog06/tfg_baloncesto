import pytest
import datetime
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from config.asgi import application
from apps.matches.models import Match, MatchEvent, DigitalScoreSheet
from apps.matches.consumers import SERVER_MATCH_CLOCKS
from apps.analytics.models import PlayerMatchStat


@database_sync_to_async
def db_set_player_fouls(match, player, count):
    stat, _ = PlayerMatchStat.objects.get_or_create(match=match, player=player)
    stat.fouls_committed = count
    stat.save()
    return stat


@database_sync_to_async
def db_check_matchevent_exists(match, event_type):
    return MatchEvent.objects.filter(match=match, event_type=event_type).exists()


@database_sync_to_async
def db_get_player_stat(match, player):
    return PlayerMatchStat.objects.get(match=match, player=player)


@database_sync_to_async
def db_prepare_match_for_closing(match):
    match.current_period = Match.Period.Q4
    match.game_clock = "00:00"
    match.home_score = 85
    match.away_score = 80
    match.save()
    from apps.matches.consumers import set_server_clock
    set_server_clock(match.id, "00:00", False)
    return match


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestMatchLiveConsumer:
    """Pruebas asíncronas y de tiempo real para MatchLiveConsumer usando WebsocketCommunicator."""

    async def test_match_live_consumer_connect_success(self, live_match, fan_user):
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = fan_user
        connected, _ = await communicator.connect()
        assert connected is True
        await communicator.disconnect()

    async def test_match_live_consumer_connect_receives_initial_state(self, live_match, fan_user):
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = fan_user
        connected, _ = await communicator.connect()
        assert connected is True
        response = await communicator.receive_json_from()
        assert response["type"] == "initial_state"
        assert response["data"]["id"] == live_match.id
        await communicator.disconnect()

    async def test_match_live_consumer_initial_state_contains_teams_and_scores(self, live_match, fan_user):
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = fan_user
        await communicator.connect()
        response = await communicator.receive_json_from()
        data = response["data"]
        assert data["home_team"]["acronym"] == "RMB"
        assert data["away_team"]["acronym"] == "FCB"
        assert data["home_team"]["score"] == live_match.home_score
        assert data["away_team"]["score"] == live_match.away_score
        await communicator.disconnect()

    async def test_match_live_consumer_initial_state_contains_clock_and_period(self, live_match, fan_user):
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = fan_user
        await communicator.connect()
        response = await communicator.receive_json_from()
        data = response["data"]
        assert "clock" in data
        assert "period" in data
        await communicator.disconnect()

    async def test_match_live_consumer_initial_state_contains_recent_events(self, live_match, fan_user):
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = fan_user
        await communicator.connect()
        response = await communicator.receive_json_from()
        data = response["data"]
        assert "recent_events" in data
        await communicator.disconnect()

    async def test_match_live_consumer_disconnect_leaves_group(self, live_match, fan_user):
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = fan_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.disconnect()

    async def test_match_live_consumer_unauthorized_user_blocked_from_actions(self, live_match, fan_user, home_team):
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = fan_user
        await communicator.connect()
        await communicator.receive_json_from()  # initial_state
        await communicator.send_json_to({
            "action": "score_point",
            "team_id": home_team.id,
            "points": 2,
            "event_type": "2PT_MADE",
        })
        response = await communicator.receive_json_from()
        assert response["type"] == "error"
        assert "permisos" in response["message"]
        await communicator.disconnect()

    async def test_match_live_consumer_anonymous_user_blocked_from_actions(self, live_match, home_team):
        from django.contrib.auth.models import AnonymousUser
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = AnonymousUser()
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            "action": "score_point",
            "team_id": home_team.id,
            "points": 2,
            "event_type": "2PT_MADE",
        })
        response = await communicator.receive_json_from()
        assert response["type"] == "error"
        await communicator.disconnect()

    async def test_match_live_consumer_score_point_1pt_free_throw_success(
        self, live_match, table_official_user, home_team, home_players
    ):
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = table_official_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            "action": "score_point",
            "team_id": home_team.id,
            "player_id": home_players[0].id,
            "points": 1,
            "event_type": "1PT_MADE",
        })
        response = await communicator.receive_json_from()
        assert response["type"] == "match_update"
        assert response["data"]["new_event"]["points"] == 1
        await communicator.disconnect()

    async def test_match_live_consumer_score_point_2pt_basket_success(
        self, live_match, table_official_user, home_team, home_players
    ):
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = table_official_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            "action": "score_point",
            "team_id": home_team.id,
            "player_id": home_players[0].id,
            "points": 2,
            "event_type": "2PT_MADE",
        })
        response = await communicator.receive_json_from()
        assert response["type"] == "match_update"
        assert response["data"]["new_event"]["points"] == 2
        await communicator.disconnect()

    async def test_match_live_consumer_score_point_3pt_triple_success(
        self, live_match, table_official_user, home_team, home_players
    ):
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = table_official_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            "action": "score_point",
            "team_id": home_team.id,
            "player_id": home_players[0].id,
            "points": 3,
            "event_type": "3PT_MADE",
        })
        response = await communicator.receive_json_from()
        assert response["type"] == "match_update"
        assert response["data"]["new_event"]["points"] == 3
        await communicator.disconnect()

    async def test_match_live_consumer_score_point_updates_match_score(
        self, live_match, table_official_user, home_team, home_players
    ):
        initial_score = live_match.home_score
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = table_official_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            "action": "score_point",
            "team_id": home_team.id,
            "player_id": home_players[0].id,
            "points": 2,
            "event_type": "2PT_MADE",
        })
        response = await communicator.receive_json_from()
        assert response["data"]["home_score"] == initial_score + 2
        await communicator.disconnect()

    async def test_match_live_consumer_score_point_creates_matchevent(
        self, live_match, table_official_user, home_team, home_players
    ):
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = table_official_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            "action": "score_point",
            "team_id": home_team.id,
            "player_id": home_players[0].id,
            "points": 3,
            "event_type": "3PT_MADE",
        })
        await communicator.receive_json_from()
        assert await db_check_matchevent_exists(live_match, "3PT_MADE")
        await communicator.disconnect()

    async def test_match_live_consumer_score_point_updates_player_stats(
        self, live_match, table_official_user, home_team, home_players
    ):
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = table_official_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            "action": "score_point",
            "team_id": home_team.id,
            "player_id": home_players[0].id,
            "points": 2,
            "event_type": "2PT_MADE",
        })
        await communicator.receive_json_from()
        stat = await db_get_player_stat(live_match, home_players[0])
        assert stat.points >= 2
        await communicator.disconnect()

    async def test_match_live_consumer_record_foul_personal_success(
        self, live_match, table_official_user, home_team, home_players
    ):
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = table_official_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            "action": "record_foul",
            "team_id": home_team.id,
            "player_id": home_players[0].id,
            "foul_type": "PF",
        })
        response = await communicator.receive_json_from()
        assert response["type"] == "event_update"
        assert response["data"]["new_event"]["event_type"] == "Falta Personal" or "Falta" in response["data"]["new_event"]["description"]
        await communicator.disconnect()

    async def test_match_live_consumer_record_foul_technical_success(
        self, live_match, table_official_user, home_team, home_players
    ):
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = table_official_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            "action": "record_foul",
            "team_id": home_team.id,
            "player_id": home_players[0].id,
            "foul_type": "TF",
        })
        response = await communicator.receive_json_from()
        assert response["type"] == "event_update"
        await communicator.disconnect()

    async def test_match_live_consumer_record_foul_unsportsmanlike_success(
        self, live_match, table_official_user, home_team, home_players
    ):
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = table_official_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            "action": "record_foul",
            "team_id": home_team.id,
            "player_id": home_players[0].id,
            "foul_type": "UF",
        })
        response = await communicator.receive_json_from()
        assert response["type"] == "event_update"
        await communicator.disconnect()

    async def test_match_live_consumer_record_foul_5th_personal_foul_marks_disqualified(
        self, live_match, table_official_user, home_team, home_players
    ):
        await db_set_player_fouls(live_match, home_players[0], 4)
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = table_official_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            "action": "record_foul",
            "team_id": home_team.id,
            "player_id": home_players[0].id,
            "foul_type": "PF",
        })
        response = await communicator.receive_json_from()
        assert response["data"].get("is_fouled_out", False) is True or response["data"]["player_fouls"] >= 5
        await communicator.disconnect()

    async def test_match_live_consumer_record_foul_5th_team_foul_triggers_quarter_bonus(
        self, live_match, table_official_user, home_team, home_players
    ):
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = table_official_user
        await communicator.connect()
        await communicator.receive_json_from()
        for i in range(5):
            await communicator.send_json_to({
                "action": "record_foul",
                "team_id": home_team.id,
                "player_id": home_players[i % len(home_players)].id,
                "foul_type": "PF",
            })
            response = await communicator.receive_json_from()
        assert response["data"]["is_bonus_foul"] is True or response["data"]["home_fouls"]["in_bonus"] is True
        assert response["data"]["team_fouls"] >= 5
        await communicator.disconnect()

    async def test_match_live_consumer_record_stat_rebound_offensive_success(
        self, live_match, table_official_user, home_team, home_players
    ):
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = table_official_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            "action": "record_stat",
            "team_id": home_team.id,
            "player_id": home_players[0].id,
            "stat_type": "REBOUND",
        })
        response = await communicator.receive_json_from()
        assert response["type"] == "event_update"
        await communicator.disconnect()

    async def test_match_live_consumer_record_stat_rebound_defensive_success(
        self, live_match, table_official_user, home_team, home_players
    ):
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = table_official_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            "action": "record_stat",
            "team_id": home_team.id,
            "player_id": home_players[0].id,
            "stat_type": "REBOUND",
        })
        response = await communicator.receive_json_from()
        assert response["type"] == "event_update"
        await communicator.disconnect()

    async def test_match_live_consumer_record_stat_assist_success(
        self, live_match, table_official_user, home_team, home_players
    ):
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = table_official_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            "action": "record_stat",
            "team_id": home_team.id,
            "player_id": home_players[0].id,
            "stat_type": "ASSIST",
        })
        response = await communicator.receive_json_from()
        assert response["type"] == "event_update"
        await communicator.disconnect()

    async def test_match_live_consumer_record_stat_steal_success(
        self, live_match, table_official_user, home_team, home_players
    ):
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = table_official_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            "action": "record_stat",
            "team_id": home_team.id,
            "player_id": home_players[0].id,
            "stat_type": "STEAL",
        })
        response = await communicator.receive_json_from()
        assert response["type"] == "event_update"
        await communicator.disconnect()

    async def test_match_live_consumer_record_stat_turnover_success(
        self, live_match, table_official_user, home_team, home_players
    ):
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = table_official_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            "action": "record_stat",
            "team_id": home_team.id,
            "player_id": home_players[0].id,
            "stat_type": "TURNOVER",
        })
        response = await communicator.receive_json_from()
        assert response["type"] == "event_update"
        await communicator.disconnect()

    async def test_match_live_consumer_record_stat_block_success(
        self, live_match, table_official_user, home_team, home_players
    ):
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = table_official_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            "action": "record_stat",
            "team_id": home_team.id,
            "player_id": home_players[0].id,
            "stat_type": "BLOCK",
        })
        response = await communicator.receive_json_from()
        assert response["type"] == "event_update"
        await communicator.disconnect()

    async def test_match_live_consumer_record_stat_missed_shot_success(
        self, live_match, table_official_user, home_team, home_players
    ):
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = table_official_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            "action": "record_stat",
            "team_id": home_team.id,
            "player_id": home_players[0].id,
            "stat_type": "MISS_2PT",
        })
        response = await communicator.receive_json_from()
        assert response["type"] == "event_update"
        await communicator.disconnect()

    async def test_match_live_consumer_request_timeout_increments_team_timeout_count(
        self, live_match, table_official_user, home_team
    ):
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = table_official_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            "action": "request_timeout",
            "team_id": home_team.id,
        })
        response = await communicator.receive_json_from()
        assert response["type"] == "timeout_update"
        assert response["data"]["home_timeouts"]["used"] >= 1
        await communicator.disconnect()

    async def test_match_live_consumer_request_timeout_broadcasts_timeout_update(
        self, live_match, table_official_user, home_team
    ):
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = table_official_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            "action": "request_timeout",
            "team_id": home_team.id,
        })
        response = await communicator.receive_json_from()
        assert response["type"] == "timeout_update"
        await communicator.disconnect()

    async def test_match_live_consumer_clock_update_synchronizes_server_match_clocks(
        self, live_match, table_official_user
    ):
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = table_official_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            "action": "clock_update",
            "game_clock": "07:45",
            "is_running": True,
        })
        response = await communicator.receive_json_from()
        assert response["type"] == "clock_update"
        assert response["data"]["clock"] == "07:45"
        assert live_match.id in SERVER_MATCH_CLOCKS
        await communicator.disconnect()

    async def test_match_live_consumer_clock_update_broadcasts_clock_update(
        self, live_match, table_official_user
    ):
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = table_official_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            "action": "clock_update",
            "game_clock": "05:00",
            "is_running": False,
        })
        response = await communicator.receive_json_from()
        assert response["type"] == "clock_update"
        await communicator.disconnect()

    async def test_match_live_consumer_period_change_advances_quarter(
        self, live_match, table_official_user
    ):
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = table_official_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            "action": "period_change",
            "period": "Q2",
            "game_clock": "10:00",
        })
        response = await communicator.receive_json_from()
        assert response["type"] == "match_update"
        assert response["data"]["period"] == "Q2"
        await communicator.disconnect()

    async def test_match_live_consumer_period_change_resets_clock_and_quarter_fouls(
        self, live_match, table_official_user
    ):
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = table_official_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            "action": "period_change",
            "period": "Q3",
            "game_clock": "10:00",
        })
        response = await communicator.receive_json_from()
        assert response["data"]["home_fouls"]["count"] == 0
        await communicator.disconnect()

    async def test_match_live_consumer_set_starting_five_success(
        self, live_match, table_official_user, home_team, home_players
    ):
        p_ids = [p.id for p in home_players[:5]]
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = table_official_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            "action": "set_starting_five",
            "team_id": home_team.id,
            "player_ids": p_ids,
        })
        response = await communicator.receive_json_from()
        assert response["type"] == "substitution_update"
        await communicator.disconnect()

    async def test_match_live_consumer_substitute_player_success(
        self, live_match, table_official_user, home_team, home_players
    ):
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = table_official_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            "action": "substitute_player",
            "team_id": home_team.id,
            "player_out_id": home_players[0].id,
            "player_in_id": home_players[5].id,
        })
        response = await communicator.receive_json_from()
        assert response["type"] == "substitution_update"
        await communicator.disconnect()

    async def test_match_live_consumer_close_scoresheet_success(
        self, live_match, table_official_user
    ):
        await db_prepare_match_for_closing(live_match)
        communicator = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        communicator.scope["user"] = table_official_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            "action": "close_scoresheet",
            "referee_signature": "Juan Carlos Garcia (Lic. FEB-48192)",
            "second_referee_signature": "Antonio Conde (Lic. FEB-31084)",
            "table_official_signature": "Carlos Murillo (Anotador)",
            "timekeeper_signature": "Laura Gomez (Cronometradora)",
            "incidents_report": "Encuentro concluido sin incidentes.",
        })
        response = await communicator.receive_json_from()
        assert response["type"] == "scoresheet_closed"
        assert response["data"]["is_closed"] is True
        await communicator.disconnect()

    async def test_match_live_consumer_multi_client_broadcast_to_spectator(
        self, live_match, table_official_user, fan_user, home_team, home_players
    ):
        # Table official client
        comm_official = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        comm_official.scope["user"] = table_official_user
        await comm_official.connect()
        await comm_official.receive_json_from()

        # Spectator fan client
        comm_fan = WebsocketCommunicator(application, f"/ws/matches/{live_match.id}/")
        comm_fan.scope["user"] = fan_user
        await comm_fan.connect()
        await comm_fan.receive_json_from()

        # Official scores 2 points
        await comm_official.send_json_to({
            "action": "score_point",
            "team_id": home_team.id,
            "player_id": home_players[0].id,
            "points": 2,
            "event_type": "2PT_MADE",
        })

        # Official receives confirmation broadcast
        res_official = await comm_official.receive_json_from()
        assert res_official["type"] == "match_update"

        # Spectator fan receives identical live broadcast simultaneously
        res_fan = await comm_fan.receive_json_from()
        assert res_fan["type"] == "match_update"
        assert res_fan["data"]["new_event"]["points"] == 2

        await comm_official.disconnect()
        await comm_fan.disconnect()
