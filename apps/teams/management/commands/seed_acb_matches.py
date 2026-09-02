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
        m1 = Match.objects.filter(pk=1).first()
        if m1:
            m1.home_team = rmb
            m1.away_team = fcb
            m1.season = season_acb
            m1.round_number = 1
            m1.status = Match.Status.FINISHED
            m1.current_period = Match.Period.FINISHED
            m1.game_clock = "00:00"
            m1.home_score = 86
            m1.away_score = 81
            m1.save()

        # Partido 2: Unicaja 79 - 74 Valencia Basket (FINALIZADO)
        m2 = Match.objects.filter(pk=2).first()
        if m2:
            m2.home_team = uni
            m2.away_team = val
            m2.season = season_acb
            m2.round_number = 1
            m2.status = Match.Status.FINISHED
            m2.current_period = Match.Period.FINISHED
            m2.game_clock = "00:00"
            m2.home_score = 79
            m2.away_score = 74
            m2.save()

        # Jornada 2:
        # Partido 3: Real Madrid vs Unicaja (EN DIRECTO)
        m3 = Match.objects.filter(pk=3).first()
        if m3:
            m3.home_team = rmb
            m3.away_team = uni
            m3.season = season_acb
            m3.round_number = 2
            m3.status = Match.Status.LIVE
            m3.current_period = Match.Period.Q4
            m3.game_clock = "09:50"
            m3.home_score = 66
            m3.away_score = 59
            m3.save()

        # Partido 4: FC Barcelona vs Valencia Basket (PROGRAMADO para hoy a las 21:00h en el Palau Blaugrana)
        m4 = Match.objects.filter(pk=4).first()
        if m4:
            m4.home_team = fcb
            m4.away_team = val
            m4.season = season_acb
            m4.round_number = 2
            m4.status = Match.Status.SCHEDULED
            m4.current_period = Match.Period.NOT_STARTED
            m4.game_clock = "10:00"
            m4.home_score = 0
            m4.away_score = 0
            m4.scheduled_at = now.replace(hour=21, minute=0, second=0, microsecond=0)
            m4.location = "Palau Blaugrana, Barcelona"
            m4.save()

        # Recalcular clasificación oficial de la Liga Endesa
        recalculate_season_standings(season_acb)

        self.stdout.write(self.style.SUCCESS("🎉 ¡Partidos de Liga Endesa y clasificación sincronizados al 100%!"))
