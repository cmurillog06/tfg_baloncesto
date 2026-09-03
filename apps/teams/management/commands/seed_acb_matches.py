from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.teams.models import League, Season, Team
from apps.matches.models import Match
from apps.analytics.services import recalculate_season_standings


class Command(BaseCommand):
    help = "Armoniza los partidos y recalcula la clasificación de la Liga Endesa ACB"

    def handle(self, *args, **kwargs):
        season_acb = Season.objects.filter(league__slug="liga-endesa-acb").first()
        if not season_acb:
            self.stdout.write(self.style.ERROR("No se encontró la temporada de Liga Endesa."))
            return

        rmb = Team.objects.filter(acronym="RMB").first()
        fcb = Team.objects.filter(acronym__in=["BAR", "FCB"]).first()
        uni = Team.objects.filter(acronym="UNI").first()
        val = Team.objects.filter(acronym__in=["VAL", "VBC"]).first()

        now = timezone.now()

        # Jornada 1: Ambos finalizados
        # Partido 1: Real Madrid 86 - 81 FC Barcelona (FINALIZADO)
        Match.objects.update_or_create(
            season=season_acb,
            round_number=1,
            home_team=rmb,
            away_team=fcb,
            defaults={
                "status": Match.Status.FINISHED,
                "current_period": Match.Period.FINISHED,
                "game_clock": "00:00",
                "home_score": 86,
                "away_score": 81,
                "location": "WiZink Center, Madrid",
                "scheduled_at": now - timedelta(days=7),
            }
        )

        # Partido 2: Unicaja 79 - 74 Valencia Basket (FINALIZADO)
        Match.objects.update_or_create(
            season=season_acb,
            round_number=1,
            home_team=uni,
            away_team=val,
            defaults={
                "status": Match.Status.FINISHED,
                "current_period": Match.Period.FINISHED,
                "game_clock": "00:00",
                "home_score": 79,
                "away_score": 74,
                "location": "Martín Carpena, Málaga",
                "scheduled_at": now - timedelta(days=7),
            }
        )

        # Jornada 2:
        # Partido 3: Real Madrid vs Unicaja (EN DIRECTO)
        Match.objects.update_or_create(
            season=season_acb,
            round_number=2,
            home_team=rmb,
            away_team=uni,
            defaults={
                "status": Match.Status.LIVE,
                "current_period": Match.Period.Q4,
                "game_clock": "09:50",
                "home_score": 66,
                "away_score": 59,
                "location": "WiZink Center, Madrid",
                "scheduled_at": now - timedelta(hours=1),
            }
        )

        # Partido 4: FC Barcelona vs Valencia Basket (PROGRAMADO)
        Match.objects.update_or_create(
            season=season_acb,
            round_number=2,
            home_team=fcb,
            away_team=val,
            defaults={
                "status": Match.Status.SCHEDULED,
                "current_period": Match.Period.NOT_STARTED,
                "game_clock": "10:00",
                "home_score": 0,
                "away_score": 0,
                "scheduled_at": now.replace(hour=21, minute=0, second=0, microsecond=0),
                "location": "Palau Blaugrana, Barcelona",
            }
        )

        # Recalcular clasificación oficial de la Liga Endesa
        recalculate_season_standings(season_acb)

        self.stdout.write(self.style.SUCCESS("🎉 ¡Partidos de Liga Endesa y clasificación sincronizados al 100%!"))
