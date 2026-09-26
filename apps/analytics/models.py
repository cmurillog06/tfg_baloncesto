from django.db import models
from apps.teams.models import Team, Season, Player
from apps.matches.models import Match


class Standing(models.Model):
    """
    Tabla de clasificación de un equipo en una temporada.
    """

    season = models.ForeignKey(
        Season, on_delete=models.CASCADE, related_name="standings", verbose_name="Temporada"
    )
    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name="standings", verbose_name="Equipo"
    )
    games_played = models.PositiveIntegerField(default=0, verbose_name="Partidos Jugados (PJ)")
    wins = models.PositiveIntegerField(default=0, verbose_name="Victorias (PG)")
    losses = models.PositiveIntegerField(default=0, verbose_name="Derrotas (PP)")
    points_for = models.PositiveIntegerField(default=0, verbose_name="Puntos a Favor (PF)")
    points_against = models.PositiveIntegerField(default=0, verbose_name="Puntos en Contra (PC)")
    points_diff = models.IntegerField(default=0, verbose_name="Diferencia de Puntos (DIF)")
    league_points = models.PositiveIntegerField(default=0, verbose_name="Puntos Clasificación (PTS)")

    class Meta:
        verbose_name = "Clasificación"
        verbose_name_plural = "Clasificaciones"
        ordering = ["-league_points", "-points_diff", "-points_for"]
        unique_together = ["season", "team"]

    def update_totals(self):
        self.games_played = self.wins + self.losses
        self.points_diff = self.points_for - self.points_against
        self.league_points = (self.wins * 2) + self.losses

    def save(self, *args, **kwargs):
        self.update_totals()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.team.acronym} - {self.league_points} pts ({self.season.name})"


class PlayerMatchStat(models.Model):
    """
    Hoja estadística individual (Box Score) de un jugador en un partido específico.
    """

    match = models.ForeignKey(
        Match, on_delete=models.CASCADE, related_name="player_stats", verbose_name="Partido"
    )
    player = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name="match_stats", verbose_name="Jugador"
    )
    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name="player_match_stats", verbose_name="Equipo"
    )
    minutes_played = models.PositiveIntegerField(default=0, verbose_name="Minutos Jugados")
    points = models.PositiveIntegerField(default=0, verbose_name="Puntos Totales")
    is_starter = models.BooleanField(default=False, verbose_name="Titular / Quinteto Inicial")
    is_on_court = models.BooleanField(default=False, verbose_name="En Pista")

    # Tiros
    field_goals_made = models.PositiveIntegerField(default=0, verbose_name="Tiros de Campo Anotados (T2/T3)")
    field_goals_attempted = models.PositiveIntegerField(default=0, verbose_name="Tiros de Campo Intentados")
    three_points_made = models.PositiveIntegerField(default=0, verbose_name="Triples Anotados")
    three_points_attempted = models.PositiveIntegerField(default=0, verbose_name="Triples Intentados")
    free_throws_made = models.PositiveIntegerField(default=0, verbose_name="Tiros Libres Anotados")
    free_throws_attempted = models.PositiveIntegerField(default=0, verbose_name="Tiros Libres Intentados")

    # Rebotes
    rebounds_off = models.PositiveIntegerField(default=0, verbose_name="Rebotes Ofensivos")
    rebounds_def = models.PositiveIntegerField(default=0, verbose_name="Rebotes Defensivos")

    # Otras acciones
    assists = models.PositiveIntegerField(default=0, verbose_name="Asistencias")
    steals = models.PositiveIntegerField(default=0, verbose_name="Robos")
    turnovers = models.PositiveIntegerField(default=0, verbose_name="Pérdidas")
    blocks_made = models.PositiveIntegerField(default=0, verbose_name="Tapones a Favor")
    blocks_received = models.PositiveIntegerField(default=0, verbose_name="Tapones Recibidos")
    fouls_committed = models.PositiveIntegerField(default=0, verbose_name="Faltas Personales Cometidas")
    fouls_received = models.PositiveIntegerField(default=0, verbose_name="Faltas Recibidas")

    # Métrica de Valoración FIBA / ACB (PIR)
    valuation_pir = models.IntegerField(default=0, verbose_name="Valoración (PIR)")

    class Meta:
        verbose_name = "Estadística de Jugador por Partido"
        verbose_name_plural = "Estadísticas de Jugadores por Partido"
        unique_together = ["match", "player"]
        ordering = ["-points", "-valuation_pir"]

    @property
    def total_rebounds(self):
        return self.rebounds_off + self.rebounds_def

    @property
    def two_points_made(self):
        return max(0, self.field_goals_made - self.three_points_made)

    @property
    def two_points_attempted(self):
        return max(0, self.field_goals_attempted - self.three_points_attempted)

    def compute_pir(self):
        """
        Cálculo oficial de Valoración ACB/FIBA:
        (PTS + REB_TOT + AST + STL + BLK_MADE + FOUL_REC) -
        ((FGA - FGM) + (FTA - FTM) + TOV + BLK_REC + FOUL_COMM)
        """
        positive_val = (
            self.points
            + self.total_rebounds
            + self.assists
            + self.steals
            + self.blocks_made
            + self.fouls_received
        )
        missed_fg = max(0, self.field_goals_attempted - self.field_goals_made)
        missed_ft = max(0, self.free_throws_attempted - self.free_throws_made)
        negative_val = (
            missed_fg
            + missed_ft
            + self.turnovers
            + self.blocks_received
            + self.fouls_committed
        )
        self.valuation_pir = positive_val - negative_val
        return self.valuation_pir

    def save(self, *args, **kwargs):
        self.compute_pir()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.player.full_name} ({self.team.acronym}) - {self.points} pts, {self.valuation_pir} val"
