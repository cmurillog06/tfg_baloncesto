import os
import shutil
from datetime import timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from apps.teams.models import League, Season, Team, Player, TeamMembership
from apps.matches.models import Match
from apps.analytics.models import PlayerMatchStat
from apps.analytics.services import recalculate_season_standings

EUROLEAGUE_CRESTS = {
    "PAO": "pao_crest.jpg",
    "OLY": "oly_crest.jpg",
    "FNB": "fnb_crest.jpg",
    "ASM": "asm_crest.jpg",
}

EUROLEAGUE_TEAMS_DATA = [
    {
        "name": "Panathinaikos AKTOR",
        "slug": "panathinaikos-aktor",
        "acronym": "PAO",
        "primary_color": "#007A33",
        "secondary_color": "#C59B27",
        "city": "Atenas",
        "arena_name": "OAKA Altion",
        "crest_key": "PAO",
        "players": [
            {"first": "Kendrick", "last": "Nunn", "num": 25, "pos": Player.Position.SHOOTING_GUARD, "height": 191, "weight": Decimal("86.0")},
            {"first": "Kostas", "last": "Sloukas", "num": 10, "pos": Player.Position.POINT_GUARD, "height": 190, "weight": Decimal("87.0")},
            {"first": "Mathias", "last": "Lessort", "num": 26, "pos": Player.Position.CENTER, "height": 206, "weight": Decimal("112.0")},
            {"first": "Juancho", "last": "Hernangómez", "num": 41, "pos": Player.Position.POWER_FORWARD, "height": 206, "weight": Decimal("100.0")},
        ]
    },
    {
        "name": "Olympiacos Piraeus",
        "slug": "olympiacos-piraeus",
        "acronym": "OLY",
        "primary_color": "#D4001F",
        "secondary_color": "#FFFFFF",
        "city": "El Pireo",
        "arena_name": "Peace and Friendship Stadium",
        "crest_key": "OLY",
        "players": [
            {"first": "Sasha", "last": "Vezenkov", "num": 14, "pos": Player.Position.POWER_FORWARD, "height": 206, "weight": Decimal("102.0")},
            {"first": "Evan", "last": "Fournier", "num": 94, "pos": Player.Position.SHOOTING_GUARD, "height": 198, "weight": Decimal("93.0")},
            {"first": "Thomas", "last": "Walkup", "num": 0, "pos": Player.Position.POINT_GUARD, "height": 193, "weight": Decimal("92.0")},
            {"first": "Nikola", "last": "Milutinov", "num": 33, "pos": Player.Position.CENTER, "height": 213, "weight": Decimal("116.0")},
        ]
    },
    {
        "name": "Fenerbahçe Beko",
        "slug": "fenerbahce-beko",
        "acronym": "FNB",
        "primary_color": "#002D62",
        "secondary_color": "#FFCC00",
        "city": "Estambul",
        "arena_name": "Ülker Sports Arena",
        "crest_key": "FNB",
        "players": [
            {"first": "Nigel", "last": "Hayes-Davis", "num": 11, "pos": Player.Position.POWER_FORWARD, "height": 203, "weight": Decimal("103.0")},
            {"first": "Wade", "last": "Baldwin IV", "num": 2, "pos": Player.Position.POINT_GUARD, "height": 193, "weight": Decimal("91.0")},
            {"first": "Marko", "last": "Guduric", "num": 23, "pos": Player.Position.SHOOTING_GUARD, "height": 196, "weight": Decimal("91.0")},
            {"first": "Nicolo", "last": "Melli", "num": 4, "pos": Player.Position.POWER_FORWARD, "height": 205, "weight": Decimal("107.0")},
        ]
    },
    {
        "name": "AS Monaco Basket",
        "slug": "as-monaco-basket",
        "acronym": "ASM",
        "primary_color": "#C59B27",
        "secondary_color": "#D4001F",
        "city": "Mónaco",
        "arena_name": "Salle Gaston Médecin",
        "crest_key": "ASM",
        "players": [
            {"first": "Mike", "last": "James", "num": 55, "pos": Player.Position.POINT_GUARD, "height": 185, "weight": Decimal("84.0")},
            {"first": "Elie", "last": "Okobo", "num": 0, "pos": Player.Position.SHOOTING_GUARD, "height": 191, "weight": Decimal("86.0")},
            {"first": "Alpha", "last": "Diallo", "num": 11, "pos": Player.Position.SMALL_FORWARD, "height": 201, "weight": Decimal("95.0")},
            {"first": "Donatas", "last": "Motiejunas", "num": 20, "pos": Player.Position.CENTER, "height": 213, "weight": Decimal("118.0")},
        ]
    },
]


