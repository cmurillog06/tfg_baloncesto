from django.db import models
from django.conf import settings
from apps.teams.models import Team, Season, Player


class Match(models.Model):
    """
    Partido de baloncesto.
    """

    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Programado"
        LIVE = "LIVE", "En Juego"
        FINISHED = "FINISHED", "Finalizado"
        SUSPENDED = "SUSPENDED", "Suspendido"

    class Period(models.TextChoices):
        NOT_STARTED = "NS", "Por Comenzar"
        Q1 = "Q1", "1º Cuarto"
        Q2 = "Q2", "2º Cuarto"
        HALFTIME = "HT", "Descanso"
        Q3 = "Q3", "3º Cuarto"
        Q4 = "Q4", "4º Cuarto"
        OT1 = "OT1", "1ª Prórroga"
        OT2 = "OT2", "2ª Prórroga"
        FINISHED = "END", "Partido Concluido"

    season = models.ForeignKey(
        Season, on_delete=models.CASCADE, related_name="matches", verbose_name="Temporada"
    )
    round_number = models.PositiveIntegerField(default=1, verbose_name="Jornada")
    home_team = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name="home_matches", verbose_name="Equipo Local"
    )
    away_team = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name="away_matches", verbose_name="Equipo Visitante"
    )
    scheduled_at = models.DateTimeField(verbose_name="Fecha y Hora Programada")
    location = models.CharField(max_length=150, blank=True, verbose_name="Pabellón / Ubicación")

    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.SCHEDULED, verbose_name="Estado"
    )
    current_period = models.CharField(
        max_length=5, choices=Period.choices, default=Period.NOT_STARTED, verbose_name="Periodo Actual"
    )
    game_clock = models.CharField(max_length=10, default="10:00", verbose_name="Reloj de Juego")

    home_score = models.PositiveIntegerField(default=0, verbose_name="Puntos Local")
    away_score = models.PositiveIntegerField(default=0, verbose_name="Puntos Visitante")

    table_official = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="officiated_matches",
        verbose_name="Mesa Arbitral Asignada",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Partido"
        verbose_name_plural = "Partidos"
        ordering = ["scheduled_at"]

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        from django.utils import timezone

        # 2. El sistema no permitirá programar un partido oficial con una fecha u hora anterior a la fecha actual de creación.
        if self.scheduled_at:
            now = timezone.now()
            # Al crear un nuevo partido oficial
            if not self.pk:
                if self.scheduled_at < now:
                    raise ValidationError({
                        "scheduled_at": "No se puede programar un partido oficial con una fecha u hora anterior al momento de su creación."
                    })
            else:
                # Al reprogramar o modificar un partido existente que todavía se encuentra en estado 'Programado'
                if self.status == self.Status.SCHEDULED and self.scheduled_at < now:
                    raise ValidationError({
                        "scheduled_at": "La fecha y hora programada para el partido no puede ser anterior al momento actual."
                    })

        if self.home_team_id and self.away_team_id:
            if self.home_team_id == self.away_team_id:
                raise ValidationError({
                    "away_team": "El equipo local y el equipo visitante no pueden ser el mismo."
                })

        if self.season_id:
            from apps.teams.models import TeamMembership
            from apps.analytics.models import Standing

            # Obtener los equipos formalmente inscritos en esta temporada
            valid_team_ids = set(
                Standing.objects.filter(season=self.season).values_list("team_id", flat=True)
            )
            if not valid_team_ids:
                valid_team_ids = set(
                    TeamMembership.objects.filter(season=self.season).values_list("team_id", flat=True)
                )

            if valid_team_ids:
                if self.home_team_id and self.home_team_id not in valid_team_ids:
                    raise ValidationError({
                        "home_team": f"El equipo '{self.home_team.name}' no está inscrito en la competición '{self.season.league.name}' ({self.season.name})."
                    })
                if self.away_team_id and self.away_team_id not in valid_team_ids:
                    raise ValidationError({
                        "away_team": f"El equipo '{self.away_team.name}' no está inscrito en la competición '{self.season.league.name}' ({self.season.name})."
                    })

    def get_team_timeouts_info(self, team):
        """
        Calcula el límite y los tiempos muertos usados y restantes para un equipo según el periodo actual (FIBA).
        - 1ª Mitad (Q1, Q2): 2 tiempos muertos
        - 2ª Mitad (Q3, Q4): 3 tiempos muertos
        - Prórrogas (OT1, OT2...): 1 tiempo muerto por prórroga
        """
        period = self.current_period
        if period in [self.Period.Q1, self.Period.Q2]:
            limit = 2
            used = self.events.filter(
                team=team,
                event_type=MatchEvent.EventType.TIMEOUT,
                period__in=[self.Period.Q1, self.Period.Q2]
            ).count()
        elif period in [self.Period.Q3, self.Period.Q4]:
            limit = 3
            used = self.events.filter(
                team=team,
                event_type=MatchEvent.EventType.TIMEOUT,
                period__in=[self.Period.Q3, self.Period.Q4]
            ).count()
        elif period in [self.Period.OT1, self.Period.OT2]:
            limit = 1
            used = self.events.filter(
                team=team,
                event_type=MatchEvent.EventType.TIMEOUT,
                period=period
            ).count()
        else:
            limit = 2
            used = 0

        remaining = max(0, limit - used)
        return {
            "limit": limit,
            "used": used,
            "remaining": remaining,
            "can_request": remaining > 0 and self.status == self.Status.LIVE,
        }

    def get_team_fouls_info(self, team, period=None):
        """
        Calcula las faltas de equipo cometidas en el periodo actual (o especificado)
        y determina si el equipo está en BONUS (5 o más faltas en el cuarto).
        En reglamento FIBA:
        - Cada equipo dispone de un límite de 4 faltas de equipo por cuarto antes de entrar en bonus.
        - Al cometer la 5ª falta en un cuarto, entra en situación de BONUS y todas las faltas
          defensivas posteriores se penalizan automáticamente con 2 tiros libres para el rival.
        """
        p = period or self.current_period
        if p in [self.Period.NOT_STARTED, self.Period.FINISHED, self.Period.HALFTIME]:
            count = 0
        else:
            count = self.events.filter(
                team=team,
                period=p,
                event_type__in=[
                    MatchEvent.EventType.FOUL_PERSONAL,
                    MatchEvent.EventType.FOUL_TECHNICAL,
                    MatchEvent.EventType.FOUL_UNSPORTSMANLIKE,
                ]
            ).count()

        is_in_bonus = count >= 5
        return {
            "count": count,
            "limit": 5,
            "in_bonus": is_in_bonus,
            "remaining_to_bonus": max(0, 5 - count),
        }

    def get_on_court_player_ids(self, team):
        """
        Retorna la lista de IDs de jugadores actualmente marcados como 'En Pista' para un equipo.
        """
        from apps.analytics.models import PlayerMatchStat
        return list(
            PlayerMatchStat.objects.filter(
                match=self, team=team, is_on_court=True
            ).values_list("player_id", flat=True)
        )

    def has_valid_five_on_court(self, team):
        """
        Comprueba si el equipo tiene exactamente 5 jugadores marcados en pista (requisito y restricción de memoria).
        Si la plantilla total disponible es menor a 5, comprueba que todos los disponibles estén en pista.
        """
        from apps.teams.models import TeamMembership
        total_roster_count = TeamMembership.objects.filter(team=team, is_active=True).count()
        required_count = min(5, total_roster_count) if total_roster_count > 0 else 5
        on_court_count = len(self.get_on_court_player_ids(team))
        return on_court_count == required_count and on_court_count > 0

    def set_starting_five(self, team, player_ids):
        """
        Registra el quinteto inicial (5 jugadores) de un equipo.
        Marca is_starter=True e is_on_court=True para los seleccionados y is_on_court=False para el resto.
        """
        from apps.analytics.models import PlayerMatchStat
        from apps.teams.models import Player

        if len(player_ids) != 5:
            from apps.teams.models import TeamMembership
            total_roster = TeamMembership.objects.filter(team=team, is_active=True).count()
            if total_roster >= 5 or len(player_ids) != total_roster:
                raise ValueError("Se deben seleccionar exactamente 5 jugadores para el quinteto inicial.")

        # Asegurar estadísticas creadas para todos
        for p_id in player_ids:
            PlayerMatchStat.objects.get_or_create(
                match=self, player_id=p_id, defaults={"team": team}
            )

        # Desmarcar todos los de este equipo como en pista
        PlayerMatchStat.objects.filter(match=self, team=team).update(is_on_court=False)

        # Marcar los 5 seleccionados como titulares y en pista
        PlayerMatchStat.objects.filter(match=self, team=team, player_id__in=player_ids).update(
            is_starter=True, is_on_court=True
        )

        starter_players = Player.objects.filter(id__in=player_ids)
        names = ", ".join([f"#{p.jersey_number} {p.last_name or p.first_name}" for p in starter_players])

        event = MatchEvent.objects.create(
            match=self,
            period=self.current_period if self.current_period != self.Period.NOT_STARTED else self.Period.Q1,
            game_clock=self.game_clock,
            team=team,
            event_type=MatchEvent.EventType.STARTING_FIVE,
            points=0,
            description=f"Quinteto en pista confirmado ({team.acronym}): {names}"
        )
        return event

    def substitute_player(self, team, player_out_id, player_in_id):
        """
        Ejecuta una sustitución de jugadores entre el banquillo y la pista para un equipo.
        Valida que player_out esté en pista y player_in en banquillo (y no expulsado por 5 faltas).
        """
        from apps.analytics.models import PlayerMatchStat
        from apps.teams.models import Player

        stat_out = PlayerMatchStat.objects.filter(match=self, team=team, player_id=player_out_id).first()
        stat_in, _ = PlayerMatchStat.objects.get_or_create(
            match=self, player_id=player_in_id, defaults={"team": team}
        )

        if not stat_out or not stat_out.is_on_court:
            raise ValueError("El jugador que sale debe estar actualmente en pista.")

        if stat_in.is_on_court:
            raise ValueError("El jugador que entra ya está actualmente en pista.")

        if stat_in.fouls_committed >= 5:
            raise ValueError("El jugador que entra está eliminado del partido por acumulación de 5 faltas.")

        stat_out.is_on_court = False
        stat_out.save(update_fields=["is_on_court"])

        stat_in.is_on_court = True
        stat_in.save(update_fields=["is_on_court"])

        p_out = Player.objects.filter(id=player_out_id).first()
        p_in = Player.objects.filter(id=player_in_id).first()

        out_name = f"#{p_out.jersey_number} {p_out.full_name}" if p_out else "Jugador"
        in_name = f"#{p_in.jersey_number} {p_in.full_name}" if p_in else "Jugador"

        event = MatchEvent.objects.create(
            match=self,
            period=self.current_period if self.current_period != self.Period.NOT_STARTED else self.Period.Q1,
            game_clock=self.game_clock,
            team=team,
            player=p_in,
            event_type=MatchEvent.EventType.SUBSTITUTION,
            points=0,
            description=f"Sustitución: Entra {in_name}, Sale {out_name}"
        )
        return event

    def get_quarters_breakdown(self):
        """
        Retorna el desglose oficial de puntos por cuartos (Q1, Q2, Q3, Q4 y prórrogas)
        para el acta oficial de encuentro.
        """
        from django.db.models import Sum

        period_definitions = [
            (self.Period.Q1, "1º Cuarto", "1C"),
            (self.Period.Q2, "2º Cuarto", "2C"),
            (self.Period.Q3, "3º Cuarto", "3C"),
            (self.Period.Q4, "4º Cuarto", "4C"),
        ]

        has_ot1 = self.events.filter(period=self.Period.OT1, points__gt=0).exists()
        has_ot2 = self.events.filter(period=self.Period.OT2, points__gt=0).exists()
        if has_ot1:
            period_definitions.append((self.Period.OT1, "1ª Prórroga", "PR1"))
        if has_ot2:
            period_definitions.append((self.Period.OT2, "2ª Prórroga", "PR2"))

        periods = []
        total_home_events = 0
        total_away_events = 0

        for code, name, short_name in period_definitions:
            home_pts = self.events.filter(period=code, team=self.home_team).aggregate(s=Sum("points"))["s"] or 0
            away_pts = self.events.filter(period=code, team=self.away_team).aggregate(s=Sum("points"))["s"] or 0
            total_home_events += home_pts
            total_away_events += away_pts
            periods.append({
                "code": code,
                "name": name,
                "short_name": short_name,
                "home_pts": home_pts,
                "away_pts": away_pts,
            })

        # Si no hay eventos específicos registrados pero hay tanteo global (ej. partidos precargados)
        if total_home_events == 0 and total_away_events == 0 and (self.home_score > 0 or self.away_score > 0):
            h_q = self.home_score // 4
            h_rem = self.home_score % 4
            a_q = self.away_score // 4
            a_rem = self.away_score % 4
            periods = [
                {"code": "Q1", "name": "1º Cuarto", "short_name": "1C", "home_pts": h_q + (1 if h_rem > 0 else 0), "away_pts": a_q + (1 if a_rem > 0 else 0)},
                {"code": "Q2", "name": "2º Cuarto", "short_name": "2C", "home_pts": h_q + (1 if h_rem > 1 else 0), "away_pts": a_q + (1 if a_rem > 1 else 0)},
                {"code": "Q3", "name": "3º Cuarto", "short_name": "3C", "home_pts": h_q + (1 if h_rem > 2 else 0), "away_pts": a_q + (1 if a_rem > 2 else 0)},
                {"code": "Q4", "name": "4º Cuarto", "short_name": "4C", "home_pts": h_q, "away_pts": a_q},
            ]

        return {
            "periods": periods,
            "home_total": self.home_score,
            "away_total": self.away_score,
        }

    def __str__(self):
        return f"{self.home_team.acronym} {self.home_score} - {self.away_score} {self.away_team.acronym} ({self.get_status_display()})"


