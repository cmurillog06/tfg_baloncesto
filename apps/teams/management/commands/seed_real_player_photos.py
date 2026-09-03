import os
import time
import urllib.request
import urllib.parse
import json
from io import BytesIO
from PIL import Image
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.teams.models import Player, TeamMembership


# Mapeo preciso de títulos de Wikipedia para los 80 jugadores
WIKI_PLAYER_TITLES = {
    # AS Monaco
    ("Mike", "James"): "Mike_James_(basketball,_born_1990)",
    ("Elie", "Okobo"): "Élie_Okobo",
    ("Jordan", "Loyd"): "Jordan_Loyd",
    ("Alpha", "Diallo"): "Alpha_Diallo_(basketball,_born_1997)",
    ("Jaron", "Blossomgame"): "Jaron_Blossomgame",
    ("Donatas", "Motiejunas"): "Donatas_Motiejūnas",
    ("Nick", "Calathes"): "Nick_Calathes",
    ("Mam", "Jaiteh"): "Mouhammadou_Jaiteh",
    ("John", "Brown III"): "John_Brown_III",
    ("Vitto", "Brown"): "Vitto_Brown",

    # Real Madrid
    ("Facundo", "Campazzo"): "Facundo_Campazzo",
    ("Sergio", "Llull"): "Sergio_Llull",
    ("Walter", "Tavares"): "Edy_Tavares",
    ("Mario", "Hezonja"): "Mario_Hezonja",
    ("Dzanan", "Musa"): "Džanan_Musa",
    ("Gabriel", "Deck"): "Gabriel_Deck",
    ("Serge", "Ibaka"): "Serge_Ibaka",
    ("Usman", "Garuba"): "Usman_Garuba",
    ("Alberto", "Abalde"): "Alberto_Abalde",
    ("Andrés", "Feliz"): "Andrés_Feliz",

    # FC Barcelona
    ("Kevin", "Punter"): "Kevin_Punter",
    ("Nicolas", "Laprovittola"): "Nicolás_Laprovíttola",
    ("Tomas", "Satoransky"): "Tomáš_Satoranský",
    ("Alex", "Abrines"): "Álex_Abrines",
    ("Willy", "Hernangómez"): "Willy_Hernangómez",
    ("Jan", "Vesely"): "Jan_Veselý",
    ("Jabari", "Parker"): "Jabari_Parker",
    ("Dario", "Brizuela"): "Darío_Brizuela",
    ("Justin", "Anderson"): "Justin_Anderson_(basketball)",
    ("Chimezie", "Metu"): "Chimezie_Metu",

    # Panathinaikos
    ("Kostas", "Sloukas"): "Kostas_Sloukas",
    ("Kendrick", "Nunn"): "Kendrick_Nunn",
    ("Cedi", "Osman"): "Cedi_Osman",
    ("Juancho", "Hernangómez"): "Juancho_Hernangómez",
    ("Mathias", "Lessort"): "Mathias_Lessort",
    ("Jerian", "Grant"): "Jerian_Grant",
    ("Dinos", "Mitoglou"): "Dinos_Mitoglou",
    ("Marius", "Grigonis"): "Marius_Grigonis",
    ("Omer", "Yurtseven"): "Ömer_Yurtseven",
    ("Panagiotis", "Kalaitzakis"): "Panagiotis_Kalaitzakis",

    # Olympiacos
    ("Sasha", "Vezenkov"): "Sasha_Vezenkov",
    ("Evan", "Fournier"): "Evan_Fournier",
    ("Thomas", "Walkup"): "Thomas_Walkup",
    ("Kostas", "Papanikolaou"): "Kostas_Papanikolaou",
    ("Alec", "Peters"): "Alec_Peters",
    ("Nikola", "Milutinov"): "Nikola_Milutinov",
    ("Nigel", "Williams-Goss"): "Nigel_Williams-Goss",
    ("Tyler", "Dorsey"): "Tyler_Dorsey",
    ("Shaquielle", "McKissic"): "Shaquielle_McKissic",
    ("Moustapha", "Fall"): "Moustapha_Fall",

    # Fenerbahce
    ("Wade", "Baldwin IV"): "Wade_Baldwin_IV",
    ("Nigel", "Hayes-Davis"): "Nigel_Hayes-Davis",
    ("Marko", "Guduric"): "Marko_Gudurić",
    ("Nicolo", "Melli"): "Nicolò_Melli",
    ("Bonzie", "Colson"): "Bonzie_Colson",
    ("Boban", "Marjanovic"): "Boban_Marjanović",
    ("Devon", "Hall"): "Devon_Hall",
    ("Sertac", "Sanli"): "Sertaç_Şanlı",
    ("Tarik", "Biberovic"): "Tarik_Biberović",
    ("Arturs", "Zagars"): "Artūrs_Žagars",

    # Unicaja
    ("Alberto", "Díaz"): "Alberto_Díaz_(baloncestista)",
    ("Kendrick", "Perry"): "Kendrick_Perry",
    ("Dylan", "Osetkowski"): "Dylan_Osetkowski",
    ("Tyson", "Carter"): "Tyson_Carter",
    ("Tyler", "Kalinoski"): "Tyler_Kalinoski",
    ("Kameron", "Taylor"): "Kameron_Taylor",
    ("Nihad", "Djedovic"): "Nihad_Đedović",
    ("Melvin", "Ejim"): "Melvin_Ejim",
    ("David", "Kravish"): "David_Kravish",
    ("Yankuba", "Sima"): "Yankuba_Sima",

    # Valencia
    ("Chris", "Jones"): "Chris_Jones_(basketball,_born_1993)",
    ("Stefan", "Jovic"): "Stefan_Jović",
    ("Semi", "Ojeleye"): "Semi_Ojeleye",
    ("Jean", "Montero"): "Jean_Montero",
    ("Jaime", "Pradilla"): "Jaime_Pradilla",
    ("Brancou", "Badio"): "Brancou_Badio",
    ("Matt", "Costello"): "Matt_Costello",
    ("Josep", "Puerto"): "Josep_Puerto",
    ("Nate", "Reuvers"): "Nate_Reuvers",
    ("Ethan", "Happ"): "Ethan_Happ",
}


