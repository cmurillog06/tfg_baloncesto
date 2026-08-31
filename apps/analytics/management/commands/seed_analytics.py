from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.matches.models import Match
from apps.teams.models import Team, Player, Season, TeamMembership
from apps.analytics.models import PlayerMatchStat
from apps.analytics.services import recalculate_season_standings


class Command(BaseCommand):
    help = "Genera estadísticas avanzadas de jugadores y recalcula clasificaciones automáticamente."

    def handle(self, *args, **options):
        season = Season.objects.filter(is_current=True).first() or Season.objects.first()
        if not season:
            self.stdout.write(self.style.ERROR("No hay ninguna temporada activa."))
            return

        teams = list(Team.objects.all())
        if len(teams) < 2:
            self.stdout.write(self.style.ERROR("Se necesitan al menos 2 equipos en la base de datos."))
            return

        team_1 = teams[0]
        team_2 = teams[1]
        team_3 = teams[2] if len(teams) > 2 else teams[0]
        team_4 = teams[3] if len(teams) > 3 else teams[1]

        now = timezone.now()

        # 1. Crear / Asegurar Partidos Finalizados de prueba
        m1, _ = Match.objects.get_or_create(
            home_team=team_1,
            away_team=team_2,
            season=season,
            round_number=1,
            defaults={
                "scheduled_at": now - timedelta(days=7),
                "location": team_1.arena_name or "Pabellón Oficial",
                "status": Match.Status.FINISHED,
                "current_period": Match.Period.FINISHED,
                "game_clock": "00:00",
                "home_score": 89,
                "away_score": 83,
            },
        )
        m1.status = Match.Status.FINISHED
        m1.home_score = 89
        m1.away_score = 83
        m1.save()

        m2, _ = Match.objects.get_or_create(
            home_team=team_3,
            away_team=team_4,
            season=season,
            round_number=1,
            defaults={
                "scheduled_at": now - timedelta(days=6),
                "location": team_3.arena_name or "Pabellón Oficial",
                "status": Match.Status.FINISHED,
                "current_period": Match.Period.FINISHED,
                "game_clock": "00:00",
                "home_score": 86,
                "away_score": 79,
            },
        )
        m2.status = Match.Status.FINISHED
        m2.home_score = 86
        m2.away_score = 79
        m2.save()

        # 2. Generar Estadísticas de Jugadores para Partido 1
        memberships_1 = list(TeamMembership.objects.filter(team=team_1, is_active=True).select_related("player"))
        memberships_2 = list(TeamMembership.objects.filter(team=team_2, is_active=True).select_related("player"))

        # Si no tienen membresías, usamos jugadores globales
        players_1 = [m.player for m in memberships_1] if memberships_1 else list(Player.objects.all()[:4])
        players_2 = [m.player for m in memberships_2] if memberships_2 else list(Player.objects.all()[4:8])

        # Asignar estadísticas realistas a jugadores de Equipo 1
        stats_data_1 = [
            {"pts": 22, "ast": 8, "reb_o": 1, "reb_d": 3, "stl": 3, "t3": 4, "t3_att": 7, "fg": 7, "fg_att": 12, "ft": 4, "ft_att": 4, "foul_c": 2, "foul_r": 5, "min": 29},
            {"pts": 18, "ast": 2, "reb_o": 4, "reb_d": 9, "stl": 1, "t3": 0, "t3_att": 0, "fg": 8, "fg_att": 11, "ft": 2, "ft_att": 3, "foul_c": 3, "foul_r": 4, "min": 27},
            {"pts": 15, "ast": 4, "reb_o": 1, "reb_d": 4, "stl": 2, "t3": 3, "t3_att": 6, "fg": 5, "fg_att": 10, "ft": 2, "ft_att": 2, "foul_c": 2, "foul_r": 2, "min": 24},
            {"pts": 11, "ast": 3, "reb_o": 0, "reb_d": 2, "stl": 1, "t3": 2, "t3_att": 5, "fg": 4, "fg_att": 8, "ft": 1, "ft_att": 2, "foul_c": 1, "foul_r": 1, "min": 20},
        ]

        for i, player in enumerate(players_1):
            s = stats_data_1[i % len(stats_data_1)]
            PlayerMatchStat.objects.update_or_create(
                match=m1,
                player=player,
                defaults={
                    "team": team_1,
                    "minutes_played": s["min"],
                    "points": s["pts"],
                    "field_goals_made": s["fg"],
                    "field_goals_attempted": s["fg_att"],
                    "three_points_made": s["t3"],
                    "three_points_attempted": s["t3_att"],
                    "free_throws_made": s["ft"],
                    "free_throws_attempted": s["ft_att"],
                    "rebounds_off": s["reb_o"],
                    "rebounds_def": s["reb_d"],
                    "assists": s["ast"],
                    "steals": s["stl"],
                    "fouls_committed": s["foul_c"],
                    "fouls_received": s["foul_r"],
                }
            )

        # Asignar estadísticas realistas a jugadores de Equipo 2
        stats_data_2 = [
            {"pts": 24, "ast": 6, "reb_o": 0, "reb_d": 3, "stl": 2, "t3": 4, "t3_att": 9, "fg": 8, "fg_att": 15, "ft": 4, "ft_att": 5, "foul_c": 3, "foul_r": 4, "min": 31},
            {"pts": 16, "ast": 1, "reb_o": 3, "reb_d": 8, "stl": 0, "t3": 0, "t3_att": 1, "fg": 7, "fg_att": 10, "ft": 2, "ft_att": 4, "foul_c": 4, "foul_r": 3, "min": 25},
            {"pts": 14, "ast": 5, "reb_o": 1, "reb_d": 2, "stl": 1, "t3": 2, "t3_att": 5, "fg": 5, "fg_att": 9, "ft": 2, "ft_att": 2, "foul_c": 2, "foul_r": 3, "min": 23},
            {"pts": 9, "ast": 2, "reb_o": 1, "reb_d": 4, "stl": 1, "t3": 1, "t3_att": 3, "fg": 3, "fg_att": 7, "ft": 2, "ft_att": 2, "foul_c": 2, "foul_r": 1, "min": 18},
        ]

        for i, player in enumerate(players_2):
            s = stats_data_2[i % len(stats_data_2)]
            PlayerMatchStat.objects.update_or_create(
                match=m1,
                player=player,
                defaults={
                    "team": team_2,
                    "minutes_played": s["min"],
                    "points": s["pts"],
                    "field_goals_made": s["fg"],
                    "field_goals_attempted": s["fg_att"],
                    "three_points_made": s["t3"],
                    "three_points_attempted": s["t3_att"],
                    "free_throws_made": s["ft"],
                    "free_throws_attempted": s["ft_att"],
                    "rebounds_off": s["reb_o"],
                    "rebounds_def": s["reb_d"],
                    "assists": s["ast"],
                    "steals": s["stl"],
                    "fouls_committed": s["foul_c"],
                    "fouls_received": s["foul_r"],
                }
            )

        # 3. Recalcular automáticamente las clasificaciones
        recalculate_season_standings(season)

        self.stdout.write(
            self.style.SUCCESS(
                f"Estadísticas avanzadas generadas y clasificaciones actualizadas con éxito para {season}."
            )
        )