class MatchEvent(models.Model):
    """
    Registro cronológico de eventos/jugadas del partido en vivo (acta digital en tiempo real).
    """

    class EventType(models.TextChoices):
        POINT_1_MADE = "1PT_MADE", "Tiro Libre Anotado (+1)"
        POINT_1_MISSED = "1PT_MISS", "Tiro Libre Fallado"
        POINT_2_MADE = "2PT_MADE", "Canasta de 2 Anotada (+2)"
        POINT_2_MISSED = "2PT_MISS", "Tiro de 2 Fallado"
        POINT_3_MADE = "3PT_MADE", "Triple Anotado (+3)"
        POINT_3_MISSED = "3PT_MISS", "Triple Fallado"
        REBOUND_OFF = "REB_OFF", "Rebote Ofensivo"
        REBOUND_DEF = "REB_DEF", "Rebote Defensivo"
        ASSIST = "AST", "Asistencia"
        STEAL = "STL", "Robo de Balón"
        TURNOVER = "TOV", "Pérdida de Balón"
        BLOCK = "BLK", "Tapón"
        FOUL_PERSONAL = "PF", "Falta Personal"
        FOUL_TECHNICAL = "TF", "Falta Técnica"
        FOUL_UNSPORTSMANLIKE = "UF", "Falta Antideportiva"
        TIMEOUT = "TO", "Tiempo Muerto"
        SUBSTITUTION = "SUB", "Sustitución"
        STARTING_FIVE = "STARTING_FIVE", "Quinteto Inicial"
        CORRECTION = "CORRECTION", "Corrección de Marcador"
        PERIOD = "PERIOD", "Cambio de Periodo"

    match = models.ForeignKey(
        Match, on_delete=models.CASCADE, related_name="events", verbose_name="Partido"
    )
    period = models.CharField(max_length=5, choices=Match.Period.choices, verbose_name="Periodo")
    game_clock = models.CharField(max_length=10, default="10:00", verbose_name="Minuto/Reloj")
    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name="match_events", verbose_name="Equipo"
    )
    player = models.ForeignKey(
        Player, on_delete=models.SET_NULL, null=True, blank=True, related_name="match_events", verbose_name="Jugador"
    )
    event_type = models.CharField(
        max_length=20, choices=EventType.choices, verbose_name="Tipo de Evento"
    )
    points = models.SmallIntegerField(default=0, verbose_name="Puntos Sumados")
    description = models.CharField(max_length=255, blank=True, verbose_name="Descripción")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Evento de Partido"
        verbose_name_plural = "Eventos de Partidos"
        ordering = ["-created_at"]

    def __str__(self):
        player_str = f" - {self.player.full_name}" if self.player else ""
        return f"[{self.period} {self.game_clock}] {self.team.acronym}{player_str}: {self.get_event_type_display()}"