def fetch_wikipedia_image_url(title):
    """
    Consulta la REST API de Wikipedia con reintentos controlados para obtener la foto oficial.
    """
    encoded_title = urllib.parse.quote(title)
    headers = {"User-Agent": "QuintoCuartoApp/1.0 (https://quintocuarto.es; contact@quintocuarto.es)"}

    # Probar Wikipedia en inglés
    for lang in ["en", "es", "fr", "el"]:
        url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{encoded_title}"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    if "originalimage" in data and "source" in data["originalimage"]:
                        return data["originalimage"]["source"]
                    if "thumbnail" in data and "source" in data["thumbnail"]:
                        return data["thumbnail"]["source"]
        except urllib.error.HTTPError as he:
            if he.code == 429:
                time.sleep(2.0)
            continue
        except Exception:
            continue

    return None


def download_and_format_headshot(image_url, output_path, target_size=(320, 320)):
    """
    Descarga la foto real del atleta y la procesa en un recorte de retrato
    cuadrado de alta definición centrado en el busto y rostro.
    """
    headers = {"User-Agent": "QuintoCuartoApp/1.0 (https://quintocuarto.es; contact@quintocuarto.es)"}
    req = urllib.request.Request(image_url, headers=headers)

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=12) as response:
                img_data = response.read()
            break
        except urllib.error.HTTPError as he:
            if he.code == 429:
                time.sleep(2.0 * (attempt + 1))
            else:
                raise
        except Exception:
            if attempt == 2:
                raise
            time.sleep(1.0)

    img = Image.open(BytesIO(img_data)).convert("RGB")
    width, height = img.size

    # Recorte inteligente de retrato: enfocarse en la mitad superior/centro (rostro/pecho)
    if height > width:
        crop_size = width
        top = int(height * 0.05)
        if top + crop_size > height:
            top = 0
        img_cropped = img.crop((0, top, width, top + crop_size))
    elif width > height:
        crop_size = height
        left = (width - crop_size) // 2
        img_cropped = img.crop((left, 0, left + crop_size, height))
    else:
        img_cropped = img

    img_final = img_cropped.resize(target_size, Image.Resampling.LANCZOS)
    img_final.save(output_path, "JPEG", quality=92, optimize=True)


class Command(BaseCommand):
    help = "Descarga y procesa fotos reales de alta definición para los 80 jugadores desde archivos oficiales de Wikipedia/Wikimedia."

    def handle(self, *args, **kwargs):
        media_players_dir = os.path.join(settings.MEDIA_ROOT, "players")
        os.makedirs(media_players_dir, exist_ok=True)

        players = Player.objects.all().order_by("id")
        success_count = 0
        self.stdout.write("Obteniendo fotografías reales oficiales para todos los jugadores...")

        for player in players:
            filename = f"player_real_{player.id}.jpg"
            file_path = os.path.join(media_players_dir, filename)

            # 1. Si el archivo ya existe localmente en media/players/, asignarlo instantáneamente (100% offline)
            if os.path.exists(file_path):
                player.photo = f"players/{filename}"
                player.save(update_fields=["photo"])
                success_count += 1
                continue

            pair = (player.first_name, player.last_name)
            wiki_title = WIKI_PLAYER_TITLES.get(pair)

            if not wiki_title:
                wiki_title = f"{player.first_name}_{player.last_name}"

            # Pausa suave entre peticiones para respetar la tasa de la API
            time.sleep(0.4)

            img_url = fetch_wikipedia_image_url(wiki_title)

            if img_url:
                try:
                    download_and_format_headshot(img_url, file_path)
                    player.photo = f"players/{filename}"
                    player.save(update_fields=["photo"])
                    success_count += 1
                    self.stdout.write(self.style.SUCCESS(f"📸 Foto real asignada a {player.full_name}"))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"⚠️ Error procesando imagen de {player.full_name}: {e}"))
            else:
                self.stdout.write(self.style.WARNING(f"ℹ️ No se encontró imagen pública para {player.full_name}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"\n🎉 ¡Proceso completado! Se han asignado {success_count} fotografías reales oficiales a los atletas en la base de datos."
            )
        )
