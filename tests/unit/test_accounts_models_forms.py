import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.accounts.models import CustomUser, Profile
from apps.accounts.forms import (
    UserRegisterForm,
    UserLoginForm,
    UserUpdateForm,
    ProfileUpdateForm,
)


@pytest.mark.django_db
class TestCustomUserModelAndProfile:
    """Pruebas unitarias para el modelo CustomUser y Profile."""

    def test_customuser_default_role_is_fan(self):
        user = CustomUser.objects.create_user(
            username="fan_default", email="fan_def@test.com", password="Password123!"
        )
        assert user.role == CustomUser.Role.FAN

    def test_customuser_role_choices(self):
        roles = [choice[0] for choice in CustomUser.Role.choices]
        assert "ADMIN" in roles
        assert "TABLE_OFFICIAL" in roles
        assert "REFEREE" in roles
        assert "COACH" in roles
        assert "FAN" in roles

    def test_customuser_is_table_official_property_for_table_official(self, table_official_user):
        assert table_official_user.is_table_official is True

    def test_customuser_is_table_official_property_for_admin(self, admin_user):
        assert admin_user.is_table_official is True

    def test_customuser_is_table_official_property_for_fan(self, fan_user):
        assert fan_user.is_table_official is False

    def test_customuser_is_referee_property_for_referee(self, referee_user):
        assert referee_user.is_referee is True

    def test_customuser_is_referee_property_for_admin(self, admin_user):
        assert admin_user.is_referee is True

    def test_customuser_is_referee_property_for_fan(self, fan_user):
        assert fan_user.is_referee is False

    def test_customuser_is_coach_property_for_coach(self, coach_user):
        assert coach_user.is_coach is True

    def test_customuser_is_coach_property_for_admin(self, admin_user):
        assert admin_user.is_coach is True

    def test_customuser_is_coach_property_for_fan(self, fan_user):
        assert fan_user.is_coach is False

    def test_customuser_is_fan_property_for_fan(self, fan_user):
        assert fan_user.is_fan is True

    def test_customuser_is_fan_property_for_coach(self, coach_user):
        assert coach_user.is_fan is False

    def test_customuser_str_representation(self, fan_user):
        assert "aficionado_fan" in str(fan_user)
        assert "Aficionado" in str(fan_user)

    def test_customuser_create_user_success(self):
        user = CustomUser.objects.create_user(
            username="newuser", email="newuser@test.com", password="Password123!"
        )
        assert user.pk is not None
        assert user.check_password("Password123!") is True

    def test_customuser_create_superuser_success(self):
        su = CustomUser.objects.create_superuser(
            username="super", email="super@test.com", password="SuperPassword123!"
        )
        assert su.is_superuser is True
        assert su.is_staff is True

    def test_profile_auto_created_via_signal_on_customuser_creation(self):
        user = CustomUser.objects.create_user(
            username="signal_user", email="signal@test.com", password="Password123!"
        )
        assert hasattr(user, "profile")
        assert user.profile is not None

    def test_profile_str_representation(self, fan_user):
        assert f"Perfil de {fan_user.username}" == str(fan_user.profile)

    def test_profile_update_fields(self, fan_user):
        profile = fan_user.profile
        profile.phone = "+34 612 345 678"
        profile.bio = "Apasionado del baloncesto ACB y local."
        profile.save()
        profile.refresh_from_db()
        assert profile.phone == "+34 612 345 678"
        assert "Apasionado" in profile.bio


