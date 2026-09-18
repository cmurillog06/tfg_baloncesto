from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from apps.teams.models import Season
from apps.matches.generator import generate_season_schedule


class Command(BaseCommand):
    help = "Genera de forma aleatoria y automática el calendario oficial, sedes y designaciones de árbitros y mesas para una temporada."

    def add_arguments(self, parser):
        parser.add_argument(
            "--season-id",
            type=int,
            help="ID de la temporada para la que se generará el calendario.",
        )
        parser.add_argument(
            "--single-round",
            action="store_true",
            help="Generar únicamente una vuelta (solo ida), en lugar de ida y vuelta.",
        )
        parser.add_argument(
            "--start-date",
            type=str,
            help="Fecha de inicio en formato YYYY-MM-DD (por defecto el próximo sábado).",
        )
        parser.add_argument(
            "--interval",
            type=int,
            default=7,
            help="Días entre jornadas consecutivas (por defecto 7).",
        )
        parser.add_argument(
            "--keep-existing",
            action="store_true",
            help="No eliminar partidos programados previamente en la temporada.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Ejecuta una simulación sin guardar los cambios en la base de datos.",
        )

    def handle(self, *args, **options):
        season_id = options.get("season_id")
        if season_id:
            season = Season.objects.filter(id=season_id).first()
            if not season:
                raise CommandError(f"No existe ninguna temporada con ID {season_id}.")
        else:
            season = Season.objects.filter(is_current=True).first() or Season.objects.first()
            if not season:
                raise CommandError("No hay ninguna temporada registrada en la base de datos.")

        start_date = None
        if options.get("start_date"):
            try:
                start_date = datetime.strptime(options["start_date"], "%Y-%m-%d").date()
            except ValueError:
                raise CommandError("Formato de fecha no válido. Utilice YYYY-MM-DD.")

        double_round = not options.get("single_round", False)
        clear_existing = not options.get("keep_existing", False)
        dry_run = options.get("dry_run", False)
        interval = options.get("interval", 7)

        self.stdout.write(self.style.MIGRATE_HEADING(f"🏀 GENERANDO CALENDARIO ALEATORIO: {season.name} ({season.league.name})"))
        self.stdout.write("=" * 75)

        try:
            result = generate_season_schedule(
                season=season,
                double_round=double_round,
                start_date=start_date,
                round_interval_days=interval,
                clear_existing=clear_existing,
                dry_run=dry_run,
            )
        except Exception as e:
            raise CommandError(f"Error al confeccionar el calendario: {str(e)}")

        self.stdout.write(self.style.SUCCESS(f"✓ Formato: {'Ida y Vuelta (Doble Vuelta)' if double_round else 'Solo Ida'}"))
        self.stdout.write(self.style.SUCCESS(f"✓ Total de Equipos: {result['total_teams']}"))
        self.stdout.write(self.style.SUCCESS(f"✓ Total de Jornadas: {result['total_rounds']}"))
        self.stdout.write(self.style.SUCCESS(f"✓ Total de Partidos: {result['total_matches']}"))
        self.stdout.write(self.style.SUCCESS(f"✓ Fecha de Inicio: {result['start_date']}"))

        if dry_run:
            self.stdout.write(self.style.WARNING("\n⚠️ Modo simulación (Dry Run): Ningún partido ha sido persistido en la BD."))
        else:
            self.stdout.write(self.style.SUCCESS("\n🎉 ¡Calendario y designaciones guardados correctamente en la base de datos!"))
