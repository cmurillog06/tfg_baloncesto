import json
import time
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import Match, MatchEvent, DigitalScoreSheet
from apps.teams.models import Player, Team


# -----------------------------------------------------------------------------
# GESTOR DE RELOJ EN TIEMPO REAL DEL SERVIDOR (SERVER-SIDE CLOCK SYNC)
# -----------------------------------------------------------------------------
# Guarda el estado del cronómetro en memoria para sincronizar a cualquier
# usuario que se conecte, recargue o cambie de pestaña en cualquier momento.
SERVER_MATCH_CLOCKS = {}


def get_server_clock(match_id, db_game_clock_str):
    """
    Calcula con precisión de servidor el tiempo restante y si está corriendo.
    """
    state = SERVER_MATCH_CLOCKS.get(match_id)
    if not state:
        try:
            parts = db_game_clock_str.split(":")
            sec = int(parts[0]) * 60 + int(parts[1])
        except Exception:
            sec = 600
        state = {
            "seconds": sec,
            "is_running": False,
            "last_start_time": None,
        }
        SERVER_MATCH_CLOCKS[match_id] = state
        return db_game_clock_str, False

    if state["is_running"] and state["last_start_time"]:
        elapsed = time.time() - state["last_start_time"]
        remaining = max(0, int(state["seconds"] - elapsed))
        m = remaining // 60
        s = remaining % 60
        clock_str = f"{m:02d}:{s:02d}"
        return clock_str, (remaining > 0)
    else:
        sec = state["seconds"]
        m = sec // 60
        s = sec % 60
        return f"{m:02d}:{s:02d}", False


def set_server_clock(match_id, clock_str, is_running):
    """
    Actualiza el estado del reloj de servidor cuando la mesa arbitral inicia/pausa/ajusta.
    """
    try:
        parts = clock_str.split(":")
        sec = int(parts[0]) * 60 + int(parts[1])
    except Exception:
        sec = 600

    SERVER_MATCH_CLOCKS[match_id] = {
        "seconds": sec,
        "is_running": is_running,
        "last_start_time": time.time() if is_running else None,
    }
    return clock_str, is_running


