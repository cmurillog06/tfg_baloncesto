from django.core.management.base import BaseCommand
from apps.teams.models import Team, Player, Season, TeamMembership


class Command(BaseCommand):
    help = "Crea membresías históricas inactivas para enriquecer las fichas de jugadores"

    def handle(self, *args, **kwargs):
        season_acb = (
            Season.objects.filter(league__name__icontains="Endesa").first()
            or Season.objects.first()
        )
        rmb = Team.objects.filter(acronym="RMB").first()
        fcb = Team.objects.filter(acronym__in=["BAR", "FCB"]).first()

        count = 0

        # Willy Hernangómez: Historial pasado en Real Madrid
        willy = Player.objects.filter(first_name="Willy", last_name="Hernangómez").first()
        if willy and rmb and season_acb:
            m, created = TeamMembership.objects.update_or_create(
                team=rmb,
                player=willy,
                season=season_acb,
                defaults={"jersey_number": 41, "is_captain": False, "is_active": False},
            )
            count += 1

        # Mario Hezonja: Historial pasado en FC Barcelona
        hezonja = Player.objects.filter(last_name="Hezonja").first()
        if hezonja and fcb and season_acb:
            m, created = TeamMembership.objects.update_or_create(
                team=fcb,
                player=hezonja,
                season=season_acb,
                defaults={"jersey_number": 8, "is_captain": False, "is_active": False},
            )
            count += 1

        self.stdout.write(
            self.style.SUCCESS(f"¡{count} membresías históricas actualizadas con éxito!")
        )
