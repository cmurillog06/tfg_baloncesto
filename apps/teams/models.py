from django.db import models
from django.conf import settings
from django.utils.text import slugify


class League(models.Model):
    """
    Competición o Liga (ej. Liga Senior Oro, Torneo Apertura).
    """

    name = models.CharField(max_length=150, unique=True, verbose_name="Nombre de la Liga")
    slug = models.SlugField(max_length=170, unique=True, blank=True)
    description = models.TextField(blank=True, verbose_name="Descripción")
    logo = models.ImageField(upload_to="leagues/", blank=True, null=True, verbose_name="Logo")
    is_active = models.BooleanField(default=True, verbose_name="Activa")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Liga"
        verbose_name_plural = "Ligas"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Season(models.Model):
    """
    Temporada deportiva dentro de una liga (ej. Temporada 2025/2026).
    """

    league = models.ForeignKey(
        League, on_delete=models.CASCADE, related_name="seasons", verbose_name="Liga"
    )
    name = models.CharField(max_length=100, verbose_name="Temporada (ej. 2025/2026)")
    start_date = models.DateField(verbose_name="Fecha de Inicio")
    end_date = models.DateField(verbose_name="Fecha de Finalización")
    is_current = models.BooleanField(default=True, verbose_name="Temporada Actual")

    class Meta:
        verbose_name = "Temporada"
        verbose_name_plural = "Temporadas"
        ordering = ["-start_date"]
        unique_together = ["league", "name"]

    def __str__(self):
        return f"{self.league.name} - {self.name}"


class Team(models.Model):
    """
    Equipo de baloncesto.
    """

    name = models.CharField(max_length=150, unique=True, verbose_name="Nombre del Equipo")
    slug = models.SlugField(max_length=170, unique=True, blank=True)
    acronym = models.CharField(max_length=4, verbose_name="Acrónimo (3-4 letras, ej. RMB, FCB)")
    logo = models.ImageField(upload_to="teams/", blank=True, null=True, verbose_name="Escudo")
    primary_color = models.CharField(max_length=7, default="#FF6600", verbose_name="Color Principal (HEX)")
    secondary_color = models.CharField(max_length=7, default="#1E293B", verbose_name="Color Secundario (HEX)")
    city = models.CharField(max_length=100, blank=True, verbose_name="Ciudad")
    arena_name = models.CharField(max_length=150, blank=True, verbose_name="Pabellón / Cancha")
    coach = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="coached_teams",
        verbose_name="Primer Entrenador",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Equipo"
        verbose_name_plural = "Equipos"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        if self.acronym:
            self.acronym = self.acronym.upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.acronym})"


class Player(models.Model):
    """
    Jugador de baloncesto.
    """

    class Position(models.TextChoices):
        POINT_GUARD = "PG", "Base"
        SHOOTING_GUARD = "SG", "Escolta"
        SMALL_FORWARD = "SF", "Alero"
        POWER_FORWARD = "PF", "Ala-Pívot"
        CENTER = "C", "Pívot"

    first_name = models.CharField(max_length=100, verbose_name="Nombre")
    last_name = models.CharField(max_length=100, verbose_name="Apellidos")
    birth_date = models.DateField(null=True, blank=True, verbose_name="Fecha de Nacimiento")
    height_cm = models.PositiveIntegerField(null=True, blank=True, verbose_name="Altura (cm)")
    weight_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Peso (kg)")
    position = models.CharField(
        max_length=3, choices=Position.choices, default=Position.SMALL_FORWARD, verbose_name="Posición Principal"
    )
    photo = models.ImageField(upload_to="players/", blank=True, null=True, verbose_name="Foto")
    is_active = models.BooleanField(default=True, verbose_name="Ficha Activa")

    class Meta:
        verbose_name = "Jugador"
        verbose_name_plural = "Jugadores"
        ordering = ["last_name", "first_name"]

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __str__(self):
        return f"{self.full_name} ({self.get_position_display()})"


class TeamMembership(models.Model):
    """
    Inscripción / Ficha de un jugador en una plantilla para una temporada determinada.
    """

    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name="roster_memberships", verbose_name="Equipo"
    )
    player = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name="team_memberships", verbose_name="Jugador"
    )
    season = models.ForeignKey(
        Season, on_delete=models.CASCADE, related_name="roster_memberships", verbose_name="Temporada"
    )
    jersey_number = models.PositiveIntegerField(verbose_name="Dorsal (0-99)")
    is_captain = models.BooleanField(default=False, verbose_name="Capitán")
    is_active = models.BooleanField(default=True, verbose_name="Activo en plantilla")

    class Meta:
        verbose_name = "Ficha de Plantilla"
        verbose_name_plural = "Fichas de Plantillas"
        ordering = ["jersey_number"]
        unique_together = [
            ("team", "season", "jersey_number"),
            ("team", "season", "player"),
        ]

    def __str__(self):
        return f"#{self.jersey_number} {self.player.full_name} - {self.team.name} ({self.season.name})"
