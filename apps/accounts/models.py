from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class CustomUser(AbstractUser):
    """
    Modelo de usuario personalizado con soporte para roles del sistema.
    """

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Administrador"
        TABLE_OFFICIAL = "TABLE_OFFICIAL", "Mesa Arbitral"
        COACH = "COACH", "Entrenador"
        FAN = "FAN", "Aficionado / Espectador"

    email = models.EmailField(unique=True, verbose_name="Correo Electrónico")
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.FAN,
        verbose_name="Rol de Usuario",
    )

    REQUIRED_FIELDS = ["email", "first_name", "last_name"]

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        ordering = ["-date_joined"]

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    @property
    def is_table_official(self):
        return self.role in [self.Role.ADMIN, self.Role.TABLE_OFFICIAL]

    @property
    def is_coach(self):
        return self.role in [self.Role.ADMIN, self.Role.COACH]

    @property
    def is_fan(self):
        return self.role == self.Role.FAN


class Profile(models.Model):
    """
    Perfil complementario para información adicional del usuario.
    """

    user = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE, related_name="profile"
    )
    phone = models.CharField(
        max_length=20, blank=True, verbose_name="Teléfono"
    )
    avatar = models.ImageField(
        upload_to="avatars/", blank=True, null=True, verbose_name="Avatar"
    )
    bio = models.TextField(blank=True, verbose_name="Biografía")

    class Meta:
        verbose_name = "Perfil"
        verbose_name_plural = "Perfiles"

    def __str__(self):
        return f"Perfil de {self.user.username}"


@receiver(post_save, sender=CustomUser)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
    else:
        if hasattr(instance, "profile"):
            instance.profile.save()
