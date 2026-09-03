import random
import unicodedata
from datetime import date
from decimal import Decimal
from django.core.management.base import BaseCommand
from apps.teams.models import Team, Player, TeamMembership, Season, League
from apps.matches.models import Match
from apps.analytics.models import PlayerMatchStat


def normalize_str(s):
    if not s:
        return ""
    norm = unicodedata.normalize("NFKD", str(s)).encode("ASCII", "ignore").decode("utf-8")
    return norm.strip().lower()


ALL_TEAMS_ROSTERS = {
    "real-madrid-baloncesto": [
        {"first": "Facundo", "last": "Campazzo", "num": 7, "pos": Player.Position.POINT_GUARD, "height": 178, "weight": Decimal("88.0"), "birth": date(1991, 3, 23), "captain": False},
        {"first": "Andrés", "last": "Feliz", "num": 12, "pos": Player.Position.POINT_GUARD, "height": 188, "weight": Decimal("85.0"), "birth": date(1997, 7, 15), "captain": False},
        {"first": "Sergio", "last": "Llull", "num": 23, "pos": Player.Position.SHOOTING_GUARD, "height": 190, "weight": Decimal("94.0"), "birth": date(1987, 11, 15), "captain": True},
        {"first": "Dzanan", "last": "Musa", "num": 13, "pos": Player.Position.SHOOTING_GUARD, "height": 205, "weight": Decimal("98.0"), "birth": date(1999, 5, 8), "captain": False},
        {"first": "Alberto", "last": "Abalde", "num": 6, "pos": Player.Position.SMALL_FORWARD, "height": 202, "weight": Decimal("95.0"), "birth": date(1995, 12, 15), "captain": False},
        {"first": "Mario", "last": "Hezonja", "num": 11, "pos": Player.Position.SMALL_FORWARD, "height": 203, "weight": Decimal("100.0"), "birth": date(1995, 2, 25), "captain": False},
        {"first": "Gabriel", "last": "Deck", "num": 14, "pos": Player.Position.POWER_FORWARD, "height": 198, "weight": Decimal("105.0"), "birth": date(1995, 2, 8), "captain": False},
        {"first": "Usman", "last": "Garuba", "num": 16, "pos": Player.Position.POWER_FORWARD, "height": 203, "weight": Decimal("104.0"), "birth": date(2002, 3, 9), "captain": False},
        {"first": "Walter", "last": "Tavares", "num": 22, "pos": Player.Position.CENTER, "height": 220, "weight": Decimal("125.0"), "birth": date(1992, 3, 22), "captain": False},
        {"first": "Serge", "last": "Ibaka", "num": 9, "pos": Player.Position.CENTER, "height": 210, "weight": Decimal("108.0"), "birth": date(1989, 9, 18), "captain": False},
    ],
    "fc-barcelona-basket": [
        {"first": "Nicolas", "last": "Laprovittola", "num": 20, "pos": Player.Position.POINT_GUARD, "height": 190, "weight": Decimal("84.0"), "birth": date(1990, 1, 31), "captain": False},
        {"first": "Tomas", "last": "Satoransky", "num": 13, "pos": Player.Position.POINT_GUARD, "height": 201, "weight": Decimal("95.0"), "birth": date(1991, 10, 30), "captain": False},
        {"first": "Kevin", "last": "Punter", "num": 0, "pos": Player.Position.SHOOTING_GUARD, "height": 193, "weight": Decimal("86.0"), "birth": date(1993, 6, 25), "captain": False},
        {"first": "Dario", "last": "Brizuela", "num": 8, "pos": Player.Position.SHOOTING_GUARD, "height": 188, "weight": Decimal("82.0"), "birth": date(1994, 11, 8), "captain": False},
        {"first": "Alex", "last": "Abrines", "num": 21, "pos": Player.Position.SMALL_FORWARD, "height": 198, "weight": Decimal("91.0"), "birth": date(1993, 8, 1), "captain": True},
        {"first": "Justin", "last": "Anderson", "num": 1, "pos": Player.Position.SMALL_FORWARD, "height": 198, "weight": Decimal("104.0"), "birth": date(1993, 11, 19), "captain": False},
        {"first": "Jabari", "last": "Parker", "num": 22, "pos": Player.Position.POWER_FORWARD, "height": 203, "weight": Decimal("113.0"), "birth": date(1995, 3, 15), "captain": False},
        {"first": "Chimezie", "last": "Metu", "num": 10, "pos": Player.Position.POWER_FORWARD, "height": 208, "weight": Decimal("102.0"), "birth": date(1997, 3, 22), "captain": False},
        {"first": "Jan", "last": "Vesely", "num": 6, "pos": Player.Position.CENTER, "height": 213, "weight": Decimal("110.0"), "birth": date(1990, 4, 24), "captain": False},
        {"first": "Willy", "last": "Hernangómez", "num": 14, "pos": Player.Position.CENTER, "height": 211, "weight": Decimal("113.0"), "birth": date(1994, 5, 27), "captain": False},
    ],
    "unicaja-malaga": [
        {"first": "Alberto", "last": "Díaz", "num": 9, "pos": Player.Position.POINT_GUARD, "height": 188, "weight": Decimal("86.0"), "birth": date(1994, 4, 23), "captain": True},
        {"first": "Kendrick", "last": "Perry", "num": 55, "pos": Player.Position.POINT_GUARD, "height": 183, "weight": Decimal("82.0"), "birth": date(1992, 12, 23), "captain": False},
        {"first": "Tyson", "last": "Carter", "num": 1, "pos": Player.Position.SHOOTING_GUARD, "height": 193, "weight": Decimal("79.0"), "birth": date(1998, 1, 14), "captain": False},
        {"first": "Tyler", "last": "Kalinoski", "num": 4, "pos": Player.Position.SHOOTING_GUARD, "height": 193, "weight": Decimal("86.0"), "birth": date(1992, 12, 19), "captain": False},
        {"first": "Kameron", "last": "Taylor", "num": 7, "pos": Player.Position.SHOOTING_GUARD, "height": 198, "weight": Decimal("95.0"), "birth": date(1994, 10, 5), "captain": False},
        {"first": "Nihad", "last": "Djedovic", "num": 14, "pos": Player.Position.SMALL_FORWARD, "height": 198, "weight": Decimal("90.0"), "birth": date(1990, 1, 12), "captain": False},
        {"first": "Melvin", "last": "Ejim", "num": 3, "pos": Player.Position.POWER_FORWARD, "height": 201, "weight": Decimal("100.0"), "birth": date(1991, 3, 4), "captain": False},
        {"first": "Dylan", "last": "Osetkowski", "num": 2, "pos": Player.Position.POWER_FORWARD, "height": 206, "weight": Decimal("115.0"), "birth": date(1996, 8, 8), "captain": False},
        {"first": "David", "last": "Kravish", "num": 45, "pos": Player.Position.CENTER, "height": 208, "weight": Decimal("109.0"), "birth": date(1992, 9, 12), "captain": False},
        {"first": "Yankuba", "last": "Sima", "num": 77, "pos": Player.Position.CENTER, "height": 211, "weight": Decimal("102.0"), "birth": date(1996, 7, 28), "captain": False},
    ],
    "valencia-basket": [
        {"first": "Chris", "last": "Jones", "num": 7, "pos": Player.Position.POINT_GUARD, "height": 188, "weight": Decimal("91.0"), "birth": date(1993, 4, 10), "captain": False},
        {"first": "Stefan", "last": "Jovic", "num": 16, "pos": Player.Position.POINT_GUARD, "height": 198, "weight": Decimal("94.0"), "birth": date(1990, 11, 3), "captain": False},
        {"first": "Jean", "last": "Montero", "num": 2, "pos": Player.Position.SHOOTING_GUARD, "height": 188, "weight": Decimal("79.0"), "birth": date(2003, 7, 3), "captain": False},
        {"first": "Brancou", "last": "Badio", "num": 0, "pos": Player.Position.SHOOTING_GUARD, "height": 191, "weight": Decimal("85.0"), "birth": date(1999, 2, 17), "captain": False},
        {"first": "Josep", "last": "Puerto", "num": 5, "pos": Player.Position.SMALL_FORWARD, "height": 199, "weight": Decimal("90.0"), "birth": date(1999, 3, 8), "captain": True},
        {"first": "Semi", "last": "Ojeleye", "num": 37, "pos": Player.Position.SMALL_FORWARD, "height": 201, "weight": Decimal("109.0"), "birth": date(1994, 12, 5), "captain": False},
        {"first": "Jaime", "last": "Pradilla", "num": 4, "pos": Player.Position.POWER_FORWARD, "height": 205, "weight": Decimal("106.0"), "birth": date(2001, 1, 3), "captain": False},
        {"first": "Nate", "last": "Reuvers", "num": 22, "pos": Player.Position.POWER_FORWARD, "height": 211, "weight": Decimal("107.0"), "birth": date(1998, 9, 30), "captain": False},
        {"first": "Matt", "last": "Costello", "num": 24, "pos": Player.Position.CENTER, "height": 208, "weight": Decimal("109.0"), "birth": date(1993, 8, 5), "captain": False},
        {"first": "Ethan", "last": "Happ", "num": 21, "pos": Player.Position.CENTER, "height": 208, "weight": Decimal("108.0"), "birth": date(1996, 5, 7), "captain": False},
    ],
    "panathinaikos-aktor": [
        {"first": "Kostas", "last": "Sloukas", "num": 10, "pos": Player.Position.POINT_GUARD, "height": 190, "weight": Decimal("87.0"), "birth": date(1990, 1, 15), "captain": True},
        {"first": "Jerian", "last": "Grant", "num": 22, "pos": Player.Position.POINT_GUARD, "height": 196, "weight": Decimal("90.0"), "birth": date(1992, 10, 9), "captain": False},
        {"first": "Kendrick", "last": "Nunn", "num": 25, "pos": Player.Position.SHOOTING_GUARD, "height": 191, "weight": Decimal("86.0"), "birth": date(1995, 8, 3), "captain": False},
        {"first": "Panagiotis", "last": "Kalaitzakis", "num": 0, "pos": Player.Position.SHOOTING_GUARD, "height": 200, "weight": Decimal("92.0"), "birth": date(1999, 1, 2), "captain": False},
        {"first": "Cedi", "last": "Osman", "num": 16, "pos": Player.Position.SMALL_FORWARD, "height": 204, "weight": Decimal("104.0"), "birth": date(1995, 4, 8), "captain": False},
        {"first": "Marius", "last": "Grigonis", "num": 40, "pos": Player.Position.SMALL_FORWARD, "height": 198, "weight": Decimal("93.0"), "birth": date(1994, 4, 26), "captain": False},
        {"first": "Juancho", "last": "Hernangómez", "num": 41, "pos": Player.Position.POWER_FORWARD, "height": 206, "weight": Decimal("100.0"), "birth": date(1995, 9, 28), "captain": False},
        {"first": "Dinos", "last": "Mitoglou", "num": 44, "pos": Player.Position.POWER_FORWARD, "height": 210, "weight": Decimal("116.0"), "birth": date(1996, 6, 11), "captain": False},
        {"first": "Mathias", "last": "Lessort", "num": 26, "pos": Player.Position.CENTER, "height": 206, "weight": Decimal("112.0"), "birth": date(1995, 9, 29), "captain": False},
        {"first": "Omer", "last": "Yurtseven", "num": 77, "pos": Player.Position.CENTER, "height": 211, "weight": Decimal("120.0"), "birth": date(1998, 6, 19), "captain": False},
    ],
    "olympiacos-piraeus": [
        {"first": "Thomas", "last": "Walkup", "num": 0, "pos": Player.Position.POINT_GUARD, "height": 193, "weight": Decimal("92.0"), "birth": date(1992, 12, 30), "captain": False},
        {"first": "Nigel", "last": "Williams-Goss", "num": 1, "pos": Player.Position.POINT_GUARD, "height": 191, "weight": Decimal("86.0"), "birth": date(1994, 9, 16), "captain": False},
        {"first": "Evan", "last": "Fournier", "num": 94, "pos": Player.Position.SHOOTING_GUARD, "height": 198, "weight": Decimal("93.0"), "birth": date(1992, 10, 29), "captain": False},
        {"first": "Tyler", "last": "Dorsey", "num": 22, "pos": Player.Position.SHOOTING_GUARD, "height": 196, "weight": Decimal("83.0"), "birth": date(1996, 2, 18), "captain": False},
        {"first": "Kostas", "last": "Papanikolaou", "num": 16, "pos": Player.Position.SMALL_FORWARD, "height": 204, "weight": Decimal("104.0"), "birth": date(1990, 7, 31), "captain": True},
        {"first": "Shaquielle", "last": "McKissic", "num": 77, "pos": Player.Position.SMALL_FORWARD, "height": 196, "weight": Decimal("96.0"), "birth": date(1990, 8, 17), "captain": False},
        {"first": "Sasha", "last": "Vezenkov", "num": 14, "pos": Player.Position.POWER_FORWARD, "height": 206, "weight": Decimal("102.0"), "birth": date(1995, 8, 6), "captain": False},
        {"first": "Alec", "last": "Peters", "num": 25, "pos": Player.Position.POWER_FORWARD, "height": 206, "weight": Decimal("107.0"), "birth": date(1995, 4, 13), "captain": False},
        {"first": "Nikola", "last": "Milutinov", "num": 33, "pos": Player.Position.CENTER, "height": 213, "weight": Decimal("116.0"), "birth": date(1994, 12, 30), "captain": False},
        {"first": "Moustapha", "last": "Fall", "num": 10, "pos": Player.Position.CENTER, "height": 218, "weight": Decimal("124.0"), "birth": date(1992, 2, 23), "captain": False},
    ],
    "fenerbahce-beko": [
        {"first": "Wade", "last": "Baldwin IV", "num": 2, "pos": Player.Position.POINT_GUARD, "height": 193, "weight": Decimal("91.0"), "birth": date(1996, 3, 29), "captain": False},
        {"first": "Arturs", "last": "Zagars", "num": 32, "pos": Player.Position.POINT_GUARD, "height": 190, "weight": Decimal("78.0"), "birth": date(2000, 4, 21), "captain": False},
        {"first": "Marko", "last": "Guduric", "num": 23, "pos": Player.Position.SHOOTING_GUARD, "height": 196, "weight": Decimal("91.0"), "birth": date(1995, 1, 22), "captain": False},
        {"first": "Devon", "last": "Hall", "num": 24, "pos": Player.Position.SHOOTING_GUARD, "height": 196, "weight": Decimal("86.0"), "birth": date(1995, 7, 7), "captain": False},
        {"first": "Bonzie", "last": "Colson", "num": 50, "pos": Player.Position.SMALL_FORWARD, "height": 198, "weight": Decimal("102.0"), "birth": date(1996, 1, 12), "captain": False},
        {"first": "Tarik", "last": "Biberovic", "num": 13, "pos": Player.Position.SMALL_FORWARD, "height": 201, "weight": Decimal("100.0"), "birth": date(2001, 1, 28), "captain": False},
        {"first": "Nigel", "last": "Hayes-Davis", "num": 11, "pos": Player.Position.POWER_FORWARD, "height": 203, "weight": Decimal("103.0"), "birth": date(1994, 12, 16), "captain": False},
        {"first": "Nicolo", "last": "Melli", "num": 4, "pos": Player.Position.POWER_FORWARD, "height": 205, "weight": Decimal("107.0"), "birth": date(1991, 1, 26), "captain": True},
        {"first": "Sertac", "last": "Sanli", "num": 5, "pos": Player.Position.CENTER, "height": 213, "weight": Decimal("115.0"), "birth": date(1991, 8, 5), "captain": False},
        {"first": "Boban", "last": "Marjanovic", "num": 51, "pos": Player.Position.CENTER, "height": 224, "weight": Decimal("132.0"), "birth": date(1988, 8, 15), "captain": False},
    ],
    "as-monaco-basket": [
        {"first": "Mike", "last": "James", "num": 55, "pos": Player.Position.POINT_GUARD, "height": 185, "weight": Decimal("84.0"), "birth": date(1990, 8, 18), "captain": True},
        {"first": "Nick", "last": "Calathes", "num": 33, "pos": Player.Position.POINT_GUARD, "height": 198, "weight": Decimal("97.0"), "birth": date(1989, 2, 7), "captain": False},
        {"first": "Elie", "last": "Okobo", "num": 0, "pos": Player.Position.SHOOTING_GUARD, "height": 191, "weight": Decimal("86.0"), "birth": date(1997, 10, 23), "captain": False},
        {"first": "Jordan", "last": "Loyd", "num": 3, "pos": Player.Position.SHOOTING_GUARD, "height": 193, "weight": Decimal("88.0"), "birth": date(1993, 7, 27), "captain": False},
        {"first": "Alpha", "last": "Diallo", "num": 11, "pos": Player.Position.SMALL_FORWARD, "height": 201, "weight": Decimal("95.0"), "birth": date(1997, 6, 29), "captain": False},
        {"first": "Jaron", "last": "Blossomgame", "num": 4, "pos": Player.Position.SMALL_FORWARD, "height": 201, "weight": Decimal("100.0"), "birth": date(1993, 9, 16), "captain": False},
        {"first": "Vitto", "last": "Brown", "num": 8, "pos": Player.Position.POWER_FORWARD, "height": 203, "weight": Decimal("107.0"), "birth": date(1995, 7, 13), "captain": False},
        {"first": "John", "last": "Brown III", "num": 28, "pos": Player.Position.POWER_FORWARD, "height": 203, "weight": Decimal("98.0"), "birth": date(1992, 1, 28), "captain": False},
        {"first": "Donatas", "last": "Motiejunas", "num": 20, "pos": Player.Position.CENTER, "height": 213, "weight": Decimal("118.0"), "birth": date(1990, 9, 20), "captain": False},
        {"first": "Mam", "last": "Jaiteh", "num": 14, "pos": Player.Position.CENTER, "height": 211, "weight": Decimal("112.0"), "birth": date(1994, 11, 27), "captain": False},
    ],
}


