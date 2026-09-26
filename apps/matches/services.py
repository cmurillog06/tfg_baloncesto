import random
from apps.matches.models import Match, MatchEvent, DigitalScoreSheet
from apps.teams.models import Team, Season, TeamMembership
from apps.analytics.models import PlayerMatchStat
from apps.analytics.services import recalculate_season_standings
from apps.teams.management.commands.seed_full_rosters import (
    distribute_team_points,
    generate_exact_player_stats,
    generate_match_events_from_stats,
)


CANONICAL_MATCH_SCORES = [
    # (Home Acronym, Away Acronym, Round, Status, Period, Clock, Home Score, Away Score)
    # EuroLeague
    ("OLY", "ASM", 2, Match.Status.FINISHED, Match.Period.FINISHED, "00:00", 86, 82),
    ("PAO", "OLY", 1, Match.Status.FINISHED, Match.Period.FINISHED, "00:00", 88, 85),
    ("FNB", "ASM", 1, Match.Status.FINISHED, Match.Period.FINISHED, "00:00", 91, 84),
    ("PAO", "FNB", 2, Match.Status.FINISHED, Match.Period.FINISHED, "00:00", 94, 89),
    ("ASM", "PAO", 3, Match.Status.SCHEDULED, Match.Period.NOT_STARTED, "10:00", 0, 0),
    # Liga Endesa ACB
    ("RMB", "BAR", 1, Match.Status.FINISHED, Match.Period.FINISHED, "00:00", 86, 81),
    ("UNI", "VAL", 1, Match.Status.FINISHED, Match.Period.FINISHED, "00:00", 79, 74),
    ("RMB", "UNI", 2, Match.Status.LIVE, Match.Period.Q4, "09:50", 66, 59),
    ("BAR", "VAL", 2, Match.Status.SCHEDULED, Match.Period.NOT_STARTED, "10:00", 0, 0),
]