class Command(BaseCommand):
    help = "Crea clubes internacionales exclusivos para la EuroLeague con escudos 1:1, plantillas, partidos y clasificación."

    def handle(self, *args, **options):
        media_teams_dir = os.path.join(settings.MEDIA_ROOT, "teams")
        os.makedirs(media_teams_dir, exist_ok=True)

        # 1. Asegurar Liga EuroLeague y Temporada
        euroleague, _ = League.objects.get_or_create(
            slug="euroleague-basketball",
            defaults={
                "name": "EuroLeague Basketball",
                "description": "La máxima competición de clubes de baloncesto de Europa.",
                "is_active": True,
            }
        )

        season_euro, _ = Season.objects.get_or_create(
            league=euroleague,
            name="Temporada 2026/2027",
            defaults={
                "start_date": "2026-10-01",
                "end_date": "2027-05-28",
                "is_current": True,
            }
        )

        created_teams = {}

        # 2. Crear Equipos de EuroLeague y asignar escudos 1:1
        for data in EUROLEAGUE_TEAMS_DATA:
            crest_filename = EUROLEAGUE_CRESTS[data["crest_key"]]

            team, _ = Team.objects.update_or_create(
                slug=data["slug"],
                defaults={
                    "name": data["name"],
                    "acronym": data["acronym"],
                    "primary_color": data["primary_color"],
                    "secondary_color": data["secondary_color"],
                    "city": data["city"],
                    "arena_name": data["arena_name"],
                    "logo": f"teams/{crest_filename}",
                }
            )
            created_teams[data["acronym"]] = team

            # Crear Jugadores y Membresías
            for p_data in data["players"]:
                player, _ = Player.objects.update_or_create(
                    first_name=p_data["first"],
                    last_name=p_data["last"],
                    defaults={
                        "position": p_data["pos"],
                        "height_cm": p_data["height"],
                        "weight_kg": p_data["weight"],
                    }
                )
                TeamMembership.objects.update_or_create(
                    team=team,
                    player=player,
                    season=season_euro,
                    defaults={
                        "jersey_number": p_data["num"],
                        "is_active": True,
                    }
                )

        pao = created_teams["PAO"]
        oly = created_teams["OLY"]
        fnb = created_teams["FNB"]
        asm = created_teams["ASM"]

        rmb = Team.objects.filter(slug="real-madrid-baloncesto").first()
        bar = Team.objects.filter(slug="fc-barcelona-basket").first()

        now = timezone.now()

        # 3. Crear Partidos de EuroLeague (Jornada 1 y 2 completas para los 6 equipos)
        # Jornada 1 (3 partidos)
        m1, _ = Match.objects.update_or_create(
            home_team=pao,
            away_team=oly,
            season=season_euro,
            round_number=1,
            defaults={
                "scheduled_at": now - timedelta(days=14),
                "location": f"{pao.arena_name or 'OAKA Altion'}, {pao.city or 'Atenas'}",
                "status": Match.Status.FINISHED,
                "current_period": Match.Period.FINISHED,
                "game_clock": "00:00",
                "home_score": 88,
                "away_score": 85,
            }
        )
        m2, _ = Match.objects.update_or_create(
            home_team=fnb,
            away_team=asm,
            season=season_euro,
            round_number=1,
            defaults={
                "scheduled_at": now - timedelta(days=13),
                "location": f"{fnb.arena_name or 'Ülker Sports Arena'}, {fnb.city or 'Estambul'}",
                "status": Match.Status.FINISHED,
                "current_period": Match.Period.FINISHED,
                "game_clock": "00:00",
                "home_score": 91,
                "away_score": 84,
            }
        )
        if rmb and bar:
            m_extra1, _ = Match.objects.update_or_create(
                home_team=rmb,
                away_team=bar,
                season=season_euro,
                round_number=1,
                defaults={
                    "scheduled_at": now - timedelta(days=13),
                    "location": f"{rmb.arena_name or 'WiZink Center'}, {rmb.city or 'Madrid'}",
                    "status": Match.Status.FINISHED,
                    "current_period": Match.Period.FINISHED,
                    "game_clock": "00:00",
                    "home_score": 89,
                    "away_score": 83,
                }
            )

        # Partidos disputados de las jornadas siguientes
        m3, _ = Match.objects.update_or_create(
            home_team=pao,
            away_team=fnb,
            season=season_euro,
            round_number=2,
            defaults={
                "scheduled_at": now - timedelta(days=7),
                "location": f"{pao.arena_name or 'OAKA Altion'}, {pao.city or 'Atenas'}",
                "status": Match.Status.FINISHED,
                "current_period": Match.Period.FINISHED,
                "game_clock": "00:00",
                "home_score": 94,
                "away_score": 89,
            }
        )
        m4, _ = Match.objects.update_or_create(
            home_team=oly,
            away_team=asm,
            season=season_euro,
            round_number=3,
            defaults={
                "scheduled_at": now - timedelta(days=6),
                "location": f"{oly.arena_name or 'Peace and Friendship Stadium'}, {oly.city or 'El Pireo'}",
                "status": Match.Status.FINISHED,
                "current_period": Match.Period.FINISHED,
                "game_clock": "00:00",
                "home_score": 86,
                "away_score": 82,
            }
        )

        # 4. Generar Estadísticas de Jugadores de EuroLeague
        for match, t_home, t_away in [(m1, pao, oly), (m2, fnb, asm), (m3, pao, fnb), (m4, oly, asm)]:
            for team in [t_home, t_away]:
                members = TeamMembership.objects.filter(team=team, season=season_euro).select_related("player")
                for m in members:
                    stat, _ = PlayerMatchStat.objects.update_or_create(
                        match=match,
                        player=m.player,
                        defaults={
                            "team": team,
                            "minutes_played": 28,
                            "points": 18,
                            "field_goals_made": 6,
                            "field_goals_attempted": 10,
                            "three_points_made": 2,
                            "three_points_attempted": 5,
                            "free_throws_made": 4,
                            "free_throws_attempted": 4,
                            "rebounds_def": 4,
                            "rebounds_off": 1,
                            "assists": 5,
                            "steals": 2,
                            "blocks_made": 1,
                            "blocks_received": 0,
                            "fouls_committed": 2,
                            "fouls_received": 4,
                            "turnovers": 2,
                            "valuation_pir": 21,
                        }
                    )
                    stat.valuation_pir = stat.compute_pir()
                    stat.save()

        # 5. Recalcular Clasificación Oficial de EuroLeague
        recalculate_season_standings(season_euro)

        self.stdout.write(self.style.SUCCESS("🎉 ¡EuroLeague poblada con éxito con 4 gigantes europeos exclusivos, escudos 1:1, partidos y clasificación!"))
