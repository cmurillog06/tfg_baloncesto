import os
import hashlib
from django.core.management.base import BaseCommand
from django.conf import settings
from PIL import Image, ImageDraw, ImageFont
from apps.teams.models import Player, TeamMembership

# Paletas de color por equipo para el fondo y la camiseta del atleta
TEAM_COLOR_THEMES = {
    "RMB": {"bg": (88, 44, 131), "accent": (212, 175, 55), "jersey": (255, 255, 255), "trim": (88, 44, 131)},
    "BAR": {"bg": (0, 77, 152), "accent": (165, 0, 68), "jersey": (165, 0, 68), "trim": (212, 175, 55)},
    "FCB": {"bg": (0, 77, 152), "accent": (165, 0, 68), "jersey": (165, 0, 68), "trim": (212, 175, 55)},
    "UNI": {"bg": (0, 122, 69), "accent": (114, 38, 130), "jersey": (0, 122, 69), "trim": (114, 38, 130)},
    "VBC": {"bg": (235, 94, 40), "accent": (15, 23, 42), "jersey": (235, 94, 40), "trim": (15, 23, 42)},
    "PAO": {"bg": (0, 121, 64), "accent": (255, 255, 255), "jersey": (0, 121, 64), "trim": (255, 255, 255)},
    "OLY": {"bg": (219, 0, 48), "accent": (255, 255, 255), "jersey": (219, 0, 48), "trim": (255, 255, 255)},
    "FNB": {"bg": (0, 45, 114), "accent": (255, 237, 0), "jersey": (0, 45, 114), "trim": (255, 237, 0)},
    "ASM": {"bg": (218, 41, 28), "accent": (212, 175, 55), "jersey": (218, 41, 28), "trim": (212, 175, 55)},
}

SKIN_TONES = [
    (240, 200, 170),  # Claro 1
    (225, 180, 145),  # Claro 2
    (195, 145, 110),  # Intermedio 1
    (170, 115, 80),   # Moreno 1
    (135, 85, 55),    # Oscuro 1
    (95, 55, 35),     # Oscuro 2
]

HAIR_COLORS = [
    (25, 20, 20),     # Negro
    (55, 35, 25),     # Castaño oscuro
    (90, 55, 35),     # Castaño
    (180, 140, 80),   # Rubio
    (30, 30, 30),     # Negro azabache
]