@pytest.mark.django_db
class TestUserRegisterForm:
    """Pruebas unitarias para el formulario de registro de usuarios."""

    def test_register_form_valid_data_creates_fan_user(self):
        data = {
            "username": "usuario_valido",
            "email": "usuario_valido@correo.com",
            "password1": "PasswordValida123!",
            "password2": "PasswordValida123!",
        }
        form = UserRegisterForm(data=data)
        assert form.is_valid()
        user = form.save()
        assert user.pk is not None
        assert user.role == CustomUser.Role.FAN
        assert user.username == "usuario_valido"

    def test_register_form_short_username_invalid(self):
        data = {
            "username": "ab",
            "email": "short@correo.com",
            "password1": "Password123!",
            "password2": "Password123!",
        }
        form = UserRegisterForm(data=data)
        assert not form.is_valid()
        assert "username" in form.errors

    def test_register_form_long_username_invalid(self):
        data = {
            "username": "a" * 31,
            "email": "long@correo.com",
            "password1": "Password123!",
            "password2": "Password123!",
        }
        form = UserRegisterForm(data=data)
        assert not form.is_valid()
        assert "username" in form.errors

    def test_register_form_all_digits_username_invalid(self):
        data = {
            "username": "123456",
            "email": "digits@correo.com",
            "password1": "Password123!",
            "password2": "Password123!",
        }
        form = UserRegisterForm(data=data)
        assert not form.is_valid()
        assert "username" in form.errors

    def test_register_form_no_alpha_username_invalid(self):
        data = {
            "username": "_--_--",
            "email": "symbols@correo.com",
            "password1": "Password123!",
            "password2": "Password123!",
        }
        form = UserRegisterForm(data=data)
        assert not form.is_valid()
        assert "username" in form.errors

    def test_register_form_duplicate_username_invalid(self, fan_user):
        data = {
            "username": fan_user.username,
            "email": "otro_correo@test.com",
            "password1": "Password123!",
            "password2": "Password123!",
        }
        form = UserRegisterForm(data=data)
        assert not form.is_valid()
        assert "username" in form.errors

    def test_register_form_empty_email_invalid(self):
        data = {
            "username": "usuariotest",
            "email": "",
            "password1": "Password123!",
            "password2": "Password123!",
        }
        form = UserRegisterForm(data=data)
        assert not form.is_valid()
        assert "email" in form.errors

    def test_register_form_long_email_invalid(self):
        data = {
            "username": "usuariolongemail",
            "email": "a" * 45 + "@correo.com",  # > 50 chars
            "password1": "Password123!",
            "password2": "Password123!",
        }
        form = UserRegisterForm(data=data)
        assert not form.is_valid()
        assert "email" in form.errors

    def test_register_form_duplicate_email_invalid(self, fan_user):
        data = {
            "username": "usuario_unico",
            "email": fan_user.email,
            "password1": "Password123!",
            "password2": "Password123!",
        }
        form = UserRegisterForm(data=data)
        assert not form.is_valid()
        assert "email" in form.errors

    def test_register_form_password_mismatch_invalid(self):
        data = {
            "username": "usuariotest2",
            "email": "test2@correo.com",
            "password1": "Password123!",
            "password2": "DifferentPassword456!",
        }
        form = UserRegisterForm(data=data)
        assert not form.is_valid()
        assert "password2" in form.errors or "__all__" in form.errors

    def test_register_form_long_password_invalid(self):
        data = {
            "username": "usuariotest3",
            "email": "test3@correo.com",
            "password1": "P" * 31,
            "password2": "P" * 31,
        }
        form = UserRegisterForm(data=data)
        assert not form.is_valid()
        assert "password1" in form.errors


@pytest.mark.django_db
class TestUserLoginForm:
    """Pruebas unitarias para el formulario de login."""

    def test_login_form_valid_with_username(self, fan_user):
        data = {
            "username": fan_user.username,
            "password": "FanPassword123!",
        }
        form = UserLoginForm(data=data)
        assert form.is_valid()
        assert form.get_user() == fan_user

    def test_login_form_valid_with_email(self, fan_user):
        data = {
            "username": fan_user.email,
            "password": "FanPassword123!",
        }
        form = UserLoginForm(data=data)
        assert form.is_valid()
        assert form.get_user() == fan_user

    def test_login_form_invalid_credentials(self, fan_user):
        data = {
            "username": fan_user.username,
            "password": "WrongPassword999!",
        }
        form = UserLoginForm(data=data)
        assert not form.is_valid()
        assert "__all__" in form.errors


@pytest.mark.django_db
class TestUserUpdateForm:
    """Pruebas unitarias para el formulario de actualización de usuario."""

    def test_user_update_form_valid(self, fan_user):
        data = {
            "username": "fan_updated",
            "email": "fan_updated@test.com",
        }
        form = UserUpdateForm(data=data, instance=fan_user)
        assert form.is_valid()
        updated_user = form.save()
        assert updated_user.username == "fan_updated"
        assert updated_user.email == "fan_updated@test.com"

    def test_user_update_form_duplicate_username_excludes_self(self, fan_user):
        data = {
            "username": fan_user.username,
            "email": "new_email@test.com",
        }
        form = UserUpdateForm(data=data, instance=fan_user)
        assert form.is_valid()

    def test_user_update_form_duplicate_username_other_fails(self, fan_user, admin_user):
        data = {
            "username": admin_user.username,
            "email": "different@test.com",
        }
        form = UserUpdateForm(data=data, instance=fan_user)
        assert not form.is_valid()
        assert "username" in form.errors

    def test_user_update_form_duplicate_email_excludes_self(self, fan_user):
        data = {
            "username": "new_username_val",
            "email": fan_user.email,
        }
        form = UserUpdateForm(data=data, instance=fan_user)
        assert form.is_valid()

    def test_user_update_form_duplicate_email_other_fails(self, fan_user, admin_user):
        data = {
            "username": "new_username_val",
            "email": admin_user.email,
        }
        form = UserUpdateForm(data=data, instance=fan_user)
        assert not form.is_valid()
        assert "email" in form.errors


@pytest.mark.django_db
class TestProfileUpdateForm:
    """Pruebas unitarias para el formulario de perfil."""

    def test_profile_update_form_valid_phone_and_bio(self, fan_user):
        data = {
            "phone": "+34 612 345 678",
            "bio": "Entusiasta del baloncesto y analista aficionado.",
        }
        form = ProfileUpdateForm(data=data, instance=fan_user.profile)
        assert form.is_valid()
        profile = form.save()
        assert profile.phone == "+34 612 345 678"

    def test_profile_update_form_invalid_phone_formats(self, fan_user):
        # Letras en el teléfono
        data = {
            "phone": "600ABC123",
            "bio": "Bio test",
        }
        form = ProfileUpdateForm(data=data, instance=fan_user.profile)
        assert not form.is_valid()
        assert "phone" in form.errors
