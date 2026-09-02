from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.matches.models import Match, MatchEvent, DigitalScoreSheet
from apps.teams.models import Team, Season


class Command(BaseCommand):
    help = "Crea o actualiza partidos en estado LIVE (En Juego) y programados para pruebas."

    def handle(self, *args, **options):
        season = Season.objects.filter(is_current=True).first()
        if not season:
            season = Season.objects.first()

        if not season:
            self.stdout.write(self.style.ERROR("No hay ninguna temporada registrada."))
            return

        madrid = Team.objects.filter(acronym="RMB").first()
        unicaja = Team.objects.filter(acronym="UNI").first()
        barca = Team.objects.filter(acronym__in=["BAR", "FCB"]).first()
        valencia = Team.objects.filter(acronym__in=["VAL", "VBC"]).first()

        if not (madrid and unicaja):
            self.stdout.write(self.style.ERROR("No se encontraron los equipos de prueba."))
            return

        # 1. Partido en Directo Principal (Real Madrid vs Unicaja)
        match_live, _ = Match.objects.get_or_create(
            id=3,
            defaults={
                "season": season,
                "round_number": 2,
                "home_team": madrid,
                "away_team": unicaja,
                "scheduled_at": timezone.now(),
                "location": "WiZink Center, Madrid",
                "status": Match.Status.LIVE,
                "current_period": Match.Period.Q3,
                "game_clock": "06:45",
                "home_score": 64,
                "away_score": 59,
            },
        )
        match_live.status = Match.Status.LIVE
        match_live.current_period = Match.Period.Q3
        match_live.game_clock = "06:45"
        match_live.home_score = 64
        match_live.away_score = 59
        match_live.save()

        # Si tenía acta cerrada, la reabrimos para pruebas
        if hasattr(match_live, "scoresheet"):
            match_live.scoresheet.is_closed = False
            match_live.scoresheet.save()

        # 2. Segundo Partido en Directo (FC Barcelona vs Valencia Basket) si existen
        if barca and valencia:
            match_live_2, _ = Match.objects.get_or_create(
                home_team=barca,
                away_team=valencia,
                season=season,
                defaults={
                    "round_number": 2,
                    "scheduled_at": timezone.now(),
                    "location": "Palau Blaugrana, Barcelona",
                    "status": Match.Status.LIVE,
                    "current_period": Match.Period.Q2,
                    "game_clock": "03:12",
                    "home_score": 38,
                    "away_score": 35,
                },
            )
            match_live_2.status = Match.Status.LIVE
            match_live_2.current_period = Match.Period.Q2
            match_live_2.game_clock = "03:12"
            match_live_2.home_score = 38
            match_live_2.away_score = 35
            match_live_2.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"Partidos en vivo configurados con exito. Accede a http://127.0.0.1:8000/matches/{match_live.id}/live/"
            )
        )
