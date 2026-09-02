import os
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.teams.models import League

LEAGUE_LOGOS = {
    "liga-endesa-acb": "acb_league_logo.jpg",
    "euroleague-basketball": "euroleague_logo.jpg",
}


class Command(BaseCommand):
    help = "Asigna los logotipos y emblemas oficiales 1:1 a las Ligas registradas."

    def handle(self, *args, **kwargs):
        media_leagues_dir = os.path.join(settings.MEDIA_ROOT, "leagues")
        os.makedirs(media_leagues_dir, exist_ok=True)

        for slug, filename in LEAGUE_LOGOS.items():
            try:
                league = League.objects.get(slug=slug)
                league.logo = f"leagues/{filename}"
                league.save()
                self.stdout.write(self.style.SUCCESS(f"✅ Emblema oficial asignado a {league.name} ({filename})"))
            except League.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"No se encontró la liga con slug {slug}"))

        self.stdout.write(self.style.SUCCESS("🎉 ¡Todos los emblemas de liga han sido asignados correctamente!"))
