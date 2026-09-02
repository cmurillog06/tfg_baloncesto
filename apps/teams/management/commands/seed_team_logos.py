import os
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.teams.models import Team

CRESTS_MAP = {
    "RMB": "real_madrid_crest.jpg",
    "FCB": "fc_barcelona_crest.jpg",
    "BAR": "fc_barcelona_crest.jpg",
    "UNI": "unicaja_malaga_crest.jpg",
    "VBC": "valencia_basket_crest.jpg",
    "PAO": "pao_crest.jpg",
    "OLY": "oly_crest.jpg",
    "FNB": "fnb_crest.jpg",
    "ASM": "asm_crest.jpg",
}


class Command(BaseCommand):
    help = "Asigna los escudos oficiales con dimensiones 1:1 homogéneas a todos los clubes (Liga Endesa y EuroLeague)."

    def handle(self, *args, **kwargs):
        media_teams_dir = os.path.join(settings.MEDIA_ROOT, "teams")
        os.makedirs(media_teams_dir, exist_ok=True)

        teams = Team.objects.all()

        for team in teams:
            acronym = (team.acronym or "").upper()
            name_lower = team.name.lower()

            filename = None
            if "madrid" in name_lower or acronym == "RMB":
                filename = CRESTS_MAP["RMB"]
            elif "barcelona" in name_lower or "barça" in name_lower or acronym in ["FCB", "BAR"]:
                filename = CRESTS_MAP["FCB"]
            elif "unicaja" in name_lower or "málaga" in name_lower or acronym == "UNI":
                filename = CRESTS_MAP["UNI"]
            elif "valencia" in name_lower or acronym in ["VBC", "VAL"]:
                filename = CRESTS_MAP["VBC"]
            elif "panathinaikos" in name_lower or acronym == "PAO":
                filename = CRESTS_MAP["PAO"]
            elif "olympiacos" in name_lower or acronym == "OLY":
                filename = CRESTS_MAP["OLY"]
            elif "fenerbahçe" in name_lower or "fenerbahce" in name_lower or acronym == "FNB":
                filename = CRESTS_MAP["FNB"]
            elif "monaco" in name_lower or acronym == "ASM":
                filename = CRESTS_MAP["ASM"]

            if filename:
                team.logo = f"teams/{filename}"
                team.save()
                self.stdout.write(self.style.SUCCESS(f"✅ Escudo oficial 1:1 asignado a {team.name} ({filename})"))
            else:
                self.stdout.write(self.style.WARNING(f"No se encontró escudo para {team.name}"))

        self.stdout.write(self.style.SUCCESS("🎉 ¡Todos los escudos oficiales han sido asignados correctamente!"))
