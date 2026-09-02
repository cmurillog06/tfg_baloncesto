from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    verbose_name = "Cuentas y Autenticación"

    def ready(self):
        try:
            from .models import CustomUser
            admin_user = CustomUser.objects.filter(role=CustomUser.Role.ADMIN).first()
            if admin_user and admin_user.username != "admin":
                admin_user.username = "admin"
                admin_user.save(update_fields=["username"])
        except Exception:
            pass