class MatchLiveConsumer(AsyncJsonWebsocketConsumer):
    """
    Consumidor WebSocket para retransmisión en tiempo real del marcador,
    eventos, reloj de servidor y acta digital del partido.
    """

    async def connect(self):
        self.match_id = int(self.scope["url_route"]["kwargs"]["match_id"])
        self.room_group_name = f"match_{self.match_id}"

        # Unirse a la sala del partido
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )
        await self.accept()

        # Enviar estado inicial del partido con tiempo de servidor exacto
        match_data = await self.get_match_state(self.match_id)
        if match_data:
            await self.send_json(
                {
                    "type": "initial_state",
                    "data": match_data,
                }
            )

    async def disconnect(self, close_code):
        # Salir de la sala del partido
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name,
        )

    async def receive_json(self, content):
        """
        Recibe acciones emitidas desde la mesa arbitral o clientes autorizados.
        """
        action = content.get("action")
        user = self.scope.get("user")

        # Verificar permisos para modificar el partido (Mesa Arbitral o Admin)
        is_authorized = await self.check_official_permission(user, self.match_id)

        if not is_authorized and action not in ["ping", "get_state"]:
            await self.send_json(
                {
                    "type": "error",
                    "message": "No tienes permisos de mesa arbitral para modificar este partido.",
                }
            )
            return

        # 1. Registro de Puntos / Canastas
        if action == "score_point":
            team_id = content.get("team_id")
            points = int(content.get("points", 1))
            player_id = content.get("player_id")
            event_type = content.get("event_type", "2PT_MADE")

            result = await self.record_score_event(
                self.match_id, team_id, points, player_id, event_type
            )
            if result:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "match_update",
                        "data": result,
                    },
                )

        # 2. Registro de Faltas Personales / Técnicas
        elif action == "record_foul":
            team_id = content.get("team_id")
            player_id = content.get("player_id")
            foul_type = content.get("foul_type", "PF")

            result = await self.record_foul_event(
                self.match_id, team_id, player_id, foul_type
            )
            if result:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "event_update",
                        "data": result,
                    },
                )

        # 3. Actualización de Reloj y Cronómetro de Servidor
        elif action == "clock_update":
            clock_str = content.get("game_clock", "10:00")
            period = content.get("period")
            status = content.get("status")
            is_running = bool(content.get("is_running", False))

            # Actualizar gestor de reloj de servidor
            calc_clock, calc_running = set_server_clock(self.match_id, clock_str, is_running)

            result = await self.update_clock_state(
                self.match_id, calc_clock, period, status, calc_running
            )
            if result:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "clock_update",
                        "data": result,
                    },
                )

        # 4. Cambio de Periodo / Cuarto
        elif action == "period_change":
            period = content.get("period")
            clock_str = content.get("game_clock", "10:00")
            
            # Resetear reloj de servidor para el nuevo periodo
            set_server_clock(self.match_id, clock_str, False)

            result = await self.update_period_state(self.match_id, period, clock_str)
            if result:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "match_update",
                        "data": result,
                    },
                )

        # 5. Cierre Oficial del Acta Digital
        elif action == "close_scoresheet":
            referee_sig = content.get("referee_signature", "Árbitro Principal")
            table_sig = content.get("table_official_signature", user.username if user else "Mesa Arbitral")
            report = content.get("incidents_report", "")

            # Detener reloj en servidor
            set_server_clock(self.match_id, "00:00", False)

            result = await self.close_digital_scoresheet(
                self.match_id, referee_sig, table_sig, report
            )
            if result:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "scoresheet_closed",
                        "data": result,
                    },
                )

    # --------------------------------------------------------------------------
    # Handlers para enviar mensajes a los clientes del grupo WebSocket
    # --------------------------------------------------------------------------

    async def match_update(self, event):
        await self.send_json(
            {
                "type": "match_update",
                "data": event["data"],
            }
        )

    async def event_update(self, event):
        await self.send_json(
            {
                "type": "event_update",
                "data": event["data"],
            }
        )

    async def clock_update(self, event):
        await self.send_json(
            {
                "type": "clock_update",
                "data": event["data"],
            }
        )

    async def scoresheet_closed(self, event):
        await self.send_json(
            {
                "type": "scoresheet_closed",
                "data": event["data"],
            }
        )

    # --------------------------------------------------------------------------
    # Consultas Asíncronas a la Base de Datos con database_sync_to_async
    # --------------------------------------------------------------------------

    @database_sync_to_async
    def check_official_permission(self, user, match_id):
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or user.role in ["ADMIN", "TABLE_OFFICIAL"]:
            return True
        try:
            match = Match.objects.get(id=match_id)
            return match.table_official == user
        except Match.DoesNotExist:
            return False

    @database_sync_to_async
    def get_match_state(self, match_id):
        try:
            match = Match.objects.select_related(
                "home_team", "away_team", "season__league"
            ).get(id=match_id)

            # Obtener tiempo de servidor y estado de reloj
            server_clock_str, is_running = get_server_clock(match_id, match.game_clock)

            events = list(
                match.events.select_related("player", "team").order_by("-created_at")[:15]
            )
            events_data = [
                {
                    "id": ev.id,
                    "period": ev.get_period_display(),
                    "clock": ev.game_clock,
                    "team_acronym": ev.team.acronym,
                    "team_id": ev.team.id,
                    "player_name": ev.player.full_name if ev.player else None,
                    "event_type": ev.get_event_type_display(),
                    "points": ev.points,
                    "description": ev.description,
                    "time": ev.created_at.strftime("%H:%M:%S"),
                }
                for ev in events
            ]

            return {
                "id": match.id,
                "league": match.season.league.name,
                "round": match.round_number,
                "status": match.status,
                "status_display": match.get_status_display(),
                "period": match.current_period,
                "period_display": match.get_current_period_display(),
                "clock": server_clock_str,
                "is_running": is_running,
                "home_team": {
                    "id": match.home_team.id,
                    "name": match.home_team.name,
                    "acronym": match.home_team.acronym,
                    "color": match.home_team.primary_color,
                    "score": match.home_score,
                },
                "away_team": {
                    "id": match.away_team.id,
                    "name": match.away_team.name,
                    "acronym": match.away_team.acronym,
                    "color": match.away_team.primary_color,
                    "score": match.away_score,
                },
                "is_closed": hasattr(match, "scoresheet") and match.scoresheet.is_closed,
                "recent_events": events_data,
            }
        except Match.DoesNotExist:
            return None

    @database_sync_to_async
    def record_score_event(self, match_id, team_id, points, player_id, event_type):
        try:
            match = Match.objects.get(id=match_id)
            team = Team.objects.get(id=team_id)
            player = Player.objects.filter(id=player_id).first() if player_id else None

            # Actualizar marcador del partido
            if match.home_team_id == team.id:
                match.home_score += points
            elif match.away_team_id == team.id:
                match.away_score += points

            if match.status == Match.Status.SCHEDULED:
                match.status = Match.Status.LIVE
                if match.current_period == Match.Period.NOT_STARTED:
                    match.current_period = Match.Period.Q1

            server_clock_str, is_running = get_server_clock(match_id, match.game_clock)
            match.game_clock = server_clock_str
            match.save()

            # Registrar el evento en el acta
            event = MatchEvent.objects.create(
                match=match,
                period=match.current_period,
                game_clock=server_clock_str,
                team=team,
                player=player,
                event_type=event_type,
                points=points,
                description=f"+{points} pts" if points > 0 else f"{points} pts",
            )

            return {
                "match_id": match.id,
                "home_score": match.home_score,
                "away_score": match.away_score,
                "status": match.status,
                "period": match.current_period,
                "period_display": match.get_current_period_display(),
                "clock": server_clock_str,
                "is_running": is_running,
                "scoring_team_id": team.id,
                "new_event": {
                    "id": event.id,
                    "period": event.get_period_display(),
                    "clock": event.game_clock,
                    "team_acronym": team.acronym,
                    "team_id": team.id,
                    "player_name": player.full_name if player else None,
                    "event_type": event.get_event_type_display(),
                    "points": event.points,
                    "time": event.created_at.strftime("%H:%M:%S"),
                },
            }
        except (Match.DoesNotExist, Team.DoesNotExist):
            return None

    @database_sync_to_async
    def record_foul_event(self, match_id, team_id, player_id, foul_type):
        try:
            match = Match.objects.get(id=match_id)
            team = Team.objects.get(id=team_id)
            player = Player.objects.filter(id=player_id).first() if player_id else None

            server_clock_str, is_running = get_server_clock(match_id, match.game_clock)

            event = MatchEvent.objects.create(
                match=match,
                period=match.current_period,
                game_clock=server_clock_str,
                team=team,
                player=player,
                event_type=foul_type,
                points=0,
                description="Falta señalizada",
            )

            # Contar faltas de equipo en el periodo actual
            team_fouls_count = MatchEvent.objects.filter(
                match=match,
                team=team,
                period=match.current_period,
                event_type__in=["PF", "TF", "UF"],
            ).count()

            return {
                "match_id": match.id,
                "team_id": team.id,
                "team_fouls": team_fouls_count,
                "new_event": {
                    "id": event.id,
                    "period": event.get_period_display(),
                    "clock": event.game_clock,
                    "team_acronym": team.acronym,
                    "team_id": team.id,
                    "player_name": player.full_name if player else None,
                    "event_type": event.get_event_type_display(),
                    "points": 0,
                    "time": event.created_at.strftime("%H:%M:%S"),
                },
            }
        except (Match.DoesNotExist, Team.DoesNotExist):
            return None

    @database_sync_to_async
    def update_clock_state(self, match_id, clock_str, period, status, is_running=False):
        try:
            match = Match.objects.get(id=match_id)
            if clock_str is not None:
                match.game_clock = clock_str
            if period:
                match.current_period = period
            if status:
                match.status = status
            match.save()

            return {
                "match_id": match.id,
                "clock": match.game_clock,
                "is_running": is_running,
                "period": match.current_period,
                "period_display": match.get_current_period_display(),
                "status": match.status,
            }
        except Match.DoesNotExist:
            return None

    @database_sync_to_async
    def update_period_state(self, match_id, period, clock_str):
        try:
            match = Match.objects.get(id=match_id)
            match.current_period = period
            match.game_clock = clock_str
            if period == Match.Period.FINISHED:
                match.status = Match.Status.FINISHED
            elif period != Match.Period.NOT_STARTED:
                match.status = Match.Status.LIVE
            match.save()

            return {
                "match_id": match.id,
                "period": match.current_period,
                "period_display": match.get_current_period_display(),
                "clock": match.game_clock,
                "is_running": False,
                "status": match.status,
                "home_score": match.home_score,
                "away_score": match.away_score,
            }
        except Match.DoesNotExist:
            return None

    @database_sync_to_async
    def close_digital_scoresheet(self, match_id, referee_sig, table_sig, report):
        try:
            match = Match.objects.get(id=match_id)
            match.status = Match.Status.FINISHED
            match.current_period = Match.Period.FINISHED
            match.game_clock = "00:00"
            match.save()

            scoresheet, _ = DigitalScoreSheet.objects.get_or_create(match=match)
            scoresheet.is_closed = True
            scoresheet.referee_signature = referee_sig
            scoresheet.table_official_signature = table_sig
            scoresheet.incidents_report = report
            scoresheet.closed_at = timezone.now()
            scoresheet.save()

            return {
                "match_id": match.id,
                "is_closed": True,
                "referee_signature": referee_sig,
                "table_signature": table_sig,
                "closed_at": scoresheet.closed_at.strftime("%d/%m/%Y %H:%M"),
                "status": match.status,
            }
        except Match.DoesNotExist:
            return None
