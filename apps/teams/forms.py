from django import forms
from .models import Team, Player, TeamMembership, League, Season


class TeamMembershipForm(forms.ModelForm):
    """
    Formulario para inscribir a un jugador en una plantilla con su dorsal y capitanía.
    """

    class Meta:
        model = TeamMembership
        fields = ["player", "jersey_number", "is_captain"]
        widgets = {
            "player": forms.Select(attrs={"class": "form-control"}),
            "jersey_number": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Nº Dorsal (0-99)",
                    "min": 0,
                    "max": 99,
                }
            ),
            "is_captain": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
        }
        labels = {
            "player": "Jugador",
            "jersey_number": "Dorsal en Camiseta",
            "is_captain": "Capitán del Equipo",
        }

    def __init__(self, *args, team=None, season=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.team = team
        self.season = season

        # 1. Jugadores con ficha activa en CUALQUIER OTRO equipo
        other_teams_active_qs = TeamMembership.objects.filter(is_active=True)
        if self.team:
            other_teams_active_qs = other_teams_active_qs.exclude(team=self.team)
        other_active_ids = set(other_teams_active_qs.values_list("player_id", flat=True))

        # 2. Jugadores con ficha activa en este mismo equipo para esta temporada
        same_team_active_ids = set()
        if self.team and self.season:
            same_team_active_ids = set(
                TeamMembership.objects.filter(
                    team=self.team,
                    season=self.season,
                    is_active=True
                ).values_list("player_id", flat=True)
            )

        unavailable_ids = other_active_ids.union(same_team_active_ids)

        self.fields["player"].queryset = Player.objects.filter(
            is_active=True
        ).exclude(
            id__in=unavailable_ids
        ).order_by("last_name", "first_name")

    def clean(self):
        cleaned_data = super().clean()
        player = cleaned_data.get("player")
        jersey_number = cleaned_data.get("jersey_number")

        if player:
            # Comprobar si el jugador ya está dado de alta en otro club
            other_team_active = TeamMembership.objects.filter(
                player=player,
                is_active=True
            )
            if self.team:
                other_team_active = other_team_active.exclude(team=self.team)

            other_membership = other_team_active.select_related("team").first()
            if other_membership:
                raise forms.ValidationError(
                    f"El jugador {player.full_name} no puede ser inscrito porque ya tiene ficha activa en {other_membership.team.name}. "
                    "Un jugador no puede pertenecer simultáneamente a dos clubes distintos."
                )

            # Comprobar si ya está activo en este equipo para esta temporada
            if self.team and self.season:
                same_team_active = TeamMembership.objects.filter(
                    player=player,
                    team=self.team,
                    season=self.season,
                    is_active=True
                ).exclude(pk=self.instance.pk if self.instance else None).exists()

                if same_team_active:
                    raise forms.ValidationError(
                        f"El jugador {player.full_name} ya está dado de alta en la plantilla de este equipo para esta temporada."
                    )

        if jersey_number is not None and self.team and self.season:
            # Comprobar si el dorsal ya está ocupado en este equipo
            dorsal_taken = TeamMembership.objects.filter(
                team=self.team,
                season=self.season,
                jersey_number=jersey_number,
                is_active=True
            ).exclude(pk=self.instance.pk if self.instance else None).exists()

            if dorsal_taken:
                raise forms.ValidationError(
                    f"El dorsal #{jersey_number} ya está asignado a otro jugador activo en este equipo."
                )

        return cleaned_data


import os
import datetime


class PlayerValidationMixin:
    """
    Mixin con validaciones rigurosas para todos los campos de un jugador de baloncesto:
    - Nombre y Apellidos: no vacíos, mínimo 2 caracteres, sin números.
    - Altura: 120 cm - 245 cm.
    - Peso: 40.0 kg - 190.0 kg.
    - Fecha de Nacimiento: no futura, edad entre 12 y 65 años.
    - Fotografía: máx. 5 MB, formatos JPG, PNG, WebP.
    """

    def clean_first_name(self):
        first_name = self.cleaned_data.get("first_name", "").strip()
        if not first_name or len(first_name) < 2:
            raise forms.ValidationError("El nombre debe tener al menos 2 caracteres.")
        if any(char.isdigit() for char in first_name):
            raise forms.ValidationError("El nombre no puede contener números.")
        return first_name

    def clean_last_name(self):
        last_name = self.cleaned_data.get("last_name", "").strip()
        if not last_name or len(last_name) < 2:
            raise forms.ValidationError("Los apellidos deben tener al menos 2 caracteres.")
        if any(char.isdigit() for char in last_name):
            raise forms.ValidationError("Los apellidos no pueden contener números.")
        return last_name

    def clean_height_cm(self):
        height = self.cleaned_data.get("height_cm")
        if height is not None:
            if height < 120 or height > 245:
                raise forms.ValidationError("La altura debe estar comprendida entre 120 y 245 cm.")
        return height

    def clean_weight_kg(self):
        weight = self.cleaned_data.get("weight_kg")
        if weight is not None:
            if float(weight) < 40.0 or float(weight) > 190.0:
                raise forms.ValidationError("El peso debe estar comprendido entre 40 y 190 kg.")
        return weight

    def clean_birth_date(self):
        birth_date = self.cleaned_data.get("birth_date")
        if birth_date:
            today = datetime.date.today()
            if birth_date > today:
                raise forms.ValidationError("La fecha de nacimiento no puede ser posterior al día de hoy.")
            age = (today - birth_date).days / 365.25
            if age < 12:
                raise forms.ValidationError("El jugador debe tener al menos 12 años para tener ficha federada.")
            if age > 65:
                raise forms.ValidationError("La edad del jugador no puede superar los 65 años.")
        return birth_date

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if photo and hasattr(photo, "size"):
            if photo.size > 5 * 1024 * 1024:
                raise forms.ValidationError("La fotografía no puede superar los 5 MB de tamaño.")
            ext = os.path.splitext(photo.name)[1].lower()
            if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
                raise forms.ValidationError("Formato no válido. Se admiten archivos JPG, PNG y WebP.")
        return photo


class PlayerForm(PlayerValidationMixin, forms.ModelForm):
    """
    Formulario para crear o editar la ficha técnica de un jugador.
    """

    class Meta:
        model = Player
        fields = [
            "first_name",
            "last_name",
            "birth_date",
            "height_cm",
            "weight_kg",
            "position",
            "photo",
            "is_active",
        ]
        widgets = {
            "first_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Nombre", "minlength": "2"}
            ),
            "last_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Apellidos", "minlength": "2"}
            ),
            "birth_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "height_cm": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Altura en cm (ej. 198)",
                    "min": 120,
                    "max": 245,
                }
            ),
            "weight_kg": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Peso en kg (ej. 92.5)",
                    "step": "0.1",
                    "min": 40,
                    "max": 190,
                }
            ),
            "position": forms.Select(attrs={"class": "form-control"}),
            "photo": forms.FileInput(attrs={"class": "form-control-file", "accept": "image/jpeg,image/png,image/webp,image/*"}),
            "is_active": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
        }
        labels = {
            "first_name": "Nombre",
            "last_name": "Apellidos",
            "birth_date": "Fecha de Nacimiento",
            "height_cm": "Altura (cm)",
            "weight_kg": "Peso (kg)",
            "position": "Posición Principal (FIBA)",
            "photo": "Fotografía Oficial",
            "is_active": "Ficha Activa",
        }


