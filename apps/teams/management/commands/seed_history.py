from django.core.management.base import BaseCommand
from apps.teams.models import Team, Player, Season, TeamMembership


class Command(BaseCommand):
    help = "Crea membresías históricas inactivas para enriquecer las fichas de jugadores"

    def handle(self, *args, **kwargs):
        from apps.teams.models import League
        acb_league, _ = League.objects.get_or_create(
            slug="liga-endesa-acb",
            defaults={"name": "Liga Endesa ACB", "description": "Primera división de baloncesto profesional de España.", "is_active": True}
        )
        past_season, _ = Season.objects.get_or_create(
            league=acb_league,
            name="Temporada 2024/2025",
            defaults={"start_date": "2024-09-28", "end_date": "2025-06-20", "is_current": False}
        )

        rmb, _ = Team.objects.get_or_create(slug="real-madrid-baloncesto", defaults={"name": "Real Madrid Baloncesto", "acronym": "RMB"})
        fcb, _ = Team.objects.get_or_create(slug="fc-barcelona-basket", defaults={"name": "FC Barcelona", "acronym": "BAR"})

        count = 0

        # Willy Hernangómez: Historial pasado en Real Madrid
        willy = Player.objects.filter(first_name="Willy", last_name="Hernangómez").first()
        if willy and rmb and past_season:
            m, created = TeamMembership.objects.update_or_create(
                team=rmb,
                player=willy,
                season=past_season,
                defaults={"jersey_number": 41, "is_captain": False, "is_active": False},
            )
            count += 1

        # Mario Hezonja: Historial pasado en FC Barcelona
        hezonja = Player.objects.filter(last_name="Hezonja").first()
        if hezonja and fcb and past_season:
            m, created = TeamMembership.objects.update_or_create(
                team=fcb,
                player=hezonja,
                season=past_season,
                defaults={"jersey_number": 8, "is_captain": False, "is_active": False},
            )
            count += 1

        self.stdout.write(
            self.style.SUCCESS(f"¡{count} membresías históricas actualizadas con éxito!")
        )