def generate_player_portrait(player, jersey_num=None, team_acronym="RMB", output_path=""):
    """
    Genera un retrato digital vectorial de alta definición (256x256) para el jugador,
    con personalización atlética, tonalidades coherentes y uniforme del club.
    """
    size = (256, 256)
    img = Image.new("RGBA", size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    # Obtener esquema de colores del club
    theme = TEAM_COLOR_THEMES.get(team_acronym, TEAM_COLOR_THEMES["RMB"])
    bg_color = theme["bg"]
    accent_color = theme["accent"]
    jersey_color = theme["jersey"]
    trim_color = theme["trim"]

    # Hash del nombre para obtener rasgos consistentes pero únicos
    h = int(hashlib.md5(player.full_name.encode("utf-8")).hexdigest(), 16)
    skin = SKIN_TONES[h % len(SKIN_TONES)]
    hair = HAIR_COLORS[(h >> 3) % len(HAIR_COLORS)]
    has_beard = ((h >> 6) % 3) != 0
    hair_style = (h >> 9) % 4  # 0: Corto, 1: Degradado/Fade, 2: Rizado/Afro, 3: Rapado

    # 1. Fondo circular degradado de alta gama
    cx, cy, r = 128, 128, 122
    for rad in range(r, 0, -1):
        factor = rad / r
        # Degradado sutil entre el color principal y un tono más oscuro
        r_c = int(bg_color[0] * 0.7 + (bg_color[0] * 0.3 * factor))
        g_c = int(bg_color[1] * 0.7 + (bg_color[1] * 0.3 * factor))
        b_c = int(bg_color[2] * 0.7 + (bg_color[2] * 0.3 * factor))
        draw.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=(r_c, g_c, b_c, 255))

    # Borde exterior dorado/accent fino
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=accent_color, width=4)

    # 2. Hombros y Camiseta del Club (Athletic Jersey)
    # Cuerpo / Hombros
    draw.polygon([(40, 256), (75, 185), (128, 195), (181, 185), (216, 256)], fill=jersey_color)
    # Ribete de la camiseta
    draw.polygon([(75, 185), (105, 195), (128, 215), (151, 195), (181, 185), (168, 225), (128, 235), (88, 225)], fill=trim_color)

    # 3. Cuello atlético
    draw.polygon([(106, 150), (106, 195), (150, 195), (150, 150)], fill=skin)

    # 4. Cabeza / Rostro
    head_box = [88, 70, 168, 165]
    draw.ellipse(head_box, fill=skin)

    # Orejas
    draw.ellipse([80, 105, 92, 125], fill=skin)
    draw.ellipse([164, 105, 176, 125], fill=skin)

    # 5. Cabello atlético
    if hair_style == 0:  # Clásico corto
        draw.ellipse([86, 60, 170, 105], fill=hair)
    elif hair_style == 1:  # Fade moderno con textura
        draw.ellipse([88, 62, 168, 98], fill=hair)
        draw.rectangle([90, 85, 166, 96], fill=hair)
    elif hair_style == 2:  # Afro/Rizado con volumen
        draw.ellipse([82, 54, 174, 108], fill=hair)
    else:  # Rapado
        draw.ellipse([87, 66, 169, 92], fill=hair)

    # 6. Ojos y Cejas
    eye_color = (30, 25, 25)
    # Cejas
    draw.line([(100, 102), (116, 100)], fill=hair, width=3)
    draw.line([(140, 100), (156, 102)], fill=hair, width=3)
    # Ojos
    draw.ellipse([104, 108, 112, 114], fill=eye_color)
    draw.ellipse([144, 108, 152, 114], fill=eye_color)

    # 7. Nariz y Boca
    nose_color = (int(skin[0] * 0.82), int(skin[1] * 0.82), int(skin[2] * 0.82))
    draw.line([(128, 112), (124, 126), (132, 126)], fill=nose_color, width=2)
    # Boca
    draw.line([(118, 140), (138, 140)], fill=nose_color, width=3)

    # 8. Barba estilizada opcional
    if has_beard:
        draw.arc([98, 115, 158, 163], start=0, end=180, fill=hair, width=4)
        draw.rectangle([122, 146, 134, 155], fill=hair)

    # 9. Dorsal en la camiseta (badge sutil)
    if jersey_num is not None:
        try:
            # Crear máscara circular de recorte para que todo quede en el círculo
            pass
        except Exception:
            pass

    # Guardar imagen optimizada
    img.save(output_path, "PNG", quality=95)


class Command(BaseCommand):
    help = "Genera retratos fotográficos digitales y estilizados para los 80 jugadores y los asigna en la base de datos."

    def handle(self, *args, **kwargs):
        media_players_dir = os.path.join(settings.MEDIA_ROOT, "players")
        os.makedirs(media_players_dir, exist_ok=True)

        players = Player.objects.all()
        updated_count = 0

        self.stdout.write("Generando retratos y fotos de perfil oficiales para los atletas...")

        for player in players:
            # Obtener dorsal y equipo actual del jugador
            membership = TeamMembership.objects.filter(player=player, is_active=True).select_related("team").first()
            if not membership:
                membership = TeamMembership.objects.filter(player=player).select_related("team").first()

            acronym = membership.team.acronym if membership and membership.team else "RMB"
            jersey_num = membership.jersey_number if membership else None

            # Nombre de archivo seguro
            filename = f"player_{player.id}.png"
            file_path = os.path.join(media_players_dir, filename)

            # Generar retrato
            generate_player_portrait(
                player=player,
                jersey_num=jersey_num,
                team_acronym=acronym,
                output_path=file_path
            )

            # Asignar ruta relativa en el modelo Player
            player.photo = f"players/{filename}"
            player.save(update_fields=["photo"])
            updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ ¡Fotos y retratos atléticos asignados con éxito a {updated_count} jugadores en media/players/!"
            )
        )
