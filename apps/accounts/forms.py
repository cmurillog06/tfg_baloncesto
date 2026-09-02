import re
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.core.validators import FileExtensionValidator
from .models import CustomUser, Profile


class UserRegisterForm(UserCreationForm):
    """
    Formulario de registro público: asigna automáticamente el rol de Aficionado (FAN).
    """

    email = forms.EmailField(
        required=True,
        max_length=50,
        label="Correo Electrónico",
        widget=forms.EmailInput(
            attrs={"placeholder": "ejemplo@correo.com", "class": "form-control", "maxlength": "50"}
        ),
    )

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = (
            "username",
            "email",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].max_length = 30
        self.fields["username"].widget.attrs.update(
            {"placeholder": "Nombre de usuario", "class": "form-control", "maxlength": "30"}
        )
        self.fields["password1"].max_length = 30
        self.fields["password1"].widget.attrs.update(
            {"placeholder": "Contraseña segura", "class": "form-control", "maxlength": "30"}
        )
        self.fields["password2"].max_length = 30
        self.fields["password2"].widget.attrs.update(
            {"placeholder": "Repite la contraseña", "class": "form-control", "maxlength": "30"}
        )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = CustomUser.Role.FAN
        if commit:
            user.save()
        return user

    def clean_username(self):
        username = self.cleaned_data.get("username", "").strip()
        if len(username) < 3:
            raise forms.ValidationError("El nombre de usuario debe contener al menos 3 caracteres.")
        if len(username) > 30:
            raise forms.ValidationError("El nombre de usuario no puede superar los 30 caracteres.")
        if username.isdigit():
            raise forms.ValidationError("El nombre de usuario no puede estar compuesto únicamente por números.")
        if not any(c.isalpha() for c in username):
            raise forms.ValidationError("El nombre de usuario debe contener al menos una letra (tipo texto/alfanumérico).")
        if CustomUser.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Ya existe una cuenta registrada con este nombre de usuario.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()
        if not email:
            raise forms.ValidationError("Debes proporcionar un correo electrónico válido.")
        if len(email) > 50:
            raise forms.ValidationError("El correo electrónico no puede superar los 50 caracteres.")
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Ya existe una cuenta registrada con este correo electrónico. Inicia sesión o utiliza otro correo.")
        return email

    def clean_password1(self):
        password = self.cleaned_data.get("password1")
        if password and len(password) > 30:
            raise forms.ValidationError("La contraseña no puede superar los 30 caracteres.")
        return password


from django.contrib.auth import authenticate


class UserLoginForm(AuthenticationForm):
    """
    Formulario estilizado de inicio de sesión: permite identificarse por usuario o correo.
    """

    username = forms.CharField(
        label="Nombre de Usuario o Correo Electrónico",
        widget=forms.TextInput(
            attrs={"placeholder": "Nombre de usuario o correo", "class": "form-control"}
        ),
    )
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(
            attrs={"placeholder": "••••••••", "class": "form-control"}
        ),
    )

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if username and password:
            if "@" in username:
                user_match = CustomUser.objects.filter(email__iexact=username).first()
                if user_match:
                    username = user_match.username
                    self.cleaned_data["username"] = username

            self.user_cache = authenticate(
                self.request, username=username, password=password
            )
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            else:
                self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data


class UserUpdateForm(forms.ModelForm):
    """
    Formulario de actualización de datos de cuenta: Nombre de Usuario y Correo Electrónico.
    """

    username = forms.CharField(
        max_length=30,
        label="Nombre de Usuario",
        widget=forms.TextInput(
            attrs={"placeholder": "Nombre de usuario", "class": "form-control", "maxlength": "30"}
        ),
    )
    email = forms.EmailField(
        max_length=50,
        label="Correo Electrónico",
        widget=forms.EmailInput(
            attrs={"placeholder": "ejemplo@correo.com", "class": "form-control", "maxlength": "50"}
        ),
    )

    class Meta:
        model = CustomUser
        fields = ["username", "email"]

    def clean_username(self):
        username = self.cleaned_data.get("username", "").strip()
        if len(username) < 3:
            raise forms.ValidationError("El nombre de usuario debe contener al menos 3 caracteres.")
        if len(username) > 30:
            raise forms.ValidationError("El nombre de usuario no puede superar los 30 caracteres.")
        if username.isdigit():
            raise forms.ValidationError("El nombre de usuario no puede estar compuesto únicamente por números.")
        if not any(c.isalpha() for c in username):
            raise forms.ValidationError("El nombre de usuario debe contener al menos una letra (tipo texto/alfanumérico).")
        if CustomUser.objects.filter(username__iexact=username).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ya existe otra cuenta registrada con este nombre de usuario.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()
        if not email:
            raise forms.ValidationError("Debes proporcionar un correo electrónico válido.")
        if len(email) > 50:
            raise forms.ValidationError("El correo electrónico no puede superar los 50 caracteres.")
        if CustomUser.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ya existe otra cuenta registrada con este correo electrónico.")
        return email


class ProfileUpdateForm(forms.ModelForm):
    """
    Formulario de actualización del perfil complementario (avatar, teléfono, biografía).
    """

    phone = forms.CharField(
        required=False,
        max_length=20,
        label="Teléfono de Contacto",
        widget=forms.TextInput(
            attrs={"placeholder": "+34 600 000 000", "class": "form-control", "maxlength": "20"}
        ),
    )
    avatar = forms.ImageField(
        required=False,
        label="Foto de Perfil / Avatar",
        widget=forms.FileInput(attrs={"class": "form-control-file", "accept": ".png,.jpg,.jpeg,.webp"}),
        validators=[FileExtensionValidator(allowed_extensions=["png", "jpg", "jpeg", "webp"])],
    )
    bio = forms.CharField(
        required=False,
        max_length=250,
        label="Biografía o Presentación",
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Cuéntanos sobre tu afición o experiencia en el baloncesto...",
                "class": "form-control",
                "maxlength": "250",
            }
        ),
    )

    class Meta:
        model = Profile
        fields = ["phone", "avatar", "bio"]

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "").strip()
        if phone:
            if not re.match(r"^(\+)?[0-9\s\-]+$", phone):
                raise forms.ValidationError("El teléfono contiene caracteres no válidos.")

            digits_only = re.sub(r"\D", "", phone)

            if phone.startswith("+34") or phone.startswith("0034"):
                national_part = digits_only[4:] if phone.startswith("0034") else digits_only[2:]
                if len(national_part) != 9 or national_part[0] not in "6789":
                    raise forms.ValidationError("Un teléfono español con prefijo +34 debe tener exactamente 9 dígitos que empiecen por 6, 7, 8 o 9 (ej: +34 600 123 456).")
            elif not phone.startswith("+"):
                if len(digits_only) != 9 or digits_only[0] not in "6789":
                    raise forms.ValidationError("El número de teléfono debe tener exactamente 9 dígitos válidos que empiecen por 6, 7, 8 o 9 (ej: 600 123 456).")
            else:
                if len(digits_only) < 10 or len(digits_only) > 15:
                    raise forms.ValidationError("El número de teléfono internacional debe tener entre 10 y 15 dígitos.")
        return phone

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if avatar and hasattr(avatar, "name"):
            ext = avatar.name.split(".")[-1].lower()
            if ext not in ["png", "jpg", "jpeg", "webp"]:
                raise forms.ValidationError("Formato no admitido. Usa imágenes en formato PNG o JPG.")
            if avatar.size > 5 * 1024 * 1024:
                raise forms.ValidationError("La imagen no puede superar los 5 MB de tamaño.")
        return avatar
