"""
URL configuration for tfg_baloncesto project.
"""

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views import static as django_static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls", namespace="core")),
    path("accounts/", include("apps.accounts.urls", namespace="accounts")),
    path("teams/", include("apps.teams.urls", namespace="teams")),
    path("matches/", include("apps.matches.urls", namespace="matches")),
    path("chat/", include("apps.chat.urls", namespace="chat")),
    path("analytics/", include("apps.analytics.urls", namespace="analytics")),
]

# Archivos multimedia
# Se sirven tanto en desarrollo como en producción.
urlpatterns += [
    re_path(
        r"^media/(?P<path>.*)$",
        django_static.serve,
        {"document_root": settings.MEDIA_ROOT},
    )
]

# En desarrollo Django sirve también los estáticos.
# En producción los gestiona WhiteNoise.
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)