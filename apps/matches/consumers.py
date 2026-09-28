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

        # Mantener activa la conexion WebSocket sin modificar el estado del partido
        if action == "ping":
            await self.send_json({"type": "pong"})
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
                if "error" in result:
                    await self.send_json({"type": "error", "message": result["error"]})
                else:
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
                if "error" in result:
                    await self.send_json({"type": "error", "message": result["error"]})
                else:
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            "type": "event_update",
                            "data": result,
                        },
                    )

        # 3. Registro de Acciones Estadísticas Avanzadas (Rebotes, Asistencias, Robos, Pérdidas, Tapones, Tiros Fallados)
        elif action == "record_stat":
            team_id = content.get("team_id")
            player_id = content.get("player_id")
            stat_type = content.get("stat_type")

            result = await self.record_stat_event(
                self.match_id, team_id, player_id, stat_type
            )
            if result:
                if "error" in result:
                    await self.send_json({"type": "error", "message": result["error"]})
                else:
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            "type": "event_update",
                            "data": result,
                        },
                    )

        # 4. Solicitud de Tiempo Muerto (Timeout Oficial con Pausa de Reloj)
        elif action == "request_timeout":
            team_id = content.get("team_id")
            result = await self.record_timeout_event(self.match_id, team_id)
            if result:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "timeout_update",
                        "data": result,
                    },
                )

        # 5. Actualización de Reloj y Cronómetro de Servidor
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

        # 6. Cambio de Periodo / Cuarto
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

        # 7. Selección y Registro de Quinteto Inicial (5 Jugadores en Pista)
        elif action == "set_starting_five":
            team_id = content.get("team_id")
            player_ids = content.get("player_ids", [])
            result = await self.record_starting_five(self.match_id, team_id, player_ids)
            if result:
                if "error" in result:
                    await self.send_json({"type": "error", "message": result["error"]})
                else:
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            "type": "substitution_update",
                            "data": result,
                        },
                    )

        # 8. Sustitución de Jugadores (Banquillo <-> En Pista)
        elif action == "substitute_player":
            team_id = content.get("team_id")
            player_out_id = content.get("player_out_id")
            player_in_id = content.get("player_in_id")
            result = await self.record_substitution(
                self.match_id, team_id, player_out_id, player_in_id
            )
            if result:
                if "error" in result:
                    await self.send_json({"type": "error", "message": result["error"]})
                else:
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            "type": "substitution_update",
                            "data": result,
                        },
                    )

        # 9. Cierre Oficial del Acta Digital
        elif action == "close_scoresheet":
            referee_sig = content.get("referee_signature", "Árbitro Principal")
            second_referee_sig = content.get("second_referee_signature", "")
            table_sig = content.get("table_official_signature", user.username if user else "Anotador")
            timekeeper_sig = content.get("timekeeper_signature", "Cronometrador")
            report = content.get("incidents_report", "")

            result = await self.close_digital_scoresheet(
                self.match_id, referee_sig, second_referee_sig, table_sig, timekeeper_sig, report
            )
            if result:
                if "error" in result:
                    await self.send_json({"type": "error", "message": result["error"]})
                else:
                    # Detener reloj en servidor
                    set_server_clock(self.match_id, "00:00", False)
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

    async def timeout_update(self, event):
        await self.send_json(
            {
                "type": "timeout_update",
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

    async def substitution_update(self, event):
        await self.send_json(
            {
                "type": "substitution_update",
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
        if user.is_superuser or user.role == "ADMIN":
            return True
        try:
            match = Match.objects.get(id=match_id)
            return (
                user.role == "TABLE_OFFICIAL"
                and (match.table_official_id == user.id or match.timekeeper_id == user.id)
            )
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

            from apps.analytics.models import PlayerMatchStat
            player_stats = PlayerMatchStat.objects.filter(match=match)
            player_points = {str(st.player_id): st.points for st in player_stats}
            player_fouls = {str(st.player_id): st.fouls_committed for st in player_stats}

            home_on_court = match.get_on_court_player_ids(match.home_team)
            away_on_court = match.get_on_court_player_ids(match.away_team)

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
                    "timeouts": match.get_team_timeouts_info(match.home_team),
                    "fouls": match.get_team_fouls_info(match.home_team),
                    "on_court": home_on_court,
                    "has_five": match.has_valid_five_on_court(match.home_team),
                },
                "away_team": {
                    "id": match.away_team.id,
                    "name": match.away_team.name,
                    "acronym": match.away_team.acronym,
                    "color": match.away_team.primary_color,
                    "score": match.away_score,
                    "timeouts": match.get_team_timeouts_info(match.away_team),
                    "fouls": match.get_team_fouls_info(match.away_team),
                    "on_court": away_on_court,
                    "has_five": match.has_valid_five_on_court(match.away_team),
                },
                "home_on_court": home_on_court,
                "away_on_court": away_on_court,
                "player_points": player_points,
                "player_fouls": player_fouls,
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

            # Validar que el equipo tenga 5 jugadores marcados en pista (requisito de memoria)
            if not match.has_valid_five_on_court(team):
                return {
                    "error": f"Para registrar acciones, el equipo {team.name} debe tener exactamente 5 jugadores activos en pista. Configura el quinteto inicial primero."
                }

            # Validar si el jugador está en pista y si está eliminado por 5 faltas
            if player:
                from apps.analytics.models import PlayerMatchStat
                stat, _ = PlayerMatchStat.objects.get_or_create(
                    match=match,
                    player=player,
                    defaults={"team": team}
                )
                if not stat.is_on_court:
                    return {
                        "error": f"El jugador #{player.jersey_number} {player.full_name} está en el banquillo. Solo los 5 jugadores en pista pueden registrar acciones."
                    }
                if stat.fouls_committed >= 5 and points > 0:
                    return {
                        "error": f"El jugador #{player.jersey_number} {player.full_name} está eliminado del partido por acumulación de 5 faltas personales."
                    }

            # Actualizar marcador del partido (evitando números negativos)
            if match.home_team_id == team.id:
                match.home_score = max(0, match.home_score + points)
            elif match.away_team_id == team.id:
                match.away_score = max(0, match.away_score + points)

            if match.status == Match.Status.SCHEDULED:
                match.status = Match.Status.LIVE
                if match.current_period == Match.Period.NOT_STARTED:
                    match.current_period = Match.Period.Q1

            server_clock_str, is_running = get_server_clock(match_id, match.game_clock)
            match.game_clock = server_clock_str
            match.save()

            # Descripción amigable del evento
            if event_type == "CORRECTION" or points < 0:
                desc = f"Corrección de marcador ({points} pt{'s' if abs(points) > 1 else ''})"
            elif points == 3 or event_type == "3PT_MADE":
                desc = "Triple Anotado (+3 pts)"
            elif points == 2 or event_type == "2PT_MADE":
                desc = "Canasta de 2 Anotada (+2 pts)"
            elif points == 1 or event_type == "1PT_MADE":
                desc = "Tiro Libre Anotado (+1 pt)"
            elif points > 0:
                desc = f"+{points} pts"
            else:
                desc = "0 pts"

            # Registrar el evento en el acta
            event = MatchEvent.objects.create(
                match=match,
                period=match.current_period,
                game_clock=server_clock_str,
                team=team,
                player=player,
                event_type=event_type,
                points=points,
                description=desc,
            )

            # Actualizar hoja estadística individual del jugador en tiempo real
            player_stat_data = None
            if player:
                try:
                    from apps.analytics.models import PlayerMatchStat
                    stat, _ = PlayerMatchStat.objects.get_or_create(
                        match=match,
                        player=player,
                        defaults={"team": team}
                    )
                    if event_type == "3PT_MADE":
                        stat.points += 3
                        stat.three_points_made += 1
                        stat.three_points_attempted += 1
                        stat.field_goals_made += 1
                        stat.field_goals_attempted += 1
                    elif event_type == "2PT_MADE":
                        stat.points += 2
                        stat.field_goals_made += 1
                        stat.field_goals_attempted += 1
                    elif event_type == "1PT_MADE":
                        stat.points += 1
                        stat.free_throws_made += 1
                        stat.free_throws_attempted += 1
                    elif event_type == "CORRECTION":
                        stat.points = max(0, stat.points + points)
                        if points < 0:
                            if stat.field_goals_made > 0:
                                stat.field_goals_made = max(0, stat.field_goals_made - 1)
                                stat.field_goals_attempted = max(0, stat.field_goals_attempted - 1)
                            elif stat.free_throws_made > 0:
                                stat.free_throws_made = max(0, stat.free_throws_made - 1)
                                stat.free_throws_attempted = max(0, stat.free_throws_attempted - 1)
                    stat.compute_pir()
                    stat.save()

                    player_stat_data = {
                        "player_id": player.id,
                        "player_name": player.full_name,
                        "team_id": team.id,
                        "minutes_played": stat.minutes_played,
                        "points": stat.points,
                        "two_points_made": stat.two_points_made,
                        "two_points_attempted": stat.two_points_attempted,
                        "three_points_made": stat.three_points_made,
                        "three_points_attempted": stat.three_points_attempted,
                        "free_throws_made": stat.free_throws_made,
                        "free_throws_attempted": stat.free_throws_attempted,
                        "total_rebounds": stat.total_rebounds,
                        "assists": stat.assists,
                        "steals": stat.steals,
                        "turnovers": stat.turnovers,
                        "blocks_made": stat.blocks_made,
                        "fouls_committed": stat.fouls_committed,
                        "valuation_pir": stat.valuation_pir,
                    }
                except Exception:
                    pass

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
                "player_stat": player_stat_data,
                "new_event": {
                    "id": event.id,
                    "period": event.get_period_display(),
                    "clock": event.game_clock,
                    "team_acronym": team.acronym,
                    "team_id": team.id,
                    "player_name": player.full_name if player else None,
                    "event_type": event.get_event_type_display(),
                    "points": event.points,
                    "description": event.description,
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

            # Validar que el equipo tenga 5 jugadores marcados en pista (requisito de memoria)
            if not match.has_valid_five_on_court(team):
                return {
                    "error": f"Para registrar faltas, el equipo {team.name} debe tener exactamente 5 jugadores activos en pista. Configura el quinteto inicial primero."
                }

            # Validar si el jugador está en pista y si ya acumulaba 5 faltas
            if player:
                from apps.analytics.models import PlayerMatchStat
                stat, _ = PlayerMatchStat.objects.get_or_create(
                    match=match,
                    player=player,
                    defaults={"team": team}
                )
                if not stat.is_on_court:
                    return {
                        "error": f"El jugador #{player.jersey_number} {player.full_name} está en el banquillo. Solo los 5 jugadores en pista pueden cometer faltas."
                    }
                if stat.fouls_committed >= 5:
                    return {
                        "error": f"El jugador #{player.jersey_number} {player.full_name} ya está eliminado del partido (acumula 5 faltas)."
                    }

            server_clock_str, is_running = get_server_clock(match_id, match.game_clock)

            if match.status == Match.Status.SCHEDULED:
                match.status = Match.Status.LIVE
            if match.current_period == Match.Period.NOT_STARTED:
                match.current_period = Match.Period.Q1
            match.save(update_fields=["status", "current_period"])

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

            # Actualizar faltas en la estadística del jugador y recalcular PIR
            player_stat_data = None
            is_fouled_out = False
            if player:
                try:
                    from apps.analytics.models import PlayerMatchStat
                    stat, _ = PlayerMatchStat.objects.get_or_create(
                        match=match,
                        player=player,
                        defaults={"team": team}
                    )
                    stat.fouls_committed += 1
                    stat.compute_pir()
                    stat.save()

                    if stat.fouls_committed >= 5:
                        is_fouled_out = True

                    player_stat_data = {
                        "player_id": player.id,
                        "player_name": player.full_name,
                        "team_id": team.id,
                        "minutes_played": stat.minutes_played,
                        "points": stat.points,
                        "two_points_made": stat.two_points_made,
                        "two_points_attempted": stat.two_points_attempted,
                        "three_points_made": stat.three_points_made,
                        "three_points_attempted": stat.three_points_attempted,
                        "free_throws_made": stat.free_throws_made,
                        "free_throws_attempted": stat.free_throws_attempted,
                        "total_rebounds": stat.total_rebounds,
                        "assists": stat.assists,
                        "steals": stat.steals,
                        "turnovers": stat.turnovers,
                        "blocks_made": stat.blocks_made,
                        "fouls_committed": stat.fouls_committed,
                        "valuation_pir": stat.valuation_pir,
                    }
                except Exception:
                    pass

            # Calcular estado de faltas de equipo en el cuarto actual (FIBA Bonus)
            home_fouls_info = match.get_team_fouls_info(match.home_team)
            away_fouls_info = match.get_team_fouls_info(match.away_team)
            committing_fouls = home_fouls_info if team.id == match.home_team_id else away_fouls_info
            is_bonus_foul = committing_fouls["count"] >= 5

            if is_bonus_foul:
                if committing_fouls["count"] == 5:
                    bonus_text = " — ¡ENTRA EN BONUS! (2 Tiros Libres)"
                else:
                    bonus_text = " (En Bonus — 2 Tiros Libres)"
            else:
                bonus_text = ""

            if is_fouled_out:
                event.description = f"5ª Falta personal — ¡ELIMINADO DEL PARTIDO!{bonus_text}"
            elif is_bonus_foul:
                event.description = f"Falta señalizada{bonus_text}"
            else:
                event.description = "Falta señalizada"
            event.save()

            return {
                "match_id": match.id,
                "team_id": team.id,
                "team_fouls": committing_fouls["count"],
                "home_fouls": home_fouls_info,
                "away_fouls": away_fouls_info,
                "is_bonus_foul": is_bonus_foul,
                "bonus_team_id": team.id if is_bonus_foul else None,
                "bonus_team_name": team.name if is_bonus_foul else None,
                "player_stat": player_stat_data,
                "is_fouled_out": is_fouled_out,
                "fouled_out_player_id": player.id if (player and is_fouled_out) else None,
                "fouled_out_player_name": player.full_name if (player and is_fouled_out) else None,
                "new_event": {
                    "id": event.id,
                    "period": event.get_period_display(),
                    "clock": event.game_clock,
                    "team_acronym": team.acronym,
                    "team_id": team.id,
                    "player_name": player.full_name if player else None,
                    "event_type": event.get_event_type_display(),
                    "points": 0,
                    "description": event.description,
                    "time": event.created_at.strftime("%H:%M:%S"),
                },
            }
        except (Match.DoesNotExist, Team.DoesNotExist):
            return None

    @database_sync_to_async
    def record_stat_event(self, match_id, team_id, player_id, stat_type):
        try:
            match = Match.objects.get(id=match_id)
            team = Team.objects.get(id=team_id)
            player = Player.objects.filter(id=player_id).first() if player_id else None

            # Validar que el equipo tenga 5 jugadores marcados en pista (requisito de memoria)
            if not match.has_valid_five_on_court(team):
                return {
                    "error": f"Para registrar acciones estadísticas, el equipo {team.name} debe tener exactamente 5 jugadores activos en pista. Configura el quinteto inicial primero."
                }

            # Validar si el jugador está en pista y si está eliminado por 5 faltas
            if player:
                from apps.analytics.models import PlayerMatchStat
                stat, _ = PlayerMatchStat.objects.get_or_create(
                    match=match,
                    player=player,
                    defaults={"team": team}
                )
                if not stat.is_on_court:
                    return {
                        "error": f"El jugador #{player.jersey_number} {player.full_name} está en el banquillo. Solo los 5 jugadores en pista pueden registrar acciones."
                    }
                if stat.fouls_committed >= 5:
                    return {
                        "error": f"El jugador #{player.jersey_number} {player.full_name} está eliminado del partido por acumulación de 5 faltas personales."
                    }

            server_clock_str, is_running = get_server_clock(match_id, match.game_clock)

            if match.status == Match.Status.SCHEDULED:
                match.status = Match.Status.LIVE
            if match.current_period == Match.Period.NOT_STARTED:
                match.current_period = Match.Period.Q1
            match.save(update_fields=["status", "current_period"])

            # Mapeo de tipos de estadísticas a modelos de EventType y descripciones
            stat_meta = {
                "REBOUND": (MatchEvent.EventType.REBOUND_DEF, "Rebote capturado"),
                "ASSIST": (MatchEvent.EventType.ASSIST, "Asistencia repartida"),
                "STEAL": (MatchEvent.EventType.STEAL, "Robo de balón"),
                "TURNOVER": (MatchEvent.EventType.TURNOVER, "Pérdida de balón"),
                "BLOCK": (MatchEvent.EventType.BLOCK, "Tapón colocado"),
                "MISS_2PT": (MatchEvent.EventType.POINT_2_MISSED, "Tiro de 2 fallado"),
                "MISS_3PT": (MatchEvent.EventType.POINT_3_MISSED, "Triple fallado"),
                "MISS_FT": (MatchEvent.EventType.POINT_1_MISSED, "Tiro libre fallado"),
            }

            event_type_choice, desc = stat_meta.get(
                stat_type, (MatchEvent.EventType.REBOUND_DEF, "Acción de juego")
            )

            event = MatchEvent.objects.create(
                match=match,
                period=match.current_period,
                game_clock=server_clock_str,
                team=team,
                player=player,
                event_type=event_type_choice,
                points=0,
                description=desc,
            )

            # Actualizar hoja estadística individual y valoración PIR en tiempo real
            player_stat_data = None
            if player:
                try:
                    from apps.analytics.models import PlayerMatchStat
                    stat, _ = PlayerMatchStat.objects.get_or_create(
                        match=match,
                        player=player,
                        defaults={"team": team}
                    )
                    if stat_type == "REBOUND":
                        stat.rebounds_def += 1
                    elif stat_type == "ASSIST":
                        stat.assists += 1
                    elif stat_type == "STEAL":
                        stat.steals += 1
                    elif stat_type == "TURNOVER":
                        stat.turnovers += 1
                    elif stat_type == "BLOCK":
                        stat.blocks_made += 1
                    elif stat_type == "MISS_2PT":
                        stat.field_goals_attempted += 1
                    elif stat_type == "MISS_3PT":
                        stat.field_goals_attempted += 1
                        stat.three_points_attempted += 1
                    elif stat_type == "MISS_FT":
                        stat.free_throws_attempted += 1

                    stat.compute_pir()
                    stat.save()

                    player_stat_data = {
                        "player_id": player.id,
                        "player_name": player.full_name,
                        "team_id": team.id,
                        "minutes_played": stat.minutes_played,
                        "points": stat.points,
                        "two_points_made": stat.two_points_made,
                        "two_points_attempted": stat.two_points_attempted,
                        "three_points_made": stat.three_points_made,
                        "three_points_attempted": stat.three_points_attempted,
                        "free_throws_made": stat.free_throws_made,
                        "free_throws_attempted": stat.free_throws_attempted,
                        "total_rebounds": stat.total_rebounds,
                        "assists": stat.assists,
                        "steals": stat.steals,
                        "turnovers": stat.turnovers,
                        "blocks_made": stat.blocks_made,
                        "fouls_committed": stat.fouls_committed,
                        "valuation_pir": stat.valuation_pir,
                    }
                except Exception:
                    pass

            return {
                "match_id": match.id,
                "team_id": team.id,
                "player_stat": player_stat_data,
                "new_event": {
                    "id": event.id,
                    "period": event.get_period_display(),
                    "clock": event.game_clock,
                    "team_acronym": team.acronym,
                    "team_id": team.id,
                    "player_name": player.full_name if player else None,
                    "event_type": event.get_event_type_display(),
                    "points": 0,
                    "description": event.description,
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
            if is_running:
                if match.status == Match.Status.SCHEDULED:
                    match.status = Match.Status.LIVE
                if match.current_period == Match.Period.NOT_STARTED:
                    match.current_period = Match.Period.Q1
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
            # Acumular minutos jugados del cuarto que finaliza
            match.accumulate_period_minutes()

            match.current_period = period
            match.game_clock = clock_str
            if period == Match.Period.FINISHED:
                match.status = Match.Status.FINISHED
            elif period != Match.Period.NOT_STARTED:
                match.status = Match.Status.LIVE
            match.save()

            period_desc = "Final del Partido" if period == Match.Period.FINISHED else f"Comienzo del {match.get_current_period_display()}"
            event = MatchEvent.objects.create(
                match=match,
                period=match.current_period,
                game_clock=clock_str,
                team=match.home_team,
                player=None,
                event_type=MatchEvent.EventType.PERIOD,
                points=0,
                description=period_desc,
            )

            return {
                "match_id": match.id,
                "period": match.current_period,
                "period_display": match.get_current_period_display(),
                "clock": match.game_clock,
                "is_running": False,
                "status": match.status,
                "home_score": match.home_score,
                "away_score": match.away_score,
                "home_timeouts": match.get_team_timeouts_info(match.home_team),
                "away_timeouts": match.get_team_timeouts_info(match.away_team),
                "home_fouls": match.get_team_fouls_info(match.home_team),
                "away_fouls": match.get_team_fouls_info(match.away_team),
                "new_event": {
                    "id": event.id,
                    "period": event.get_period_display(),
                    "clock": event.game_clock,
                    "team_acronym": match.home_team.acronym,
                    "team_id": match.home_team.id,
                    "player_name": None,
                    "event_type": event.get_event_type_display(),
                    "points": 0,
                    "description": period_desc,
                    "time": event.created_at.strftime("%H:%M:%S"),
                },
            }
        except Match.DoesNotExist:
            return None

    @database_sync_to_async
    def record_timeout_event(self, match_id, team_id):
        try:
            match = Match.objects.get(id=match_id)
            team = Team.objects.get(id=team_id)

            timeout_info = match.get_team_timeouts_info(team)
            if timeout_info["remaining"] <= 0:
                return None

            # Pausar el reloj del partido en el servidor automáticamente
            server_clock_str, _ = get_server_clock(match_id, match.game_clock)
            calc_clock, calc_running = set_server_clock(match_id, server_clock_str, False)
            match.game_clock = calc_clock
            if match.status == Match.Status.SCHEDULED:
                match.status = Match.Status.LIVE
                if match.current_period == Match.Period.NOT_STARTED:
                    match.current_period = Match.Period.Q1
            match.save()

            # Registrar el evento de Tiempo Muerto en el acta oficial
            event = MatchEvent.objects.create(
                match=match,
                period=match.current_period,
                game_clock=calc_clock,
                team=team,
                player=None,
                event_type=MatchEvent.EventType.TIMEOUT,
                points=0,
                description=f"Tiempo Muerto solicitado ({timeout_info['used'] + 1}/{timeout_info['limit']})",
            )

            # Recalcular tiempos muertos actualizados para ambos equipos
            updated_home_timeouts = match.get_team_timeouts_info(match.home_team)
            updated_away_timeouts = match.get_team_timeouts_info(match.away_team)

            return {
                "match_id": match.id,
                "team_id": team.id,
                "team_name": team.name,
                "team_acronym": team.acronym,
                "clock": calc_clock,
                "is_running": False,
                "home_timeouts": updated_home_timeouts,
                "away_timeouts": updated_away_timeouts,
                "new_event": {
                    "id": event.id,
                    "period": event.get_period_display(),
                    "clock": event.game_clock,
                    "team_acronym": team.acronym,
                    "team_id": team.id,
                    "player_name": None,
                    "event_type": event.get_event_type_display(),
                    "points": 0,
                    "description": event.description,
                    "time": event.created_at.strftime("%H:%M:%S"),
                },
            }
        except (Match.DoesNotExist, Team.DoesNotExist):
            return None

    @database_sync_to_async
    def close_digital_scoresheet(self, match_id, referee_sig, second_referee_sig, table_sig, timekeeper_sig, report):
        try:
            match = Match.objects.get(id=match_id)
            server_clock_str, is_running = get_server_clock(match_id, match.game_clock)

            # 1. Validar que el partido se encuentre en el último cuarto (4Q) o prórroga
            valid_closing_periods = [
                Match.Period.Q4,
                Match.Period.OT1,
                Match.Period.OT2,
                Match.Period.FINISHED,
            ]
            if match.current_period not in valid_closing_periods:
                return {
                    "error": f"No se puede firmar ni cerrar el acta: el encuentro se encuentra en el {match.get_current_period_display()}. El acta solo puede firmarse al concluir el último periodo (4Q o Prórroga)."
                }

            # 2. Validar que el tiempo de juego haya expirado por completo (00:00) y no esté corriendo
            if server_clock_str != "00:00" or is_running:
                return {
                    "error": f"No se puede firmar ni cerrar el acta: el partido aún está en juego con {server_clock_str} restantes. El reloj debe llegar a 00:00 para concluir el partido."
                }

            # 3. Validar que no haya empate al finalizar el tiempo reglamentario (Reglamento FIBA/ACB)
            if match.home_score == match.away_score:
                return {
                    "error": f"No se puede cerrar el acta con empate ({match.home_score} - {match.away_score}). En baloncesto oficial debe disputarse una prórroga antes del cierre del acta."
                }

            match.status = Match.Status.FINISHED
            match.current_period = Match.Period.FINISHED
            match.game_clock = "00:00"
            match.save()

            scoresheet, _ = DigitalScoreSheet.objects.get_or_create(match=match)
            scoresheet.is_closed = True
            scoresheet.referee_signature = referee_sig
            scoresheet.second_referee_signature = second_referee_sig or (
                f"{match.second_referee.get_full_name() or match.second_referee.username} (Lic. FEB-31084)"
                if match.second_referee else "Antonio Conde Ruiz (Lic. FEB-31084)"
            )
            scoresheet.table_official_signature = table_sig
            scoresheet.timekeeper_signature = timekeeper_sig
            scoresheet.incidents_report = report
            scoresheet.closed_at = timezone.now()
            scoresheet.save()

            # Recalcular automáticamente la tabla de clasificación
            try:
                from apps.analytics.services import recalculate_season_standings
                recalculate_season_standings(match.season)
            except Exception:
                pass

            return {
                "match_id": match.id,
                "is_closed": True,
                "referee_signature": referee_sig,
                "table_signature": table_sig,
                "timekeeper_signature": timekeeper_sig,
                "closed_at": scoresheet.closed_at.strftime("%d/%m/%Y %H:%M"),
                "status": match.status,
            }
        except Match.DoesNotExist:
            return None

    @database_sync_to_async
    def record_starting_five(self, match_id, team_id, player_ids):
        try:
            match = Match.objects.get(id=match_id)
            team = Team.objects.get(id=team_id)
            event = match.set_starting_five(team, player_ids)

            home_on_court = match.get_on_court_player_ids(match.home_team)
            away_on_court = match.get_on_court_player_ids(match.away_team)

            return {
                "match_id": match.id,
                "team_id": team.id,
                "team_name": team.name,
                "home_on_court": home_on_court,
                "away_on_court": away_on_court,
                "home_has_five": match.has_valid_five_on_court(match.home_team),
                "away_has_five": match.has_valid_five_on_court(match.away_team),
                "new_event": {
                    "id": event.id,
                    "period": event.get_period_display(),
                    "clock": event.game_clock,
                    "team_acronym": team.acronym,
                    "team_id": team.id,
                    "player_name": None,
                    "event_type": event.get_event_type_display(),
                    "points": 0,
                    "description": event.description,
                    "time": event.created_at.strftime("%H:%M:%S"),
                },
            }
        except Exception as e:
            return {"error": str(e)}

    @database_sync_to_async
    def record_substitution(self, match_id, team_id, player_out_id, player_in_id):
        try:
            match = Match.objects.get(id=match_id)
            team = Team.objects.get(id=team_id)

            server_clock_str, is_running = get_server_clock(match_id, match.game_clock)
            match.game_clock = server_clock_str
            match.save(update_fields=["game_clock"])

            event = match.substitute_player(team, player_out_id, player_in_id)

            home_on_court = match.get_on_court_player_ids(match.home_team)
            away_on_court = match.get_on_court_player_ids(match.away_team)

            from apps.analytics.models import PlayerMatchStat
            stat_out = PlayerMatchStat.objects.filter(match=match, player_id=player_out_id).first()
            stat_in = PlayerMatchStat.objects.filter(match=match, player_id=player_in_id).first()

            if stat_out:
                calc_mins_out = match.calculate_player_minutes(player_out_id)
                stat_out.minutes_played = max(stat_out.minutes_played, calc_mins_out)
                stat_out.compute_pir()
                stat_out.save(update_fields=["minutes_played", "valuation_pir"])

            if stat_in:
                calc_mins_in = match.calculate_player_minutes(player_in_id)
                stat_in.minutes_played = max(stat_in.minutes_played, calc_mins_in)
                stat_in.compute_pir()
                stat_in.save(update_fields=["minutes_played", "valuation_pir"])

            stat_out_data = {
                "player_id": player_out_id,
                "player_name": stat_out.player.full_name if stat_out else None,
                "team_id": team.id,
                "minutes_played": stat_out.minutes_played if stat_out else 0,
                "points": stat_out.points if stat_out else 0,
                "two_points_made": stat_out.two_points_made if stat_out else 0,
                "two_points_attempted": stat_out.two_points_attempted if stat_out else 0,
                "three_points_made": stat_out.three_points_made if stat_out else 0,
                "three_points_attempted": stat_out.three_points_attempted if stat_out else 0,
                "free_throws_made": stat_out.free_throws_made if stat_out else 0,
                "free_throws_attempted": stat_out.free_throws_attempted if stat_out else 0,
                "total_rebounds": stat_out.total_rebounds if stat_out else 0,
                "assists": stat_out.assists if stat_out else 0,
                "steals": stat_out.steals if stat_out else 0,
                "turnovers": stat_out.turnovers if stat_out else 0,
                "blocks_made": stat_out.blocks_made if stat_out else 0,
                "fouls_committed": stat_out.fouls_committed if stat_out else 0,
                "valuation_pir": stat_out.valuation_pir if stat_out else 0,
            } if stat_out else None

            stat_in_data = {
                "player_id": player_in_id,
                "player_name": stat_in.player.full_name if stat_in else None,
                "team_id": team.id,
                "minutes_played": stat_in.minutes_played if stat_in else 0,
                "points": stat_in.points if stat_in else 0,
                "two_points_made": stat_in.two_points_made if stat_in else 0,
                "two_points_attempted": stat_in.two_points_attempted if stat_in else 0,
                "three_points_made": stat_in.three_points_made if stat_in else 0,
                "three_points_attempted": stat_in.three_points_attempted if stat_in else 0,
                "free_throws_made": stat_in.free_throws_made if stat_in else 0,
                "free_throws_attempted": stat_in.free_throws_attempted if stat_in else 0,
                "total_rebounds": stat_in.total_rebounds if stat_in else 0,
                "assists": stat_in.assists if stat_in else 0,
                "steals": stat_in.steals if stat_in else 0,
                "turnovers": stat_in.turnovers if stat_in else 0,
                "blocks_made": stat_in.blocks_made if stat_in else 0,
                "fouls_committed": stat_in.fouls_committed if stat_in else 0,
                "valuation_pir": stat_in.valuation_pir if stat_in else 0,
            } if stat_in else None

            return {
                "match_id": match.id,
                "team_id": team.id,
                "team_name": team.name,
                "player_out_id": player_out_id,
                "player_in_id": player_in_id,
                "player_out_stat": stat_out_data,
                "player_in_stat": stat_in_data,
                "home_on_court": home_on_court,
                "away_on_court": away_on_court,
                "home_has_five": match.has_valid_five_on_court(match.home_team),
                "away_has_five": match.has_valid_five_on_court(match.away_team),
                "new_event": {
                    "id": event.id,
                    "period": event.get_period_display(),
                    "clock": event.game_clock,
                    "team_acronym": team.acronym,
                    "team_id": team.id,
                    "player_name": event.player.full_name if event.player else None,
                    "event_type": event.get_event_type_display(),
                    "points": 0,
                    "description": event.description,
                    "time": event.created_at.strftime("%H:%M:%S"),
                },
            }
        except Exception as e:
            return {"error": str(e)}
