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

    def __str__(self):
        return f"Acta Oficial - {self.match}"