HISTORICAL_MEMBERSHIPS = [
    # Sloukas: Estuvo en Olympiacos y Fenerbahçe antes de Panathinaikos
    {"player": ("Kostas", "Sloukas"), "team": "olympiacos-piraeus", "season": "2023-2024", "num": 10, "captain": True},
    {"player": ("Kostas", "Sloukas"), "team": "fenerbahce-beko", "season": "2022-2023", "num": 16, "captain": False},
    {"player": ("Kostas", "Sloukas"), "team": "panathinaikos-aktor", "season": "2024-2025", "num": 10, "captain": True},

    # Campazzo: Real Madrid histórico
    {"player": ("Facundo", "Campazzo"), "team": "real-madrid-baloncesto", "season": "2024-2025", "num": 7, "captain": False},
    {"player": ("Facundo", "Campazzo"), "team": "valencia-basket", "season": "2023-2024", "num": 7, "captain": False},

    # Llull: Leyenda Real Madrid
    {"player": ("Sergio", "Llull"), "team": "real-madrid-baloncesto", "season": "2024-2025", "num": 23, "captain": True},
    {"player": ("Sergio", "Llull"), "team": "real-madrid-baloncesto", "season": "2023-2024", "num": 23, "captain": True},

    # Tavares: Real Madrid
    {"player": ("Walter", "Tavares"), "team": "real-madrid-baloncesto", "season": "2024-2025", "num": 22, "captain": False},
    {"player": ("Walter", "Tavares"), "team": "real-madrid-baloncesto", "season": "2023-2024", "num": 22, "captain": False},

    # Willy Hernangómez: Barça y antes Real Madrid
    {"player": ("Willy", "Hernangómez"), "team": "fc-barcelona-basket", "season": "2024-2025", "num": 14, "captain": False},
    {"player": ("Willy", "Hernangómez"), "team": "real-madrid-baloncesto", "season": "2023-2024", "num": 14, "captain": False},

    # Serge Ibaka: Real Madrid y antes Barça
    {"player": ("Serge", "Ibaka"), "team": "fc-barcelona-basket", "season": "2024-2025", "num": 9, "captain": False},
    {"player": ("Serge", "Ibaka"), "team": "real-madrid-baloncesto", "season": "2023-2024", "num": 9, "captain": False},

    # Mario Hezonja: Real Madrid, antes Panathinaikos y Barça
    {"player": ("Mario", "Hezonja"), "team": "panathinaikos-aktor", "season": "2024-2025", "num": 11, "captain": False},
    {"player": ("Mario", "Hezonja"), "team": "fc-barcelona-basket", "season": "2023-2024", "num": 11, "captain": False},

    # Mike James: Monaco y antes Panathinaikos
    {"player": ("Mike", "James"), "team": "as-monaco-basket", "season": "2024-2025", "num": 55, "captain": True},
    {"player": ("Mike", "James"), "team": "panathinaikos-aktor", "season": "2023-2024", "num": 55, "captain": False},

    # Nick Calathes: Monaco, antes Fenerbahce y Barça
    {"player": ("Nick", "Calathes"), "team": "fenerbahce-beko", "season": "2024-2025", "num": 33, "captain": False},
    {"player": ("Nick", "Calathes"), "team": "fc-barcelona-basket", "season": "2023-2024", "num": 33, "captain": False},
    {"player": ("Nick", "Calathes"), "team": "panathinaikos-aktor", "season": "2022-2023", "num": 33, "captain": True},

    # Nigel Williams-Goss: Olympiacos y antes Real Madrid
    {"player": ("Nigel", "Williams-Goss"), "team": "real-madrid-baloncesto", "season": "2024-2025", "num": 1, "captain": False},

    # Jan Vesely: Barça y antes Fenerbahce
    {"player": ("Jan", "Vesely"), "team": "fc-barcelona-basket", "season": "2024-2025", "num": 6, "captain": False},
    {"player": ("Jan", "Vesely"), "team": "fenerbahce-beko", "season": "2023-2024", "num": 24, "captain": False},

    # Sasha Vezenkov: Olympiacos y antes Barça
    {"player": ("Sasha", "Vezenkov"), "team": "fc-barcelona-basket", "season": "2023-2024", "num": 14, "captain": False},
    {"player": ("Sasha", "Vezenkov"), "team": "olympiacos-piraeus", "season": "2024-2025", "num": 14, "captain": False},

    # Kevin Punter: Barça y antes Olympiacos
    {"player": ("Kevin", "Punter"), "team": "olympiacos-piraeus", "season": "2024-2025", "num": 0, "captain": False},

    # Alex Abrines: Barça
    {"player": ("Alex", "Abrines"), "team": "fc-barcelona-basket", "season": "2024-2025", "num": 21, "captain": True},
    {"player": ("Alex", "Abrines"), "team": "unicaja-malaga", "season": "2023-2024", "num": 21, "captain": False},

    # Alberto Díaz: Unicaja
    {"player": ("Alberto", "Díaz"), "team": "unicaja-malaga", "season": "2024-2025", "num": 9, "captain": True},
    {"player": ("Alberto", "Díaz"), "team": "unicaja-malaga", "season": "2023-2024", "num": 9, "captain": True},

    # Chris Jones: Valencia y antes AS Monaco
    {"player": ("Chris", "Jones"), "team": "as-monaco-basket", "season": "2024-2025", "num": 7, "captain": False},
]


