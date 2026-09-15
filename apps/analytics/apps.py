from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.analytics"
    verbose_name = "Estadísticas Avanzadas y Clasificaciones"

    def ready(self):
        try:
            import apps.analytics.signals  # noqa
        except Exception:
            pass

