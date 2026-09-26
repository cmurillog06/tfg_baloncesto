from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.teams.models import League, Season, Team, Player
from apps.matches.models import Match, MatchEvent
from apps.analytics.services import recalculate_season_standings


class Command(BaseCommand):
    help = "Armoniza los partidos y recalcula la clasificación de la Liga Endesa ACB"

    def handle(self, *args, **kwargs):
        acb_league, _ = League.objects.get_or_create(
            slug="liga-endesa-acb",
            defaults={"name": "Liga Endesa ACB", "description": "Primera división de baloncesto profesional de España.", "is_active": True}
        )
        season_acb, _ = Season.objects.get_or_create(
            league=acb_league,
            name="Temporada 2026/2027",
            defaults={"start_date": "2026-09-26", "end_date": "2027-05-30", "is_current": True}
        )
        if not season_acb.is_current:
            season_acb.is_current = True
            season_acb.save()

        rmb, _ = Team.objects.get_or_create(slug="real-madrid-baloncesto", defaults={"name": "Real Madrid Baloncesto", "acronym": "RMB", "arena_name": "WiZink Center", "city": "Madrid"})
        fcb, _ = Team.objects.get_or_create(slug="fc-barcelona-basket", defaults={"name": "FC Barcelona", "acronym": "BAR", "arena_name": "Palau Blaugrana", "city": "Barcelona"})
        uni, _ = Team.objects.get_or_create(slug="unicaja-malaga", defaults={"name": "Unicaja Málaga", "acronym": "UNI", "arena_name": "Palacio de Deportes Martín Carpena", "city": "Málaga"})
        val, _ = Team.objects.get_or_create(slug="valencia-basket", defaults={"name": "Valencia Basket", "acronym": "VAL", "arena_name": "Pabellón Fuente de San Luis", "city": "Valencia"})

        from django.contrib.auth import get_user_model
        User = get_user_model()
        mesa = User.objects.filter(username="oficial_mesa").first()
        crono = User.objects.filter(username="cronometrador").first()
        ref1 = User.objects.filter(username="arbitro_principal").first()
        ref2 = User.objects.filter(username="arbitro_fiba").first()

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
                "referee": ref1,
                "second_referee": ref2,
                "table_official": mesa,
                "timekeeper": crono,
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
                "referee": ref1,
                "second_referee": ref2,
                "table_official": mesa,
                "timekeeper": crono,
            }
        )

        # Jornada 2:
        # Partido 3: Real Madrid vs Unicaja (EN DIRECTO)
        m3, _ = Match.objects.update_or_create(
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
                "referee": ref1,
                "second_referee": ref2,
                "table_official": mesa,
                "timekeeper": crono,
            }
        )

        # Sincronizar la cronología completa de jugadas (Jugada a Jugada) con las estadísticas del partido
        from apps.teams.management.commands.seed_full_rosters import generate_match_events_from_stats
        generate_match_events_from_stats(m3)

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
                "referee": ref1,
                "second_referee": ref2,
                "table_official": mesa,
                "timekeeper": crono,
            }
        )

        # Recalcular clasificación oficial de la Liga Endesa
        recalculate_season_standings(season_acb)

        self.stdout.write(self.style.SUCCESS("🎉 ¡Partidos de Liga Endesa y clasificación sincronizados al 100%!"))
