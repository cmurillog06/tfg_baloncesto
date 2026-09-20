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

    @property
    def arena(self):
        return self.arena_name

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

    def clean(self):
        from django.core.exceptions import ValidationError
        import datetime
        super().clean()

        if self.first_name:
            self.first_name = self.first_name.strip()
            if len(self.first_name) < 2:
                raise ValidationError({"first_name": "El nombre debe tener al menos 2 caracteres."})

        if self.last_name:
            self.last_name = self.last_name.strip()
            if len(self.last_name) < 2:
                raise ValidationError({"last_name": "Los apellidos deben tener al menos 2 caracteres."})

        if self.height_cm is not None:
            if self.height_cm < 120 or self.height_cm > 245:
                raise ValidationError({"height_cm": "La altura debe estar comprendida entre 120 y 245 cm."})

        if self.weight_kg is not None:
            if float(self.weight_kg) < 40.0 or float(self.weight_kg) > 190.0:
                raise ValidationError({"weight_kg": "El peso debe estar comprendido entre 40 y 190 kg."})

        if self.birth_date:
            today = datetime.date.today()
            if self.birth_date > today:
                raise ValidationError({"birth_date": "La fecha de nacimiento no puede ser posterior al día de hoy."})
            age = (today - self.birth_date).days / 365.25
            if age < 12:
                raise ValidationError({"birth_date": "El jugador debe tener al menos 12 años para poseer ficha federada."})
            if age > 65:
                raise ValidationError({"birth_date": "La edad del jugador no puede superar los 65 años."})

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def current_membership(self):
        """
        Retorna la ficha de plantilla activa más reciente del jugador.
        """
        membership = self.team_memberships.filter(is_active=True).select_related("team", "season").order_by("-season__start_date").first()
        if not membership:
            membership = self.team_memberships.select_related("team", "season").order_by("-season__start_date").first()
        return membership

    @property
    def current_team(self):
        """
        Retorna el club actual activo del jugador.
        """
        membership = self.current_membership
        return membership.team if membership else None

    @property
    def jersey_number(self):
        """
        Retorna el número de dorsal del jugador en su plantilla activa.
        """
        membership = self.current_membership
        return membership.jersey_number if membership else ""

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

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()

        # Validación de rango de dorsal (0 a 99)
        if self.jersey_number is not None:
            if self.jersey_number < 0 or self.jersey_number > 99:
                raise ValidationError({"jersey_number": "El dorsal debe ser un número entero comprendido entre 0 y 99."})

        # 1. En un mismo equipo no pueden existir dos jugadores con el mismo número de dorsal activo durante la misma temporada
        if self.is_active and self.team_id and self.season_id and self.jersey_number is not None:
            existing_dorsal = TeamMembership.objects.filter(
                team_id=self.team_id,
                season_id=self.season_id,
                jersey_number=self.jersey_number,
                is_active=True
            ).exclude(pk=self.pk).select_related("player", "season").first()

            if existing_dorsal:
                player_name = existing_dorsal.player.full_name if existing_dorsal.player else "otro jugador"
                season_name = self.season.name if self.season_id else "la temporada seleccionada"
                raise ValidationError({
                    "jersey_number": f"El dorsal #{self.jersey_number} ya está asignado al jugador {player_name} con ficha activa en este equipo durante la temporada {season_name}."
                })

        if self.is_active and self.player_id and self.season_id:
            # Un jugador no puede tener más de una ficha activa en la misma temporada (en ningún equipo)
            existing_active = TeamMembership.objects.filter(
                player_id=self.player_id,
                season_id=self.season_id,
                is_active=True
            ).exclude(pk=self.pk).select_related("team").first()

            if existing_active:
                if existing_active.team_id == self.team_id:
                    raise ValidationError(
                        f"El jugador {self.player.full_name} ya tiene una ficha activa en este equipo para esta temporada."
                    )
                else:
                    raise ValidationError(
                        f"El jugador {self.player.full_name} ya está dado de alta en {existing_active.team.name} para esta temporada. Un jugador no puede estar activo simultáneamente en dos equipos."
                    )

    def __str__(self):
        return f"#{self.jersey_number} {self.player.full_name} - {self.team.name} ({self.season.name})"
