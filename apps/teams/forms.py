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

        if team and season:
            # Excluir a los jugadores que ya están en activo en este equipo para esta temporada
            active_player_ids = TeamMembership.objects.filter(
                team=team, season=season, is_active=True
            ).values_list("player_id", flat=True)
            self.fields["player"].queryset = Player.objects.exclude(
                id__in=active_player_ids
            ).order_by("last_name", "first_name")


class PlayerForm(forms.ModelForm):
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
                attrs={"class": "form-control", "placeholder": "Nombre"}
            ),
            "last_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Apellidos"}
            ),
            "birth_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "height_cm": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Altura en cm (ej. 198)",
                }
            ),
            "weight_kg": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Peso en kg (ej. 92.5)",
                }
            ),
            "position": forms.Select(attrs={"class": "form-control"}),
            "photo": forms.FileInput(attrs={"class": "form-control-file"}),
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