def restore_canonical_matches():
    """
    Restaura todos los marcadores, periodos, relojes, estadísticas individuales y jugadas
    de los partidos al estado canónico oficial.
    """
    canonical_match_ids = []
    for home_acr, away_acr, round_num, status, period, clock, h_score, a_score in CANONICAL_MATCH_SCORES:
        matches = Match.objects.filter(
            season__is_current=True,
            home_team__acronym=home_acr,
            away_team__acronym=away_acr,
            round_number=round_num,
        )
        if not matches.exists():
            # Intentar búsqueda con acrónimos alternativos (por ejemplo FCB / BAR, VAL / VBC)
            matches = Match.objects.filter(
                season__is_current=True,
                home_team__acronym__in=[home_acr, f"{home_acr}C", "FCB" if home_acr == "BAR" else home_acr],
                away_team__acronym__in=[away_acr, f"{away_acr}C", "FCB" if away_acr == "BAR" else away_acr],
                round_number=round_num,
            )

        from django.contrib.auth import get_user_model
        User = get_user_model()
        mesa = User.objects.filter(username="oficial_mesa").first()
        crono = User.objects.filter(username="cronometrador").first()
        ref1 = User.objects.filter(username="arbitro_principal").first()
        ref2 = User.objects.filter(username="arbitro_fiba").first()

        for match in matches:
            canonical_match_ids.append(match.id)
            needs_stat_regen = (
                match.home_score != h_score
                or match.away_score != a_score
                or match.status != status
            )

            match.home_score = h_score
            match.away_score = a_score
            match.status = status
            match.current_period = period
            match.game_clock = clock
            if not match.referee and ref1:
                match.referee = ref1
            if not match.second_referee and ref2:
                match.second_referee = ref2
            if not match.table_official and mesa:
                match.table_official = mesa
            if not match.timekeeper and crono:
                match.timekeeper = crono
            match.save()

            if status == Match.Status.FINISHED:
                scoresheet, _ = DigitalScoreSheet.objects.get_or_create(match=match)
                scoresheet.is_closed = True
                if not scoresheet.referee_signature:
                    scoresheet.referee_signature = (
                        f"{match.referee.get_full_name() or match.referee.username} (Lic. FEB-48192)"
                        if match.referee else "Juan Carlos García González (Lic. FEB-48192)"
                    )
                if not scoresheet.second_referee_signature:
                    scoresheet.second_referee_signature = (
                        f"{match.second_referee.get_full_name() or match.second_referee.username} (Lic. FEB-31084)"
                        if match.second_referee else "Antonio Conde Ruiz (Lic. FEB-31084)"
                    )
                if not scoresheet.table_official_signature:
                    scoresheet.table_official_signature = (
                        match.table_official.get_full_name() or match.table_official.username
                        if match.table_official else "Carlos Murillo (Anotador)"
                    )
                if not scoresheet.timekeeper_signature:
                    scoresheet.timekeeper_signature = (
                        match.timekeeper.get_full_name() or match.timekeeper.username
                        if match.timekeeper else "Laura Gómez (Cronometradora)"
                    )
                scoresheet.save()

            if status == Match.Status.SCHEDULED:
                PlayerMatchStat.objects.filter(match=match).delete()
                MatchEvent.objects.filter(match=match).delete()
                DigitalScoreSheet.objects.filter(match=match).delete()
                continue

            # Regenerar estadísticas individuales y eventos si los puntos cambiaron o no coinciden exactamente
            home_stats = PlayerMatchStat.objects.filter(match=match, team=match.home_team)
            away_stats = PlayerMatchStat.objects.filter(match=match, team=match.away_team)
            home_pts_sum = sum(s.points for s in home_stats)
            away_pts_sum = sum(s.points for s in away_stats)

            if needs_stat_regen or home_pts_sum != h_score or away_pts_sum != a_score or not home_stats.exists():
                PlayerMatchStat.objects.filter(match=match).delete()
                seen_player_ids = set()

                # Local Box Score
                home_memberships = list(TeamMembership.objects.filter(team=match.home_team, season=match.season, is_active=True)[:8])
                if not home_memberships:
                    home_memberships = list(TeamMembership.objects.filter(team=match.home_team, is_active=True)[:8])

                home_points_dist = distribute_team_points(h_score, len(home_memberships))

                for idx, m in enumerate(home_memberships):
                    if m.player_id in seen_player_ids:
                        continue
                    seen_player_ids.add(m.player_id)
                    p_pts = home_points_dist[idx] if idx < len(home_points_dist) else 8
                    p_mins = random.randint(14, 34) if status == Match.Status.FINISHED else random.randint(8, 23)
                    stat_dict = generate_exact_player_stats(
                        pts=p_pts,
                        mins=p_mins,
                        reb_off=random.randint(0, 3),
                        reb_def=random.randint(1, 6),
                        ast=random.randint(1, 8),
                        stl=random.randint(0, 3),
                        tov=random.randint(0, 3),
                        blk_m=random.randint(0, 2),
                        blk_r=random.randint(0, 1),
                        f_comm=random.randint(1, 4),
                        f_rec=random.randint(1, 5),
                    )
                    PlayerMatchStat.objects.create(
                        match=match,
                        player=m.player,
                        team=match.home_team,
                        **stat_dict,
                    )

                # Visitante Box Score
                away_memberships = list(TeamMembership.objects.filter(team=match.away_team, season=match.season, is_active=True)[:8])
                if not away_memberships:
                    away_memberships = list(TeamMembership.objects.filter(team=match.away_team, is_active=True)[:8])

                away_points_dist = distribute_team_points(a_score, len(away_memberships))

                for idx, m in enumerate(away_memberships):
                    if m.player_id in seen_player_ids:
                        continue
                    seen_player_ids.add(m.player_id)
                    p_pts = away_points_dist[idx] if idx < len(away_points_dist) else 8
                    p_mins = random.randint(12, 32) if status == Match.Status.FINISHED else random.randint(8, 23)
                    stat_dict = generate_exact_player_stats(
                        pts=p_pts,
                        mins=p_mins,
                        reb_off=random.randint(0, 3),
                        reb_def=random.randint(1, 5),
                        ast=random.randint(0, 7),
                        stl=random.randint(0, 2),
                        tov=random.randint(0, 3),
                        blk_m=random.randint(0, 1),
                        blk_r=random.randint(0, 1),
                        f_comm=random.randint(1, 4),
                        f_rec=random.randint(1, 4),
                    )
                    PlayerMatchStat.objects.create(
                        match=match,
                        player=m.player,
                        team=match.away_team,
                        **stat_dict,
                    )

                # Generar eventos jugada a jugada acordes
                generate_match_events_from_stats(match)

    # Eliminar cualquier partido de prueba no canónico creado durante tests en la temporada actual
    if canonical_match_ids:
        Match.objects.filter(season__is_current=True).exclude(id__in=canonical_match_ids).delete()

    # Recalcular clasificaciones de todas las temporadas
    for season in Season.objects.all():
        recalculate_season_standings(season)

