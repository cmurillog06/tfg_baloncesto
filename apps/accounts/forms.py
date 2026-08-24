from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import CustomUser, Profile


class UserRegisterForm(UserCreationForm):
    """
    Formulario de registro con selección de rol (Entrenador o Aficionado).
    """

    email = forms.EmailField(
        required=True,
        label="Correo Electrónico",
        widget=forms.EmailInput(
            attrs={"placeholder": "ejemplo@correo.com", "class": "form-control"}
        ),
    )
    first_name = forms.CharField(
        required=True,
        label="Nombre",
        widget=forms.TextInput(
            attrs={"placeholder": "Tu nombre", "class": "form-control"}
        ),
    )
    last_name = forms.CharField(
        required=True,
        label="Apellidos",
        widget=forms.TextInput(
            attrs={"placeholder": "Tus apellidos", "class": "form-control"}
        ),
    )
    role = forms.ChoiceField(
        choices=[
            (CustomUser.Role.FAN, "Aficionado / Espectador (Seguimiento, Marcadores y Chat)"),
            (CustomUser.Role.COACH, "Entrenador (Gestión de Plantillas e Inscripciones)"),
        ],
        label="Tipo de Usuario",
        initial=CustomUser.Role.FAN,
        widget=forms.Select(attrs={"class": "form-control select-role"}),
        help_text="Los roles de Mesa Arbitral y Administrador son designados por la federación/comité.",
    )

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"placeholder": "Nombre de usuario", "class": "form-control"}
        )
        self.fields["password1"].widget.attrs.update(
            {"placeholder": "Contraseña segura", "class": "form-control"}
        )
        self.fields["password2"].widget.attrs.update(
            {"placeholder": "Repite la contraseña", "class": "form-control"}
        )


class UserLoginForm(AuthenticationForm):
    """
    Formulario estilizado de inicio de sesión.
    """

    username = forms.CharField(
        label="Usuario o Correo",
        widget=forms.TextInput(
            attrs={"placeholder": "Nombre de usuario", "class": "form-control"}
        ),
    )
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(
            attrs={"placeholder": "••••••••", "class": "form-control"}
        ),
    )


class UserUpdateForm(forms.ModelForm):
    """
    Formulario de actualización de datos básicos de usuario.
    """

    email = forms.EmailField(
        label="Correo Electrónico",
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )
    first_name = forms.CharField(
        label="Nombre",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    last_name = forms.CharField(
        label="Apellidos",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    class Meta:
        model = CustomUser
        fields = ["first_name", "last_name", "email"]


class ProfileUpdateForm(forms.ModelForm):
    """
    Formulario de actualización del perfil complementario (avatar, teléfono, biografía).
    """

    phone = forms.CharField(
        required=False,
        label="Teléfono de Contacto",
        widget=forms.TextInput(
            attrs={"placeholder": "+34 600 000 000", "class": "form-control"}
        ),
    )
    avatar = forms.ImageField(
        required=False,
        label="Foto de Perfil",
        widget=forms.FileInput(attrs={"class": "form-control-file"}),
    )
    bio = forms.CharField(
        required=False,
        label="Biografía / Presentación",
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Cuéntanos sobre tu afición o trayectoria en el baloncesto...",
                "class": "form-control",
            }
        ),
    )

    class Meta:
        model = Profile
        fields = ["phone", "avatar", "bio"]
