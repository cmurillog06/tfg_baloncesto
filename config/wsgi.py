"""
WSGI config for tfg_baloncesto project.
"""

import os
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "apps"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