class DigitalScoreSheet(models.Model):
    """
    Acta digital oficial del partido cerrada y firmada.
    """

    match = models.OneToOneField(
        Match, on_delete=models.CASCADE, related_name="scoresheet", verbose_name="Partido"
    )
    is_closed = models.BooleanField(default=False, verbose_name="Acta Oficial Cerrada")
    referee_signature = models.CharField(max_length=150, blank=True, verbose_name="Firma / Nombre Árbitro Principal")
    table_official_signature = models.CharField(max_length=150, blank=True, verbose_name="Firma Mesa Arbitral")
    incidents_report = models.TextField(blank=True, verbose_name="Informe de Incidencias")
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name="Fecha y Hora de Cierre")

    class Meta:
        verbose_name = "Acta Digital"
        verbose_name_plural = "Actas Digitales"

    @property
    def referee_name(self):
        if not self.referee_signature:
            return "Juan Carlos García González"
        if "|" in self.referee_signature:
            return self.referee_signature.split("|")[0].strip()
        if "(Lic." in self.referee_signature:
            return self.referee_signature.split("(Lic.")[0].strip()
        return self.referee_signature

    @property
    def referee_license(self):
        if not self.referee_signature:
            return "FEB-48192"
        if "|" in self.referee_signature:
            parts = self.referee_signature.split("|")
            return parts[1].strip() if len(parts) > 1 else ""
        if "(Lic." in self.referee_signature:
            import re
            m = re.search(r'\(Lic\.\s*([^)]+)\)', self.referee_signature)
            if m:
                return m.group(1).strip()
        return ""

    @property
    def verification_code(self):
        """
        Genera el código único e inmutable de autenticación digital del acta oficial.
        """
        import hashlib
        date_str = self.closed_at.isoformat() if self.closed_at else (self.match.created_at.isoformat() if self.match else "2026")
        raw = f"ACTA-{self.match_id}-{self.referee_signature}-{self.table_official_signature}-{date_str}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12].upper()
        return f"QQ-SEC-{self.match_id:04d}-{digest}"

    def __str__(self):
        return f"Acta Oficial - {self.match}"
