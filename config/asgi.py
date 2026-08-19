"""
ASGI config for tfg_baloncesto project.
Enrutador asíncrono para peticiones HTTP y conexiones WebSocket.
"""

import os
from pathlib import Path
import sys

# Asegurar que 'apps' está en PYTHONPATH
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "apps"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

from django.core.asgi import get_asgi_application
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

# Importación diferida de rutas WebSocket
from apps.matches import routing as matches_routing
from apps.chat import routing as chat_routing

websocket_urlpatterns = (
    matches_routing.websocket_urlpatterns + chat_routing.websocket_urlpatterns
)

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        ),
    }
)
