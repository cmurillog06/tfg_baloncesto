"""
Configuración para entorno de DESARROLLO LOCAL.
"""

from .base import *
import dj_database_url

DEBUG = True

# Base de datos local: SQLite por defecto o PostgreSQL si se provee DATABASE_URL
DATABASE_URL = config("DATABASE_URL", default=None)

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(DATABASE_URL, conn_max_age=600)
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# Capa de canales (Channel Layer) para WebSockets en desarrollo
REDIS_URL = config("REDIS_URL", default=None)

if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [REDIS_URL],
            },
        },
    }
else:
    # Capa en memoria sin necesidad de levantar servidor Redis en desarrollo local
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    }
