import random
from datetime import date, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.teams.models import League, Season, Team, Player, TeamMembership
from apps.matches.models import Match, MatchEvent, DigitalScoreSheet
from apps.analytics.models import Standing, PlayerMatchStat
from apps.analytics.services import recalculate_season_standings
from apps.teams.management.commands.seed_full_rosters import (
    ALL_TEAMS_ROSTERS,
    generate_exact_player_stats,
    distribute_team_points,
    generate_match_events_from_stats,
)

User = get_user_model()


def generate_berger_rounds(teams):
    """
    Genera jornadas canónicas de ida y vuelta para una lista de equipos:
    - Primera Vuelta (J1 a N-1): todos los equipos se enfrentan exactamente 1 vez.
    - Segunda Vuelta (Jornadas N a 2*(N-1)): se repiten los mismos cruces invirtiendo local/visitante.
    """
    n = len(teams)
    team_list = list(teams)
    if n == 4:
        t0, t1, t2, t3 = team_list[0], team_list[1], team_list[2], team_list[3]
        first_leg = [
            [(t2, t3), (t0, t1)],  # J1: (UNI, VAL), (RMB, BAR)
            [(t3, t1), (t2, t0)],  # J2: (VAL, BAR), (UNI, RMB)
            [(t0, t3), (t1, t2)],  # J3: (RMB, VAL), (BAR, UNI)
        ]
    else:
        rounds = []
        for r in range(n - 1):
            round_matches = []
            for i in range(n // 2):
                t1 = (r - i) % (n - 1)
                t2 = (r + i) % (n - 1)
                if i == 0:
                    t2 = n - 1
                if r % 2 == 0:
                    home, away = teams[t1], teams[t2]
                else:
                    home, away = teams[t2], teams[t1]
                round_matches.append((home, away))
            rounds.append(round_matches)
        first_leg = rounds

    all_rounds = list(first_leg)
    second_leg = []
    for r_matches in first_leg:
        return_matches = [(away, home) for home, away in r_matches]
        second_leg.append(return_matches)
    all_rounds.extend(second_leg)

    return all_rounds


class Command(BaseCommand):
    help = "Genera el histórico completo de temporadas (2024/2025 y 2025/2026 pasadas, y 2026/2027 actual) con calendarios realistas y estadísticas completas para todos los jugadores."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("🏀 INICIALIZANDO HISTÓRICO DE TEMPORADAS Y CALENDARIOS OFICIALES"))
        self.stdout.write("=" * 75)

        # 1. Obtener árbitros y mesa oficial
        mesa = User.objects.filter(username="oficial_mesa").first()
        crono = User.objects.filter(username="cronometrador").first()
        ref1 = User.objects.filter(username="arbitro_principal").first()
        ref2 = User.objects.filter(username="arbitro_fiba").first()

        # 2. Asegurar Ligas
        acb, _ = League.objects.get_or_create(
            slug="liga-endesa-acb",
            defaults={"name": "Liga Endesa ACB", "description": "Máxima competición nacional de baloncesto en España.", "is_active": True}
        )
        euroleague, _ = League.objects.get_or_create(
            slug="euroleague-basketball",
            defaults={"name": "EuroLeague Basketball", "description": "La máxima competición de clubes de baloncesto de Europa.", "is_active": True}
        )

        # 3. Limpiar temporadas obsoletas o con nombres no canónicos (p. ej. "2025/2026", "Temporada 2023/2024")
        valid_season_names = ["Temporada 2024/2025", "Temporada 2025/2026", "Temporada 2026/2027"]
        obsolete_seasons = Season.objects.exclude(name__in=valid_season_names)
        if obsolete_seasons.exists():
            self.stdout.write(f"🧹 Depurando {obsolete_seasons.count()} temporadas duplicadas u obsoletas...")
            obsolete_seasons.delete()

        # 4. Definir las 6 Temporadas Canónicas Oficiales
        seasons_config = [
            # Liga Endesa ACB (4 Equipos -> 6 Jornadas, 12 Partidos)
            {
                "league": acb,
                "name": "Temporada 2024/2025",
                "start_date": date(2024, 9, 28),
                "end_date": date(2025, 6, 20),
                "is_current": False,
                "teams_slugs": ["real-madrid-baloncesto", "fc-barcelona-basket", "unicaja-malaga", "valencia-basket"],
                "seed": 202420251,
            },
            {
                "league": acb,
                "name": "Temporada 2025/2026",
                "start_date": date(2025, 9, 27),
                "end_date": date(2026, 6, 18),
                "is_current": False,
                "teams_slugs": ["real-madrid-baloncesto", "fc-barcelona-basket", "unicaja-malaga", "valencia-basket"],
                "seed": 202520261,
            },
            {
                "league": acb,
                "name": "Temporada 2026/2027",
                "start_date": date(2026, 9, 26),
                "end_date": date(2027, 6, 20),
                "is_current": True,
                "teams_slugs": ["real-madrid-baloncesto", "fc-barcelona-basket", "unicaja-malaga", "valencia-basket"],
                "seed": 202620271,
            },
            # EuroLeague Basketball (6 Equipos -> 10 Jornadas, 30 Partidos)
            {
                "league": euroleague,
                "name": "Temporada 2024/2025",
                "start_date": date(2024, 10, 3),
                "end_date": date(2025, 5, 25),
                "is_current": False,
                "teams_slugs": [
                    "panathinaikos-aktor", "olympiacos-piraeus", "fenerbahce-beko", "as-monaco-basket",
                    "real-madrid-baloncesto", "fc-barcelona-basket"
                ],
                "seed": 202420252,
            },
            {
                "league": euroleague,
                "name": "Temporada 2025/2026",
                "start_date": date(2025, 10, 2),
                "end_date": date(2026, 5, 30),
                "is_current": False,
                "teams_slugs": [
                    "panathinaikos-aktor", "olympiacos-piraeus", "fenerbahce-beko", "as-monaco-basket",
                    "real-madrid-baloncesto", "fc-barcelona-basket"
                ],
                "seed": 202520262,
            },
            {
                "league": euroleague,
                "name": "Temporada 2026/2027",
                "start_date": date(2026, 10, 1),
                "end_date": date(2027, 5, 28),
                "is_current": True,
                "teams_slugs": [
                    "panathinaikos-aktor", "olympiacos-piraeus", "fenerbahce-beko", "as-monaco-basket",
                    "real-madrid-baloncesto", "fc-barcelona-basket"
                ],
                "seed": 202620272,
            },
        ]

        created_seasons = {}

        self.stdout.write("\n📅 [1/4] Creando temporadas canónicas (2 pasadas + 1 actual por liga)...")
        for cfg in seasons_config:
            season, _ = Season.objects.get_or_create(
                league=cfg["league"],
                name=cfg["name"],
                defaults={
                    "start_date": cfg["start_date"],
                    "end_date": cfg["end_date"],
                    "is_current": cfg["is_current"],
                }
            )
            season.start_date = cfg["start_date"]
            season.end_date = cfg["end_date"]
            season.is_current = cfg["is_current"]
            season.save()
            created_seasons[(cfg["league"].slug, cfg["name"])] = (season, cfg)
            status_tag = "ACTUAL (ACTIVA)" if cfg["is_current"] else "HISTÓRICA (FINALIZADA)"
            self.stdout.write(f"   ✓ {cfg['league'].name} - {cfg['name']} ({status_tag})")

        # 5. Asegurar Membresías de Jugadores en todas las temporadas
        self.stdout.write("\n👥 [2/4] Generando fichas e historial de plantillas para todos los 80 jugadores...")
        all_teams = {t.slug: t for t in Team.objects.all()}

        # Limpiar membresías erróneas donde equipos nacionales/europeos exclusivos estuvieran en ligas erróneas
        TeamMembership.objects.filter(
            team__slug__in=["unicaja-malaga", "valencia-basket"],
            season__league__slug="euroleague-basketball"
        ).delete()
        TeamMembership.objects.filter(
            team__slug__in=["panathinaikos-aktor", "olympiacos-piraeus", "fenerbahce-beko", "as-monaco-basket"],
            season__league__slug="liga-endesa-acb"
        ).delete()

        for (league_slug, season_name), (season, cfg) in created_seasons.items():
            for team_slug in cfg["teams_slugs"]:
                team = all_teams.get(team_slug)
                if not team:
                    continue
                roster = ALL_TEAMS_ROSTERS.get(team_slug, [])
                for p_data in roster:
                    player = Player.objects.filter(first_name=p_data["first"], last_name=p_data["last"]).first()
                    if not player:
                        player = Player.objects.create(
                            first_name=p_data["first"],
                            last_name=p_data["last"],
                            position=p_data["pos"],
                            height_cm=p_data["height"],
                            weight_kg=p_data["weight"],
                            birth_date=p_data["birth"],
                            is_active=True,
                        )

                    is_active_season = season.is_current
                    TeamMembership.objects.update_or_create(
                        team=team,
                        player=player,
                        season=season,
                        defaults={
                            "jersey_number": p_data["num"],
                            "is_captain": p_data.get("captain", False),
                            "is_active": is_active_season,
                        }
                    )

        # 6. Generar Partidos y Estadísticas Completas
        self.stdout.write("\n📊 [3/4] Generando partidos y estadísticas completas para todas las jornadas...")

        for (league_slug, season_name), (season, cfg) in created_seasons.items():
            # Limpiar partidos programados previos para garantizar idempotencia exacta
            Match.objects.filter(season=season, status=Match.Status.SCHEDULED).delete()
            season_teams = [all_teams[s] for s in cfg["teams_slugs"] if s in all_teams]
            rng = random.Random(cfg["seed"])
            rounds_pairings = generate_berger_rounds(season_teams, rng=rng)

            total_matches_created = 0
            start_d = season.start_date

            for round_idx, matches_in_round in enumerate(rounds_pairings, start=1):
                match_date = start_d + timedelta(days=(round_idx - 1) * 7)

                for match_idx, (t_home, t_away) in enumerate(matches_in_round):
                    total_matches_created += 1
                    match_time_offset = match_idx % 2
                    actual_match_date = match_date + timedelta(days=match_time_offset)
                    scheduled_dt = timezone.make_aware(
                        timezone.datetime(actual_match_date.year, actual_match_date.month, actual_match_date.day, 18 + match_idx, 30)
                    )

                    # Determinar estado del partido según temporada y jornada
                    if not season.is_current:
                        # Temporadas pasadas (2024/2025 y 2025/2026): TODOS los partidos están FINALIZADOS
                        home_score = rng.randint(76, 96)
                        away_score = rng.randint(72, 92)
                        if home_score == away_score:
                            home_score += rng.choice([2, 3, 5])

                        match, _ = Match.objects.update_or_create(
                            season=season,
                            home_team=t_home,
                            away_team=t_away,
                            round_number=round_idx,
                            defaults={
                                "scheduled_at": scheduled_dt,
                                "location": f"{t_home.arena_name}, {t_home.city}",
                                "status": Match.Status.FINISHED,
                                "current_period": Match.Period.FINISHED,
                                "game_clock": "00:00",
                                "home_score": home_score,
                                "away_score": away_score,
                                "referee": ref1,
                                "second_referee": ref2,
                                "table_official": mesa,
                                "timekeeper": crono,
                            }
                        )

                        DigitalScoreSheet.objects.update_or_create(
                            match=match,
                            defaults={
                                "is_closed": True,
                                "referee_signature": f"{ref1.get_full_name() or ref1.username} (Lic. FEB-48192)" if ref1 else "Juan Carlos García (Lic. FEB-48192)",
                                "second_referee_signature": f"{ref2.get_full_name() or ref2.username} (Lic. FEB-31084)" if ref2 else "Antonio Conde (Lic. FEB-31084)",
                                "table_official_signature": f"{mesa.get_full_name() or mesa.username} (Anotador Oficial)" if mesa else "Carlos Murillo (Anotador)",
                                "timekeeper_signature": f"{crono.get_full_name() or crono.username} (Cronometrador Oficial)" if crono else "Laura Sánchez (Cronometradora)",
                                "incidents_report": "Encuentro oficial concluido conforme al reglamento.",
                                "closed_at": match.scheduled_at + timedelta(hours=2),
                            }
                        )
                        self._populate_match_player_stats(match, t_home, home_score, rng)
                        self._populate_match_player_stats(match, t_away, away_score, rng)
                        generate_match_events_from_stats(match)

                    else:
                        # Temporada actual (2026/2027)
                        if league_slug == "liga-endesa-acb":
                            if round_idx == 1:
                                # J1 Finalizada
                                h_score = 86 if t_home.acronym == "RMB" else 79
                                a_score = 81 if t_home.acronym == "RMB" else 74
                                match, _ = Match.objects.update_or_create(
                                    season=season,
                                    home_team=t_home,
                                    away_team=t_away,
                                    round_number=1,
                                    defaults={
                                        "scheduled_at": timezone.now() - timedelta(days=7),
                                        "location": f"{t_home.arena_name}, {t_home.city}",
                                        "status": Match.Status.FINISHED,
                                        "current_period": Match.Period.FINISHED,
                                        "game_clock": "00:00",
                                        "home_score": h_score,
                                        "away_score": a_score,
                                        "referee": ref1,
                                        "second_referee": ref2,
                                        "table_official": mesa,
                                        "timekeeper": crono,
                                    }
                                )
                                DigitalScoreSheet.objects.update_or_create(
                                    match=match,
                                    defaults={
                                        "is_closed": True,
                                        "referee_signature": "Juan Carlos García (Lic. FEB-48192)",
                                        "table_official_signature": "Carlos Murillo (Anotador)",
                                        "timekeeper_signature": "Laura Sánchez (Cronometradora)",
                                        "closed_at": match.scheduled_at + timedelta(hours=2),
                                    }
                                )
                                self._populate_match_player_stats(match, t_home, h_score, rng)
                                self._populate_match_player_stats(match, t_away, a_score, rng)
                                generate_match_events_from_stats(match)

                            elif round_idx == 2 and t_home.acronym == "RMB" and t_away.acronym == "UNI":
                                # RMB vs UNI: Partido LIVE en juego
                                match, _ = Match.objects.update_or_create(
                                    season=season,
                                    home_team=t_home,
                                    away_team=t_away,
                                    round_number=2,
                                    defaults={
                                        "scheduled_at": timezone.now() - timedelta(hours=1),
                                        "location": f"{t_home.arena_name}, {t_home.city}",
                                        "status": Match.Status.LIVE,
                                        "current_period": Match.Period.Q4,
                                        "game_clock": "09:50",
                                        "home_score": 66,
                                        "away_score": 59,
                                        "referee": ref1,
                                        "second_referee": ref2,
                                        "table_official": mesa,
                                        "timekeeper": crono,
                                    }
                                )
                                self._populate_match_player_stats(match, t_home, 66, rng)
                                self._populate_match_player_stats(match, t_away, 59, rng)
                                generate_match_events_from_stats(match)

                            elif round_idx == 2:
                                # BAR vs VAL: Finalizado
                                match, _ = Match.objects.update_or_create(
                                    season=season,
                                    home_team=t_home,
                                    away_team=t_away,
                                    round_number=2,
                                    defaults={
                                        "scheduled_at": timezone.now() - timedelta(days=1),
                                        "location": f"{t_home.arena_name}, {t_home.city}",
                                        "status": Match.Status.FINISHED,
                                        "current_period": Match.Period.FINISHED,
                                        "game_clock": "00:00",
                                        "home_score": 84,
                                        "away_score": 80,
                                        "referee": ref1,
                                        "second_referee": ref2,
                                        "table_official": mesa,
                                        "timekeeper": crono,
                                    }
                                )
                                DigitalScoreSheet.objects.update_or_create(
                                    match=match,
                                    defaults={
                                        "is_closed": True,
                                        "referee_signature": "Juan Carlos García (Lic. FEB-48192)",
                                        "table_official_signature": "Carlos Murillo (Anotador)",
                                        "timekeeper_signature": "Laura Sánchez (Cronometradora)",
                                        "closed_at": match.scheduled_at + timedelta(hours=2),
                                    }
                                )
                                self._populate_match_player_stats(match, t_home, 84, rng)
                                self._populate_match_player_stats(match, t_away, 80, rng)
                                generate_match_events_from_stats(match)

                            else:
                                # Jornadas 3 a 6: Programadas
                                Match.objects.update_or_create(
                                    season=season,
                                    home_team=t_home,
                                    away_team=t_away,
                                    round_number=round_idx,
                                    defaults={
                                        "scheduled_at": timezone.now() + timedelta(days=round_idx * 7),
                                        "location": f"{t_home.arena_name}, {t_home.city}",
                                        "status": Match.Status.SCHEDULED,
                                        "current_period": Match.Period.NOT_STARTED,
                                        "game_clock": "10:00",
                                        "home_score": 0,
                                        "away_score": 0,
                                        "referee": ref1,
                                        "second_referee": ref2,
                                        "table_official": mesa,
                                        "timekeeper": crono,
                                    }
                                )

                        elif league_slug == "euroleague-basketball":
                            if round_idx in [1, 2]:
                                # J1 y J2 de Euroleague finalizadas
                                h_score = rng.randint(84, 94)
                                a_score = rng.randint(78, 89)
                                match, _ = Match.objects.update_or_create(
                                    season=season,
                                    home_team=t_home,
                                    away_team=t_away,
                                    round_number=round_idx,
                                    defaults={
                                        "scheduled_at": timezone.now() - timedelta(days=(3 - round_idx) * 7),
                                        "location": f"{t_home.arena_name}, {t_home.city}",
                                        "status": Match.Status.FINISHED,
                                        "current_period": Match.Period.FINISHED,
                                        "game_clock": "00:00",
                                        "home_score": h_score,
                                        "away_score": a_score,
                                        "referee": ref1,
                                        "second_referee": ref2,
                                        "table_official": mesa,
                                        "timekeeper": crono,
                                    }
                                )
                                DigitalScoreSheet.objects.update_or_create(
                                    match=match,
                                    defaults={
                                        "is_closed": True,
                                        "referee_signature": "Juan Carlos García (Lic. FEB-48192)",
                                        "table_official_signature": "Carlos Murillo (Anotador)",
                                        "timekeeper_signature": "Laura Sánchez (Cronometradora)",
                                        "closed_at": match.scheduled_at + timedelta(hours=2),
                                    }
                                )
                                self._populate_match_player_stats(match, t_home, h_score, rng)
                                self._populate_match_player_stats(match, t_away, a_score, rng)
                                generate_match_events_from_stats(match)
                            else:
                                # Jornadas 3 a 10: Programadas
                                Match.objects.update_or_create(
                                    season=season,
                                    home_team=t_home,
                                    away_team=t_away,
                                    round_number=round_idx,
                                    defaults={
                                        "scheduled_at": timezone.now() + timedelta(days=round_idx * 7),
                                        "location": f"{t_home.arena_name}, {t_home.city}",
                                        "status": Match.Status.SCHEDULED,
                                        "current_period": Match.Period.NOT_STARTED,
                                        "game_clock": "10:00",
                                        "home_score": 0,
                                        "away_score": 0,
                                        "referee": ref1,
                                        "second_referee": ref2,
                                        "table_official": mesa,
                                        "timekeeper": crono,
                                    }
                                )

            self.stdout.write(f"   ✓ {season.league.name} - {season.name}: {len(rounds_pairings)} jornadas ({total_matches_created} partidos)")

        # 7. Recalcular tablas de clasificación oficiales para todas las temporadas
        self.stdout.write("\n🏆 [4/4] Recalculando tablas de clasificación oficiales (Standings)...")
        for (league_slug, season_name), (season, cfg) in created_seasons.items():
            recalculate_season_standings(season)
            standings_count = Standing.objects.filter(season=season).count()
            self.stdout.write(f"   ✓ {season} -> {standings_count} clubes clasificados")

        self.stdout.write("\n" + "=" * 75)
        self.stdout.write(
            self.style.SUCCESS(
                "🎉 ¡HISTÓRICO DE TEMPORADAS Y CALENDARIOS COMPLETOS GENERADOS CON ÉXITO!\n"
                "✓ Liga Endesa ACB: 4 equipos, 6 jornadas (12 partidos) por temporada.\n"
                "✓ EuroLeague Basketball: 6 equipos, 10 jornadas (30 partidos) por temporada.\n"
                "✓ Temporadas pasadas (2024/2025 y 2025/2026) 100% finalizadas con actas y estadísticas FIBA.\n"
                "✓ Temporada actual (2026/2027) con jornadas disputadas, partido en directo y próximas programadas.\n"
                "✓ Todos los 80 jugadores disponen de estadísticas completas sin huecos en blanco."
            )
        )
        self.stdout.write("=" * 75)

    def _populate_match_player_stats(self, match, team, total_score, rng):
        """
        Asigna estadísticas exactas y ricas a todos los 10 jugadores del equipo para el partido.
        """
        memberships = list(
            TeamMembership.objects.filter(team=team, season=match.season)
            .select_related("player")
            .order_by("jersey_number")
        )
        if not memberships:
            all_mems = list(
                TeamMembership.objects.filter(team=team)
                .select_related("player")
            )
            seen_p = set()
            memberships = []
            for m in all_mems:
                if m.player_id not in seen_p:
                    seen_p.add(m.player_id)
                    memberships.append(m)

        num_players = len(memberships)
        if num_players == 0:
            return

        points_distribution = distribute_team_points(total_score, count=num_players)

        for idx, mem in enumerate(memberships):
            player = mem.player
            pts = points_distribution[idx] if idx < len(points_distribution) else rng.randint(2, 6)

            if idx < 5:
                mins = rng.randint(22, 32)
                reb_off = rng.randint(1, 3)
                reb_def = rng.randint(2, 6)
                ast = rng.randint(2, 7) if player.position in [Player.Position.POINT_GUARD, Player.Position.SHOOTING_GUARD] else rng.randint(1, 3)
                stl = rng.randint(0, 2)
                tov = rng.randint(1, 3)
                blk_m = rng.randint(1, 3) if player.position in [Player.Position.POWER_FORWARD, Player.Position.CENTER] else 0
                blk_r = rng.randint(0, 1)
                f_comm = rng.randint(1, 3)
                f_rec = rng.randint(2, 5)
            else:
                mins = rng.randint(10, 18)
                reb_off = rng.randint(0, 2)
                reb_def = rng.randint(1, 3)
                ast = rng.randint(1, 4) if player.position in [Player.Position.POINT_GUARD, Player.Position.SHOOTING_GUARD] else rng.randint(0, 2)
                stl = rng.randint(0, 1)
                tov = rng.randint(0, 2)
                blk_m = rng.randint(0, 2) if player.position in [Player.Position.POWER_FORWARD, Player.Position.CENTER] else 0
                blk_r = rng.randint(0, 1)
                f_comm = rng.randint(1, 2)
                f_rec = rng.randint(1, 3)

            stat_data = generate_exact_player_stats(
                pts=pts,
                mins=mins,
                reb_off=reb_off,
                reb_def=reb_def,
                ast=ast,
                stl=stl,
                tov=tov,
                blk_m=blk_m,
                blk_r=blk_r,
                f_comm=f_comm,
                f_rec=f_rec,
            )

            stat_obj, _ = PlayerMatchStat.objects.get_or_create(
                match=match,
                player=player,
                defaults={"team": team}
            )
            stat_obj.team = team
            for k, v in stat_data.items():
                setattr(stat_obj, k, v)
            stat_obj.compute_pir()
            stat_obj.save()