class CoachPlayerCreateForm(PlayerValidationMixin, forms.ModelForm):
    """
    Formulario para que el entrenador dé de alta a un jugador nuevo con sus datos biométricos,
    posición, fotografía y le asigne un dorsal y capitanía directamente en su plantilla.
    """
    jersey_number = forms.IntegerField(
        min_value=0,
        max_value=99,
        label="Dorsal (0-99)",
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "ej. 23", "min": 0, "max": 99})
    )
    is_captain = forms.BooleanField(
        required=False,
        label="Designar como Capitán",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )

    class Meta:
        model = Player
        fields = [
            "first_name",
            "last_name",
            "birth_date",
            "height_cm",
            "weight_kg",
            "position",
            "photo",
        ]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre", "minlength": "2"}),
            "last_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Apellidos", "minlength": "2"}),
            "birth_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "height_cm": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Altura en cm (ej. 198)", "min": 120, "max": 245}),
            "weight_kg": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Peso en kg (ej. 92.5)", "step": "0.1", "min": 40, "max": 190}),
            "position": forms.Select(attrs={"class": "form-control"}),
            "photo": forms.FileInput(attrs={"class": "form-control-file", "accept": "image/jpeg,image/png,image/webp,image/*"}),
        }
        labels = {
            "first_name": "Nombre",
            "last_name": "Apellidos",
            "birth_date": "Fecha de Nacimiento",
            "height_cm": "Altura (cm)",
            "weight_kg": "Peso (kg)",
            "position": "Posición en Cancha",
            "photo": "Fotografía Oficial",
        }

    def __init__(self, *args, team=None, season=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.team = team
        self.season = season

    def clean_jersey_number(self):
        jersey = self.cleaned_data.get("jersey_number")
        if jersey is not None:
            if jersey < 0 or jersey > 99:
                raise forms.ValidationError("El dorsal debe ser un número entero entre 0 y 99.")
            if self.team and self.season:
                dorsal_taken = TeamMembership.objects.filter(
                    team=self.team,
                    season=self.season,
                    jersey_number=jersey,
                    is_active=True
                ).exists()
                if dorsal_taken:
                    raise forms.ValidationError(
                        f"El dorsal #{jersey} ya está ocupado por otro jugador en la plantilla."
                    )
        return jersey


class CoachPlayerEditForm(PlayerValidationMixin, forms.ModelForm):
    """
    Formulario para que el entrenador modifique los datos biométricos, dorsal,
    posición o fotografía de un jugador de su plantilla.
    """
    jersey_number = forms.IntegerField(
        min_value=0,
        max_value=99,
        label="Dorsal (0-99)",
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "ej. 23", "min": 0, "max": 99})
    )
    is_captain = forms.BooleanField(
        required=False,
        label="Designar como Capitán",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )

    class Meta:
        model = Player
        fields = [
            "first_name",
            "last_name",
            "birth_date",
            "height_cm",
            "weight_kg",
            "position",
            "photo",
        ]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre", "minlength": "2"}),
            "last_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Apellidos", "minlength": "2"}),
            "birth_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "height_cm": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Altura en cm (ej. 198)", "min": 120, "max": 245}),
            "weight_kg": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Peso en kg (ej. 92.5)", "step": "0.1", "min": 40, "max": 190}),
            "position": forms.Select(attrs={"class": "form-control"}),
            "photo": forms.FileInput(attrs={"class": "form-control-file", "accept": "image/jpeg,image/png,image/webp"}),
        }
        labels = {
            "first_name": "Nombre",
            "last_name": "Apellidos",
            "birth_date": "Fecha de Nacimiento",
            "height_cm": "Altura (cm)",
            "weight_kg": "Peso (kg)",
            "position": "Posición en Cancha",
            "photo": "Fotografía Oficial",
        }

    def __init__(self, *args, team=None, season=None, membership=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.team = team
        self.season = season
        self.membership = membership
        if membership:
            self.fields["jersey_number"].initial = membership.jersey_number
            self.fields["is_captain"].initial = membership.is_captain

    def clean_jersey_number(self):
        jersey = self.cleaned_data.get("jersey_number")
        if jersey is not None:
            if jersey < 0 or jersey > 99:
                raise forms.ValidationError("El dorsal debe ser un número entero entre 0 y 99.")
            if self.team and self.season:
                query = TeamMembership.objects.filter(
                    team=self.team,
                    season=self.season,
                    jersey_number=jersey,
                    is_active=True
                )
                if self.membership:
                    query = query.exclude(pk=self.membership.pk)
                if query.exists():
                    raise forms.ValidationError(
                        f"El dorsal #{jersey} ya está ocupado por otro jugador activo en este equipo."
                    )
        return jersey


class TeamForm(forms.ModelForm):
    """
    Formulario para actualizar datos del club (pabellón, ciudad, colores).
    """

    class Meta:
        model = Team
        fields = [
            "name",
            "acronym",
            "city",
            "arena_name",
            "primary_color",
            "secondary_color",
            "logo",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "acronym": forms.TextInput(attrs={"class": "form-control"}),
            "city": forms.TextInput(attrs={"class": "form-control"}),
            "arena_name": forms.TextInput(attrs={"class": "form-control"}),
            "primary_color": forms.TextInput(
                attrs={"class": "form-control", "type": "color"}
            ),
            "secondary_color": forms.TextInput(
                attrs={"class": "form-control", "type": "color"}
            ),
            "logo": forms.FileInput(attrs={"class": "form-control-file"}),
        }
