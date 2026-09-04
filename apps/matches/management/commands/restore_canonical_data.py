from django.core.management.base import BaseCommand
from apps.matches.services import restore_canonical_matches
from apps.matches.consumers import SERVER_MATCH_CLOCKS


class Command(BaseCommand):
    help = "Restaura todos los partidos, estadísticas, clasificaciones y actas al estado canónico oficial para demostración."

    def handle(self, *args, **options):
        # Limpiar relojes en memoria de websocket
        SERVER_MATCH_CLOCKS.clear()
        
        restore_canonical_matches()
        self.stdout.write(
            self.style.SUCCESS("Base de datos de partidos restaurada al estado canónico oficial con éxito.")
        )