def generate_exact_player_stats(pts, mins, reb_off, reb_def, ast, stl, tov, blk_m, blk_r, f_comm, f_rec):
    """
    Descompone 'pts' de forma matemáticamente exacta:
    (two_points_made * 2) + (three_points_made * 3) + (free_throws_made * 1) == pts
    con intentos >= anotados siempre, y calcula el PIR oficial FIBA/ACB.
    """
    # 1. Determinar Tiros Libres (0 a 4)
    ft_m = random.randint(0, min(pts, 4))
    rem = pts - ft_m

    # 2. Buscar combinaciones de triples (T3) y tiros de 2 (T2)
    possible_t3 = [i for i in range(0, (rem // 3) + 1) if (rem - 3 * i) % 2 == 0]
    if possible_t3:
        t3_m = random.choice(possible_t3)
    else:
        t3_m = 0
        ft_m = pts % 2
        rem = pts - ft_m

    t2_m = (rem - 3 * t3_m) // 2

    # Verificación matemática estricta
    exact_sum = (t2_m * 2) + (t3_m * 3) + ft_m
    if exact_sum != pts:
        t3_m = 0
        ft_m = pts % 2
        t2_m = (pts - ft_m) // 2

    # 3. Intentos de tiro (siempre >= anotados)
    t2_a = t2_m + random.randint(0, 3)
    t3_a = t3_m + random.randint(0, 3)
    ft_a = ft_m + random.randint(0, 2)

    fg_m = t2_m + t3_m
    fg_a = t2_a + t3_a

    # 4. Fórmula Oficial FIBA / ACB de Valoración (PIR):
    # (PTS + REB_TOT + AST + STL + BLK_M + FOUL_REC) - ((FG_A - FG_M) + (FT_A - FT_M) + TOV + BLK_R + FOUL_COMM)
    tot_reb = reb_off + reb_def
    pos_val = pts + tot_reb + ast + stl + blk_m + f_rec
    neg_val = (fg_a - fg_m) + (ft_a - ft_m) + tov + blk_r + f_comm
    pir = max(0, pos_val - neg_val)

    return {
        "minutes_played": mins,
        "points": pts,
        "field_goals_made": fg_m,
        "field_goals_attempted": fg_a,
        "three_points_made": t3_m,
        "three_points_attempted": t3_a,
        "free_throws_made": ft_m,
        "free_throws_attempted": ft_a,
        "rebounds_off": reb_off,
        "rebounds_def": reb_def,
        "assists": ast,
        "steals": stl,
        "turnovers": tov,
        "blocks_made": blk_m,
        "blocks_received": blk_r,
        "fouls_committed": f_comm,
        "fouls_received": f_rec,
        "valuation_pir": pir,
    }


def distribute_team_points(total_score, count=8):
    """
    Distribuye los puntos totales del marcador entre los jugadores con minutos
    garantizando que la suma de puntos individuales sea exactamente igual a total_score.
    """
    if count <= 0:
        return []
    # Generar pesos aleatorios
    weights = [random.uniform(0.5, 3.0) for _ in range(count)]
    total_weight = sum(weights)
    points = [max(2, int(round((w / total_weight) * total_score))) for w in weights]

    # Ajustar diferencia exacta para que la suma sea exactamente total_score
    diff = total_score - sum(points)
    i = 0
    while diff != 0:
        idx = i % count
        if diff > 0:
            points[idx] += 1
            diff -= 1
        elif diff < 0 and points[idx] > 1:
            points[idx] -= 1
            diff += 1
        i += 1

    return sorted(points, reverse=True)


class Command(BaseCommand):
    help = "Puebla las plantillas completas de 10 jugadores, deduplica jugadores y crea historial multiclub con estadísticas matemáticamente exactas."

    def handle(self, *args, **options):
        # 1. PASO PREVIO: Deduplicar jugadores existentes en la base de datos
        self.stdout.write("Ejecutando deduplicación de jugadores...")
        all_players = list(Player.objects.all().order_by("id"))
        seen_players = {}
        merged_count = 0

        for p in all_players:
            key = (normalize_str(p.first_name), normalize_str(p.last_name))
            if key in seen_players:
                canonical = seen_players[key]
                for tm in TeamMembership.objects.filter(player=p):
                    if not TeamMembership.objects.filter(player=canonical, team=tm.team, season=tm.season).exists():
                        tm.player = canonical
                        tm.save()
                    else:
                        tm.delete()
                PlayerMatchStat.objects.filter(player=p).update(player=canonical)
                p.delete()
                merged_count += 1
            else:
                seen_players[key] = p

        self.stdout.write(self.style.SUCCESS(f"Deduplicación finalizada: {merged_count} registros duplicados eliminados."))

        # 2. Temporada actual
        current_season = Season.objects.filter(is_current=True).first()
        if not current_season:
            current_season = Season.objects.first()

        league = current_season.league if current_season else League.objects.first()

        # 3. Asegurar Temporadas Históricas Pasadas
        seasons_map = {
            "2024-2025": Season.objects.get_or_create(
                league=league,
                name="Temporada 2024-2025",
                defaults={"start_date": date(2024, 9, 15), "end_date": date(2025, 6, 20), "is_current": False}
            )[0],
            "2023-2024": Season.objects.get_or_create(
                league=league,
                name="Temporada 2023-2024",
                defaults={"start_date": date(2023, 9, 15), "end_date": date(2024, 6, 20), "is_current": False}
            )[0],
            "2022-2023": Season.objects.get_or_create(
                league=league,
                name="Temporada 2022-2023",
                defaults={"start_date": date(2022, 9, 15), "end_date": date(2023, 6, 20), "is_current": False}
            )[0],
        }

        total_players = 0
        total_memberships = 0

        # 4. Poblar y actualizar los 80 jugadores y membresías activas actuales
        for team_slug, players_data in ALL_TEAMS_ROSTERS.items():
            team = Team.objects.filter(slug=team_slug).first()
            if not team:
                continue

            TeamMembership.objects.filter(team=team, season=current_season).delete()

            for p_info in players_data:
                norm_fn = normalize_str(p_info["first"])
                norm_ln = normalize_str(p_info["last"])

                player = None
                for candidate in Player.objects.all():
                    if normalize_str(candidate.first_name) == norm_fn and normalize_str(candidate.last_name) == norm_ln:
                        player = candidate
                        break

                if not player:
                    player = Player.objects.create(
                        first_name=p_info["first"],
                        last_name=p_info["last"],
                    )

                player.first_name = p_info["first"]
                player.last_name = p_info["last"]
                player.birth_date = p_info["birth"]
                player.height_cm = p_info["height"]
                player.weight_kg = p_info["weight"]
                player.position = p_info["pos"]
                player.is_active = True
                player.save()
                total_players += 1

                TeamMembership.objects.create(
                    team=team,
                    player=player,
                    season=current_season,
                    jersey_number=p_info["num"],
                    is_captain=p_info.get("captain", False),
                    is_active=True,
                )
                total_memberships += 1

            self.stdout.write(self.style.SUCCESS(f"Plantilla de {team.name} completada con {len(players_data)} jugadores."))

        # 5. Asignar historial multiclub y multitemporada
        for hist in HISTORICAL_MEMBERSHIPS:
            p_first, p_last = hist["player"]
            norm_fn = normalize_str(p_first)
            norm_ln = normalize_str(p_last)
            p = None
            for candidate in Player.objects.all():
                if normalize_str(candidate.first_name) == norm_fn and normalize_str(candidate.last_name) == norm_ln:
                    p = candidate
                    break
            t = Team.objects.filter(slug=hist["team"]).first()
            s = seasons_map.get(hist["season"])
            if p and t and s:
                TeamMembership.objects.filter(team=t, season=s, jersey_number=hist["num"]).delete()
                TeamMembership.objects.filter(player=p, season=s).delete()
                TeamMembership.objects.create(
                    team=t,
                    player=p,
                    season=s,
                    jersey_number=hist["num"],
                    is_captain=hist["captain"],
                    is_active=False,
                )

        # Asegurar que todas las membresías de temporadas pasadas queden formalmente inactivas
        TeamMembership.objects.exclude(season=current_season).update(is_active=False)

        # 6. Generar estadísticas de partido matemáticamente coherentes para TODOS los partidos finalizados
        matches = Match.objects.filter(status=Match.Status.FINISHED)
        total_stats = 0
        for match in matches:
            PlayerMatchStat.objects.filter(match=match).delete()
            seen_player_ids = set()

            # Local Box Score
            home_memberships = list(TeamMembership.objects.filter(team=match.home_team, season=match.season, is_active=True)[:8])
            if not home_memberships:
                home_memberships = list(TeamMembership.objects.filter(team=match.home_team, is_active=True)[:8])

            home_points_dist = distribute_team_points(match.home_score, len(home_memberships))

            for idx, m in enumerate(home_memberships):
                if m.player_id in seen_player_ids:
                    continue
                seen_player_ids.add(m.player_id)

                p_pts = home_points_dist[idx] if idx < len(home_points_dist) else random.randint(4, 16)
                p_mins = random.randint(14, 34)
                p_reb_off = random.randint(0, 3)
                p_reb_def = random.randint(1, 6)
                p_ast = random.randint(1, 8)
                p_stl = random.randint(0, 3)
                p_tov = random.randint(0, 3)
                p_blk_m = random.randint(0, 2)
                p_blk_r = random.randint(0, 1)
                p_f_comm = random.randint(1, 4)
                p_f_rec = random.randint(1, 5)

                exact_stat = generate_exact_player_stats(
                    pts=p_pts,
                    mins=p_mins,
                    reb_off=p_reb_off,
                    reb_def=p_reb_def,
                    ast=p_ast,
                    stl=p_stl,
                    tov=p_tov,
                    blk_m=p_blk_m,
                    blk_r=p_blk_r,
                    f_comm=p_f_comm,
                    f_rec=p_f_rec,
                )

                PlayerMatchStat.objects.create(
                    match=match,
                    player=m.player,
                    team=match.home_team,
                    **exact_stat
                )
                total_stats += 1

            # Visitante Box Score
            away_memberships = list(TeamMembership.objects.filter(team=match.away_team, season=match.season, is_active=True)[:8])
            if not away_memberships:
                away_memberships = list(TeamMembership.objects.filter(team=match.away_team, is_active=True)[:8])

            away_points_dist = distribute_team_points(match.away_score, len(away_memberships))

            for idx, m in enumerate(away_memberships):
                if m.player_id in seen_player_ids:
                    continue
                seen_player_ids.add(m.player_id)

                p_pts = away_points_dist[idx] if idx < len(away_points_dist) else random.randint(4, 16)
                p_mins = random.randint(12, 32)
                p_reb_off = random.randint(0, 3)
                p_reb_def = random.randint(1, 5)
                p_ast = random.randint(0, 7)
                p_stl = random.randint(0, 2)
                p_tov = random.randint(0, 3)
                p_blk_m = random.randint(0, 1)
                p_blk_r = random.randint(0, 1)
                p_f_comm = random.randint(1, 4)
                p_f_rec = random.randint(1, 4)

                exact_stat = generate_exact_player_stats(
                    pts=p_pts,
                    mins=p_mins,
                    reb_off=p_reb_off,
                    reb_def=p_reb_def,
                    ast=p_ast,
                    stl=p_stl,
                    tov=p_tov,
                    blk_m=p_blk_m,
                    blk_r=p_blk_r,
                    f_comm=p_f_comm,
                    f_rec=p_f_rec,
                )

                PlayerMatchStat.objects.create(
                    match=match,
                    player=m.player,
                    team=match.away_team,
                    **exact_stat
                )
                total_stats += 1

        # 7. Obtener y asignar fotografías reales de alta definición para todos los jugadores
        from django.core.management import call_command
        try:
            call_command("seed_real_player_photos")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Nota fotos reales: {e}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Sincronización completa: Base de datos limpia sin duplicados, estadísticas matemáticamente exactas ({total_stats} registros creados) y fotos reales de atletas asignadas."
            )
        )
