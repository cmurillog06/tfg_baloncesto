import os
import glob
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "Elimina los antiguos retratos procedimentales player_*.png en desuso."

    def handle(self, *args, **options):
        media_players_dir = os.path.join(settings.MEDIA_ROOT, "players")
        png_files = glob.glob(os.path.join(media_players_dir, "player_*.png"))

        count = 0
        for f in png_files:
            if "player_real_" not in os.path.basename(f):
                try:
                    os.remove(f)
                    count += 1
                except Exception:
                    pass

        self.stdout.write(self.style.SUCCESS(f"Eliminados {count} archivos PNG innecesarios."))

