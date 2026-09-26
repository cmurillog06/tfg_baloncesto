import math
import random
from django.db.models import Sum, Avg, Count, Max, F, Q
from .models import Standing, PlayerMatchStat
from apps.matches.models import Match
from apps.teams.models import Team, Season, Player


def recalculate_season_standings(season):
    """
    Recalcula automáticamente la tabla de clasificación de una temporada
    en base a los partidos que se encuentran en estado FINISHED.
    """
    finished_matches = Match.objects.filter(
        season=season, status=Match.Status.FINISHED
    ).select_related("home_team", "away_team")

    teams = Team.objects.filter(
        Q(home_matches__season=season)
        | Q(away_matches__season=season)
        | Q(standings__season=season)
        | Q(roster_memberships__season=season)
    ).distinct()

    stats_by_team = {
        team.id: {
            "team": team,
            "wins": 0,
            "losses": 0,
            "points_for": 0,
            "points_against": 0,
        }
        for team in teams
    }

    for match in finished_matches:
        home_id = match.home_team_id
        away_id = match.away_team_id

        if home_id not in stats_by_team:
            stats_by_team[home_id] = {
                "team": match.home_team,
                "wins": 0,
                "losses": 0,
                "points_for": 0,
                "points_against": 0,
            }
        if away_id not in stats_by_team:
            stats_by_team[away_id] = {
                "team": match.away_team,
                "wins": 0,
                "losses": 0,
                "points_for": 0,
                "points_against": 0,
            }

        stats_by_team[home_id]["points_for"] += match.home_score
        stats_by_team[home_id]["points_against"] += match.away_score
        stats_by_team[away_id]["points_for"] += match.away_score
        stats_by_team[away_id]["points_against"] += match.home_score

        if match.home_score > match.away_score:
            stats_by_team[home_id]["wins"] += 1
            stats_by_team[away_id]["losses"] += 1
        else:
            stats_by_team[away_id]["wins"] += 1
            stats_by_team[home_id]["losses"] += 1

    valid_team_ids = set()
    for team_id, data in stats_by_team.items():
        valid_team_ids.add(team_id)
        standing, _ = Standing.objects.get_or_create(
            season=season,
            team=data["team"],
        )
        standing.wins = data["wins"]
        standing.losses = data["losses"]
        standing.points_for = data["points_for"]
        standing.points_against = data["points_against"]
        standing.save()

    Standing.objects.filter(season=season).exclude(team_id__in=valid_team_ids).delete()


def get_league_leaders(season=None, limit=5):
    """
    Obtiene los líderes estadísticos individuales (Puntos, Valoración, Asistencias, Rebotes).
    Solo computa partidos finalizados (status=FINISHED) donde el jugador disputó minutos (minutes_played > 0).
    """
    qs = PlayerMatchStat.objects.filter(
        match__status=Match.Status.FINISHED,
        minutes_played__gt=0
    )
    if season:
        qs = qs.filter(match__season=season)

    aggregated = (
        qs.values(
            "player__id",
            "player__first_name",
            "player__last_name",
            "player__position",
            "player__photo",
            "team__name",
            "team__acronym",
            "team__primary_color",
        )
        .annotate(
            games_played=Count("id"),
            total_points=Sum("points"),
            avg_points=Avg("points"),
            total_pir=Sum("valuation_pir"),
            avg_pir=Avg("valuation_pir"),
            total_assists=Sum("assists"),
            avg_assists=Avg("assists"),
            total_rebounds=Sum(F("rebounds_off") + F("rebounds_def")),
            avg_rebounds=Avg(F("rebounds_off") + F("rebounds_def")),
            total_steals=Sum("steals"),
            avg_steals=Avg("steals"),
            total_triples=Sum("three_points_made"),
        )
        .filter(games_played__gt=0)
    )

    top_scorers = list(aggregated.order_by("-avg_points", "-total_points")[:limit])
    top_mvp = list(aggregated.order_by("-avg_pir", "-total_pir")[:limit])
    top_assists = list(aggregated.order_by("-avg_assists", "-total_assists")[:limit])
    top_rebounders = list(aggregated.order_by("-avg_rebounds", "-total_rebounds")[:limit])

    return {
        "top_scorers": top_scorers,
        "top_mvp": top_mvp,
        "top_assists": top_assists,
        "top_rebounders": top_rebounders,
    }


def compare_teams_head_to_head(team_a, team_b, season=None):
    """
    Compara el rendimiento de dos equipos cara a cara y su historial directo en partidos finalizados dentro de una competición.
    """
    matches_h2h = Match.objects.filter(
        Q(home_team=team_a, away_team=team_b) | Q(home_team=team_b, away_team=team_a),
        status=Match.Status.FINISHED
    )
    if season:
        matches_h2h = matches_h2h.filter(season=season)

    matches_h2h = matches_h2h.order_by("-scheduled_at")

    team_a_h2h_wins = 0
    team_b_h2h_wins = 0

    for m in matches_h2h:
        if m.home_team == team_a and m.home_score > m.away_score:
            team_a_h2h_wins += 1
        elif m.away_team == team_a and m.away_score > m.home_score:
            team_a_h2h_wins += 1
        elif m.home_team == team_b and m.home_score > m.away_score:
            team_b_h2h_wins += 1
        elif m.away_team == team_b and m.away_score > m.home_score:
            team_b_h2h_wins += 1

    def _compute_team_stats(team):
        standing_qs = Standing.objects.filter(team=team)
        if season:
            standing_qs = standing_qs.filter(season=season)
        standing = standing_qs.first()

        matches_team_qs = Match.objects.filter(
            Q(home_team=team) | Q(away_team=team),
            status=Match.Status.FINISHED
        )
        if season:
            matches_team_qs = matches_team_qs.filter(season=season)
        
        matches_count = matches_team_qs.count()
        games = standing.games_played if (standing and standing.games_played > 0) else matches_count

        pts_for_calc = 0
        pts_against_calc = 0
        for m in matches_team_qs:
            if m.home_team == team:
                pts_for_calc += m.home_score
                pts_against_calc += m.away_score
            else:
                pts_for_calc += m.away_score
                pts_against_calc += m.home_score

        pts_for = standing.points_for if (standing and standing.points_for > 0) else pts_for_calc
        pts_against = standing.points_against if (standing and standing.points_against > 0) else pts_against_calc

        p_stats_qs = PlayerMatchStat.objects.filter(
            team=team,
            match__status=Match.Status.FINISHED,
            minutes_played__gt=0
        )
        if season:
            p_stats_qs = p_stats_qs.filter(match__season=season)

        agg = p_stats_qs.aggregate(
            total_pts=Sum("points"),
            total_reb_off=Sum("rebounds_off"),
            total_reb_def=Sum("rebounds_def"),
            total_reb=Sum(F("rebounds_off") + F("rebounds_def")),
            total_ast=Sum("assists"),
            total_stl=Sum("steals"),
            total_tov=Sum("turnovers"),
            total_blk=Sum("blocks_made"),
            total_fouls=Sum("fouls_committed"),
            total_fgm=Sum("field_goals_made"),
            total_fga=Sum("field_goals_attempted"),
            total_t3m=Sum("three_points_made"),
            total_t3a=Sum("three_points_attempted"),
            total_ftm=Sum("free_throws_made"),
            total_fta=Sum("free_throws_attempted"),
            total_pir=Sum("valuation_pir"),
        )

        avg_pts = (pts_for / games) if games > 0 else 0
        avg_against = (pts_against / games) if games > 0 else 0
        avg_reb = round(((agg["total_reb"] or 0) / games), 1) if games > 0 else 0
        avg_reb_off = round(((agg["total_reb_off"] or 0) / games), 1) if games > 0 else 0
        avg_reb_def = round(((agg["total_reb_def"] or 0) / games), 1) if games > 0 else 0
        avg_ast = round(((agg["total_ast"] or 0) / games), 1) if games > 0 else 0
        avg_stl = round(((agg["total_stl"] or 0) / games), 1) if games > 0 else 0
        avg_tov = round(((agg["total_tov"] or 0) / games), 1) if games > 0 else 0
        avg_blk = round(((agg["total_blk"] or 0) / games), 1) if games > 0 else 0
        avg_fouls = round(((agg["total_fouls"] or 0) / games), 1) if games > 0 else 0
        avg_t3m = round(((agg["total_t3m"] or 0) / games), 1) if games > 0 else 0
        avg_pir = round(((agg["total_pir"] or 0) / games), 1) if games > 0 else 0

        total_fga = agg["total_fga"] or 0
        total_fgm = agg["total_fgm"] or 0
        total_t3a = agg["total_t3a"] or 0
        total_t3m = agg["total_t3m"] or 0
        total_fta = agg["total_fta"] or 0
        total_ftm = agg["total_ftm"] or 0
        total_orb = agg["total_reb_off"] or 0
        total_tov = agg["total_tov"] or 0

        pct_fg = round((total_fgm / total_fga * 100), 1) if total_fga > 0 else 0.0
        pct_t3 = round((total_t3m / total_t3a * 100), 1) if total_t3a > 0 else 0.0
        pct_ft = round((total_ftm / total_fta * 100), 1) if total_fta > 0 else 0.0

        # Posesiones Oficiales de Oliver: Poss = FGA + 0.44 * FTA - ORB + TOV
        total_poss = max(1.0, float(total_fga + (0.44 * total_fta) - total_orb + total_tov))
        avg_poss = round(total_poss / games, 1) if games > 0 else 75.0

        # Offensive Rating (ORtg) y Defensive Rating (DRtg) por 100 posesiones (Oliver, 2004)
        ortg = round((pts_for / total_poss) * 100.0, 1) if total_poss > 0 else 100.0
        drtg = round((pts_against / total_poss) * 100.0, 1) if total_poss > 0 else 100.0
        net_rating = round(ortg - drtg, 1)

        # Print debug in terminal
        print(f"[DEBUG STATS] {team.name} ({season.name if season else 'all'}): total_fga={total_fga}, total_fta={total_fta}, total_ftm={total_ftm}, total_orb={total_orb}, total_tov={total_tov}, total_poss={total_poss}")

        return {
            "standing": standing,
            "games": games,
            "wins": standing.wins if standing else 0,
            "losses": standing.losses if standing else 0,
            "points_for": pts_for,
            "points_against": pts_against,
            "league_points": standing.league_points if standing else 0,
            "points_diff": standing.points_diff if standing else (pts_for - pts_against),
            "avg_pts": round(avg_pts, 1),
            "avg_against": round(avg_against, 1),
            "avg_reb": avg_reb,
            "avg_reb_off": avg_reb_off,
            "avg_reb_def": avg_reb_def,
            "avg_ast": avg_ast,
            "avg_stl": avg_stl,
            "avg_tov": avg_tov,
            "avg_blk": avg_blk,
            "avg_fouls": avg_fouls,
            "avg_t3m": avg_t3m,
            "avg_pir": avg_pir,
            "total_fga": total_fga,
            "total_fgm": total_fgm,
            "total_t3a": total_t3a,
            "total_t3m": total_t3m,
            "total_fta": total_fta,
            "total_ftm": total_ftm,
            "total_orb": total_orb,
            "total_tov": total_tov,
            "pct_fg": pct_fg,
            "pct_t3": pct_t3,
            "pct_ft": pct_ft,
            "possessions": round(total_poss, 1),
            "pace": avg_poss,
            "ortg": ortg,
            "drtg": drtg,
            "net_rating": net_rating,
        }

    stats_team_a = _compute_team_stats(team_a)
    stats_team_b = _compute_team_stats(team_b)

    return {
        "team_a": team_a,
        "team_b": team_b,
        "season": season,
        "matches_h2h": matches_h2h,
        "team_a_h2h_wins": team_a_h2h_wins,
        "team_b_h2h_wins": team_b_h2h_wins,
        "standing_a": stats_team_a["standing"],
        "standing_b": stats_team_b["standing"],
        "stats_a": stats_team_a,
        "stats_b": stats_team_b,
        "avg_points_a": stats_team_a["avg_pts"],
        "avg_points_b": stats_team_b["avg_pts"],
        "avg_against_a": stats_team_a["avg_against"],
        "avg_against_b": stats_team_b["avg_against"],
    }


def compare_players_head_to_head(player_a, player_b):
    """
    Compara las estadísticas medias de dos atletas en partidos oficiales concluidos.
    """
    stats_a = PlayerMatchStat.objects.filter(
        player=player_a,
        match__status=Match.Status.FINISHED,
        minutes_played__gt=0
    ).aggregate(
        games=Count("id"),
        avg_pts=Avg("points"),
        avg_pir=Avg("valuation_pir"),
        avg_ast=Avg("assists"),
        avg_reb_off=Avg("rebounds_off"),
        avg_reb_def=Avg("rebounds_def"),
        avg_stl=Avg("steals"),
    )
    stats_b = PlayerMatchStat.objects.filter(
        player=player_b,
        match__status=Match.Status.FINISHED,
        minutes_played__gt=0
    ).aggregate(
        games=Count("id"),
        avg_pts=Avg("points"),
        avg_pir=Avg("valuation_pir"),
        avg_ast=Avg("assists"),
        avg_reb_off=Avg("rebounds_off"),
        avg_reb_def=Avg("rebounds_def"),
        avg_stl=Avg("steals"),
    )

    avg_reb_a = round((stats_a["avg_reb_off"] or 0) + (stats_a["avg_reb_def"] or 0), 1)
    avg_reb_b = round((stats_b["avg_reb_off"] or 0) + (stats_b["avg_reb_def"] or 0), 1)

    sa = {
        "games": stats_a["games"] or 0,
        "pts": round(stats_a["avg_pts"] or 0, 1),
        "pir": round(stats_a["avg_pir"] or 0, 1),
        "reb": avg_reb_a,
        "ast": round(stats_a["avg_ast"] or 0, 1),
        "stl": round(stats_a["avg_stl"] or 0, 1),
    }
    sb = {
        "games": stats_b["games"] or 0,
        "pts": round(stats_b["avg_pts"] or 0, 1),
        "pir": round(stats_b["avg_pir"] or 0, 1),
        "reb": avg_reb_b,
        "ast": round(stats_b["avg_ast"] or 0, 1),
        "stl": round(stats_b["avg_stl"] or 0, 1),
    }

    def _calc_bars(val_a, val_b):
        a_pos = max(0.0, float(val_a))
        b_pos = max(0.0, float(val_b))
        total = a_pos + b_pos
        if total <= 0:
            return 50, 50
        pct_a = int(round((a_pos / total) * 100))
        pct_b = 100 - pct_a
        return pct_a, pct_b

    def _get_player_color(player, fallback):
        if player and player.current_team and player.current_team.primary_color:
            c = player.current_team.primary_color.strip()
            if c.lower() not in ["#ffffff", "white", "#fff", ""]:
                return c
        return fallback

    color_a = _get_player_color(player_a, "var(--gold-primary)")
    color_b = _get_player_color(player_b, "var(--state-blue)")
    if color_a == color_b:
        color_a = "var(--gold-primary)"
        color_b = "var(--obsidian-dark)"

    metrics = [
        {
            "name": "Puntos por Partido (PPP)",
            "unit": "pts",
            "val_a": sa["pts"],
            "val_b": sb["pts"],
            "bar_a": _calc_bars(sa["pts"], sb["pts"])[0],
            "bar_b": _calc_bars(sa["pts"], sb["pts"])[1],
            "leader": "a" if sa["pts"] > sb["pts"] else ("b" if sb["pts"] > sa["pts"] else "equal"),
        },
        {
            "name": "Valoración Media Oficial (PIR ACB/FIBA)",
            "unit": "val",
            "val_a": sa["pir"],
            "val_b": sb["pir"],
            "bar_a": _calc_bars(sa["pir"], sb["pir"])[0],
            "bar_b": _calc_bars(sa["pir"], sb["pir"])[1],
            "leader": "a" if sa["pir"] > sb["pir"] else ("b" if sb["pir"] > sa["pir"] else "equal"),
        },
        {
            "name": "Rebotes Totales (REB)",
            "unit": "reb",
            "val_a": sa["reb"],
            "val_b": sb["reb"],
            "bar_a": _calc_bars(sa["reb"], sb["reb"])[0],
            "bar_b": _calc_bars(sa["reb"], sb["reb"])[1],
            "leader": "a" if sa["reb"] > sb["reb"] else ("b" if sb["reb"] > sa["reb"] else "equal"),
        },
        {
            "name": "Asistencias (AST)",
            "unit": "ast",
            "val_a": sa["ast"],
            "val_b": sb["ast"],
            "bar_a": _calc_bars(sa["ast"], sb["ast"])[0],
            "bar_b": _calc_bars(sa["ast"], sb["ast"])[1],
            "leader": "a" if sa["ast"] > sb["ast"] else ("b" if sb["ast"] > sa["ast"] else "equal"),
        },
        {
            "name": "Robos de Balón (ROB)",
            "unit": "rob",
            "val_a": sa["stl"],
            "val_b": sb["stl"],
            "bar_a": _calc_bars(sa["stl"], sb["stl"])[0],
            "bar_b": _calc_bars(sa["stl"], sb["stl"])[1],
            "leader": "a" if sa["stl"] > sb["stl"] else ("b" if sb["stl"] > sa["stl"] else "equal"),
        },
    ]

    superiority_prob = calculate_player_superiority_probability(player_a, player_b)

    return {
        "player_a": player_a,
        "player_b": player_b,
        "color_a": color_a,
        "color_b": color_b,
        "stats_a": sa,
        "stats_b": sb,
        "metrics": metrics,
        "superiority_prob": superiority_prob,
    }


def calculate_player_superiority_probability(player_a, player_b):
    """
    Computa el ratio de rendimiento relativo oficial entre dos atletas a partir
    de su Valoración PIR Media Oficial (FIBA / ACB / Euroliga).
    
    Fórmula Oficial PIR:
    PIR = (PTS + REB + AST + STL + BLK + FC) - (FGA_miss + FTA_miss + TOV + BLK_rec + FD)
    
    Probabilidad Relativa:
    P(A) = (PIR_A / (PIR_A + PIR_B)) * 100
    """
    stats_a = list(
        PlayerMatchStat.objects.filter(
            player=player_a, match__status=Match.Status.FINISHED, minutes_played__gt=0
        ).values_list("valuation_pir", flat=True)
    )
    stats_b = list(
        PlayerMatchStat.objects.filter(
            player=player_b, match__status=Match.Status.FINISHED, minutes_played__gt=0
        ).values_list("valuation_pir", flat=True)
    )

    games_a = len(stats_a)
    games_b = len(stats_b)

    mu_a = sum(stats_a) / games_a if games_a > 0 else 0.0
    mu_b = sum(stats_b) / games_b if games_b > 0 else 0.0

    if games_a == 0 and games_b == 0:
        prob_a_pct = 50.0
        prob_b_pct = 50.0
        simple_explanation = (
            f"Ninguno de los dos jugadores ha disputado minutos todavía en esta temporada para comparar su rendimiento."
        )
    elif games_a > 0 and games_b == 0:
        prob_a_pct = 100.0
        prob_b_pct = 0.0
        simple_explanation = (
            f"{player_a.full_name} promedia {round(mu_a, 1)} de valoración en {games_a} partido(s), "
            f"mientras que {player_b.full_name} todavía no ha jugado partidos en esta temporada."
        )
    elif games_a == 0 and games_b > 0:
        prob_a_pct = 0.0
        prob_b_pct = 100.0
        simple_explanation = (
            f"{player_b.full_name} promedia {round(mu_b, 1)} de valoración en {games_b} partido(s), "
            f"mientras que {player_a.full_name} todavía no ha jugado partidos en esta temporada."
        )
    else:
        mu_a_pos = max(0.0, mu_a)
        mu_b_pos = max(0.0, mu_b)
        tot_mu = mu_a_pos + mu_b_pos

        if tot_mu > 0:
            prob_a_pct = round((mu_a_pos / tot_mu) * 100.0, 1)
            prob_b_pct = round(100.0 - prob_a_pct, 1)
        else:
            prob_a_pct = 50.0
            prob_b_pct = 50.0

        if prob_a_pct > prob_b_pct:
            simple_explanation = (
                f"{player_a.full_name} tiene mejor valoración media ({round(mu_a, 1)} frente a {round(mu_b, 1)} de {player_b.full_name}), "
                f"lo que le da un {prob_a_pct}% de opciones de jugar mejor en este partido frente al {prob_b_pct}% de su rival."
            )
        elif prob_b_pct > prob_a_pct:
            simple_explanation = (
                f"{player_b.full_name} tiene mejor valoración media ({round(mu_b, 1)} frente a {round(mu_a, 1)} de {player_a.full_name}), "
                f"lo que le da un {prob_b_pct}% de opciones de jugar mejor en este partido frente al {prob_a_pct}% de su rival."
            )
        else:
            simple_explanation = (
                f"Ambos jugadores tienen la misma valoración media de {round(mu_a, 1)} puntos en la temporada (50% de probabilidad para cada uno)."
            )

    var_a = (
        sum((x - mu_a) ** 2 for x in stats_a) / len(stats_a)
        if len(stats_a) > 1
        else 0.0
    )
    var_b = (
        sum((x - mu_b) ** 2 for x in stats_b) / len(stats_b)
        if len(stats_b) > 1
        else 0.0
    )

    sigma_a = round(math.sqrt(var_a), 1)
    sigma_b = round(math.sqrt(var_b), 1)

    return {
        "games_a": games_a,
        "games_b": games_b,
        "mu_a": round(mu_a, 1),
        "mu_b": round(mu_b, 1),
        "sigma_a": sigma_a,
        "sigma_b": sigma_b,
        "prob_a_pct": prob_a_pct,
        "prob_b_pct": prob_b_pct,
        "prob_a_css": f"{prob_a_pct:.1f}",
        "prob_b_css": f"{prob_b_pct:.1f}",
        "leader": "a" if prob_a_pct > prob_b_pct else ("b" if prob_b_pct > prob_a_pct else "equal"),
        "simple_explanation": simple_explanation,
    }


def compute_positional_group_metrics(team, season=None):
    """
    Agrupa los jugadores de un club por sus 3 grandes demarcaciones tácticas:
    - Bases (PG - Point Guards)
    - Aleros y Escoltas (SG, SF - Shooting Guards & Small Forwards)
    - Pívots (PF, C - Power Forwards & Centers)
    
    Calcula las métricas oficiales FIBA/ACB por puesto:
    Valoración PIR Media, Puntos, Rebotes, Asistencias y Porcentajes de Tiro.
    
    Referencia: Reglamento Oficial de Estadísticas ACB / FIBA.
    """
    pos_configs = {
        "PG": {
            "name": "Bases",
            "short_name": "Bases",
            "roles": [Player.Position.POINT_GUARD],
            "icon": "🏀",
            "simple_desc": "Dirección de juego, asistencias y ritmo",
        },
        "WING": {
            "name": "Aleros y Escoltas",
            "short_name": "Aleros",
            "roles": [Player.Position.SHOOTING_GUARD, Player.Position.SMALL_FORWARD],
            "icon": "🎯",
            "simple_desc": "Anotación exterior, tiro de tres y penetraciones",
        },
        "BIG": {
            "name": "Pívots",
            "short_name": "Pívots",
            "roles": [Player.Position.POWER_FORWARD, Player.Position.CENTER],
            "icon": "🛡️",
            "simple_desc": "Juego interior, rebotes y protección del aro",
        },
    }

    if season:
        roster_players = Player.objects.filter(
            team_memberships__team=team,
            team_memberships__season=season
        ).distinct()
    else:
        roster_players = Player.objects.filter(
            team_memberships__team=team,
            team_memberships__is_active=True
        ).distinct()

    results = {}

    for group_key, cfg in pos_configs.items():
        players_in_group = roster_players.filter(position__in=cfg["roles"])
        p_ids = list(players_in_group.values_list("id", flat=True))

        p_stats_qs = PlayerMatchStat.objects.filter(
            player_id__in=p_ids,
            team=team,
            match__status=Match.Status.FINISHED,
            minutes_played__gt=0
        )
        if season:
            p_stats_qs = p_stats_qs.filter(match__season=season)

        agg = p_stats_qs.aggregate(
            games=Count("id"),
            avg_min=Avg("minutes_played"),
            avg_pts=Avg("points"),
            avg_ast=Avg("assists"),
            avg_tov=Avg("turnovers"),
            avg_stl=Avg("steals"),
            avg_blk=Avg("blocks_made"),
            avg_reb_off=Avg("rebounds_off"),
            avg_reb_def=Avg("rebounds_def"),
            avg_pir=Avg("valuation_pir"),
            sum_fgm=Sum("field_goals_made"),
            sum_fga=Sum("field_goals_attempted"),
            sum_t3m=Sum("three_points_made"),
            sum_t3a=Sum("three_points_attempted"),
            sum_ftm=Sum("free_throws_made"),
            sum_fta=Sum("free_throws_attempted"),
        )

        games_count = agg["games"] or 0
        avg_pts = round(agg["avg_pts"] or 0.0, 1)
        avg_ast = round(agg["avg_ast"] or 0.0, 1)
        avg_tov = round(agg["avg_tov"] or 0.0, 1)
        avg_stl = round(agg["avg_stl"] or 0.0, 1)
        avg_blk = round(agg["avg_blk"] or 0.0, 1)
        avg_reb_off = round(agg["avg_reb_off"] or 0.0, 1)
        avg_reb_def = round(agg["avg_reb_def"] or 0.0, 1)
        avg_reb = round(avg_reb_off + avg_reb_def, 1)
        avg_pir = round(agg["avg_pir"] or 0.0, 1)

        fga = agg["sum_fga"] or 0
        fgm = agg["sum_fgm"] or 0
        pct_fg = round((fgm / fga * 100), 1) if fga > 0 else 0.0

        t3a = agg["sum_t3a"] or 0
        t3m = agg["sum_t3m"] or 0
        pct_t3 = round((t3m / t3a * 100), 1) if t3a > 0 else 0.0

        # El rating oficial de la posición es su Valoración Media PIR (ACB/FIBA)
        rating = avg_pir

        results[group_key] = {
            "key": group_key,
            "name": cfg["name"],
            "short_name": cfg["short_name"],
            "icon": cfg["icon"],
            "simple_desc": cfg["simple_desc"],
            "players_count": players_in_group.count(),
            "players_list": list(players_in_group.values("id", "first_name", "last_name", "position", "photo")),
            "games_count": games_count,
            "avg_pts": avg_pts,
            "avg_ast": avg_ast,
            "avg_tov": avg_tov,
            "avg_stl": avg_stl,
            "avg_blk": avg_blk,
            "avg_reb": avg_reb,
            "avg_reb_off": avg_reb_off,
            "avg_reb_def": avg_reb_def,
            "avg_pir": avg_pir,
            "pct_fg": pct_fg,
            "pct_t3": pct_t3,
            "rating": rating,
        }

    return results


def predictive_matchup_model(team_a, team_b, season=None, home_court_advantage=3.5):
    """
    Modelo Matemático y Predictivo Oficial para Pronóstico de Partidos.
    
    Integra 3 modelos canónicos y oficiales de la literatura de Sports Analytics:
    
    1. Expectativa Pitagórica del Baloncesto (Daryl Morey 1993, Dean Oliver 2004):
       W = PF^13.91 / (PF^13.91 + PC^13.91)
       Referencia: STATS Scoreboard (1993) & Basketball on Paper (2004, Cap. 4).
       
    2. Posesiones y Ratings de Eficiencia Ofensiva / Defensiva (Dean Oliver 2004):
       Poss = FGA + 0.44 * FTA - ORB + TOV
       ORtg = (PTS / Poss) * 100,  DRtg = (PC / Poss) * 100,  NetRating = ORtg - DRtg
       Referencia: Basketball on Paper (2004, Cap. 3, pp. 27-42).
       
    3. Probabilidad de Victoria por Regresión Logística (Hal Stern 1994, Wayne Winston 2009):
       P(Victoria Local) = 1 / (1 + e^(-0.08 * (NetRating_Local - NetRating_Visitante + HCA)))
       Referencia: JASA 89(427), pp. 1128-1134 (1994) & Mathletics (2009, Cap. 18).
    """
    h2h_data = compare_teams_head_to_head(team_a, team_b, season=season)
    stats_a = h2h_data["stats_a"]
    stats_b = h2h_data["stats_b"]

    pts_for_a = max(1.0, float(stats_a.get("points_for") or (stats_a.get("avg_pts", 80) * max(1, stats_a.get("games", 1)))))
    pts_against_a = max(1.0, float(stats_a.get("points_against") or (stats_a.get("avg_against", 80) * max(1, stats_a.get("games", 1)))))
    pts_for_b = max(1.0, float(stats_b.get("points_for") or (stats_b.get("avg_pts", 80) * max(1, stats_b.get("games", 1)))))
    pts_against_b = max(1.0, float(stats_b.get("points_against") or (stats_b.get("avg_against", 80) * max(1, stats_b.get("games", 1)))))

    # 1. Expectativa Pitagórica Oficial de Daryl Morey (1993, gamma = 13.91)
    def _pythagorean_ratio(pf, pc):
        if pf <= 0 or pc <= 0:
            return 0.5
        ratio = pc / pf
        if ratio > 5.0:
            return 0.001
        if ratio < 0.2:
            return 0.999
        return 1.0 / (1.0 + (ratio ** 13.91))

    pyth_ratio_a = _pythagorean_ratio(pts_for_a, pts_against_a)
    pyth_ratio_b = _pythagorean_ratio(pts_for_b, pts_against_b)

    win_exp_a_pct = round(pyth_ratio_a * 100.0, 1)
    win_exp_b_pct = round(pyth_ratio_b * 100.0, 1)

    pyth_sum = pyth_ratio_a + pyth_ratio_b
    prob_pyth_a_pct = round((pyth_ratio_a / pyth_sum) * 100.0, 1) if pyth_sum > 0 else 50.0
    prob_pyth_b_pct = round(100.0 - prob_pyth_a_pct, 1)

    # 2. Ratings de Eficiencia por 100 posesiones (Dean Oliver, 2004)
    net_rtg_a = float(stats_a.get("net_rating") or 0.0)
    net_rtg_b = float(stats_b.get("net_rating") or 0.0)
    HCA = float(home_court_advantage)

    # Diferencial Neto de Rating con Ventaja de Campo
    delta_net = (net_rtg_a - net_rtg_b) + HCA

    # 3. Probabilidad de Victoria por Regresión Logística Sigmoide (Stern 1994, Winston 2009)
    # P = 1 / (1 + exp(-k * delta)), k = 0.08
    k = 0.08
    z = k * delta_net
    z_clipped = max(-20.0, min(20.0, z))
    prob_win_a = 1.0 / (1.0 + math.exp(-z_clipped))
    prob_win_a_pct = round(prob_win_a * 100.0, 1)
    prob_win_b_pct = round(100.0 - prob_win_a_pct, 1)

    # 4. Marcador Proyectado Oficial (Dean Oliver, 2004)
    # Calculado a partir del ritmo esperado (Pace) y la eficiencia por cada 100 posesiones (ORtg / DRtg):
    pace_a = float(stats_a.get("pace") or 75.0)
    pace_b = float(stats_b.get("pace") or 75.0)
    expected_pace = (pace_a + pace_b) / 2.0 if (pace_a > 0 and pace_b > 0) else 75.0

    ortg_a = float(stats_a.get("ortg") or 105.0)
    drtg_a = float(stats_a.get("drtg") or 105.0)
    ortg_b = float(stats_b.get("ortg") or 105.0)
    drtg_b = float(stats_b.get("drtg") or 105.0)

    # Eficiencia esperada por 100 posesiones incorporando la ventaja de campo (HCA)
    expected_ortg_a = ((ortg_a + drtg_b) / 2.0) + (HCA / 2.0)
    expected_ortg_b = ((ortg_b + drtg_a) / 2.0) - (HCA / 2.0)

    raw_score_a = expected_pace * (expected_ortg_a / 100.0)
    raw_score_b = expected_pace * (expected_ortg_b / 100.0)

    proj_score_a = int(round(raw_score_a))
    proj_score_b = int(round(raw_score_b))

    if proj_score_a == proj_score_b:
        if prob_win_a_pct > 50.0:
            proj_score_a += 1
        elif prob_win_b_pct > 50.0:
            proj_score_b += 1

    # Duelos por Posición Oficiales (PIR FIBA/ACB)
    pos_a = compute_positional_group_metrics(team_a, season=season)
    pos_b = compute_positional_group_metrics(team_b, season=season)

    def _calc_duel(r_a, r_b):
        tot = max(0.1, r_a) + max(0.1, r_b)
        pct_a = round((max(0.1, r_a) / tot) * 100.0, 1)
        pct_b = round(100.0 - pct_a, 1)
        return pct_a, pct_b, round(r_a - r_b, 1)

    pg_pct_a, pg_pct_b, pg_diff = _calc_duel(pos_a["PG"]["rating"], pos_b["PG"]["rating"])
    wing_pct_a, wing_pct_b, wing_diff = _calc_duel(pos_a["WING"]["rating"], pos_b["WING"]["rating"])
    big_pct_a, big_pct_b, big_diff = _calc_duel(pos_a["BIG"]["rating"], pos_b["BIG"]["rating"])

    positional_duels = [
        {
            "key": "PG",
            "name": "Bases",
            "subtitle": "Dirección de juego y asistencias",
            "icon": "🏀",
            "data_a": pos_a["PG"],
            "data_b": pos_b["PG"],
            "pct_a": pg_pct_a,
            "pct_b": pg_pct_b,
            "diff": pg_diff,
            "leader": "a" if pg_diff > 0 else ("b" if pg_diff < 0 else "equal"),
            "why": f"Mayor valoración media de sus bases ({pos_a['PG']['avg_pir']} vs {pos_b['PG']['avg_pir']} puntos de valoración)." if pg_diff != 0 else "Valoración media idéntica en la posición de base.",
        },
        {
            "key": "WING",
            "name": "Aleros y Escoltas",
            "subtitle": "Anotación exterior y tiro de tres",
            "icon": "🎯",
            "data_a": pos_a["WING"],
            "data_b": pos_b["WING"],
            "pct_a": wing_pct_a,
            "pct_b": wing_pct_b,
            "diff": wing_diff,
            "leader": "a" if wing_diff > 0 else ("b" if wing_diff < 0 else "equal"),
            "why": f"Mayor valoración media en el juego exterior ({pos_a['WING']['avg_pir']} vs {pos_b['WING']['avg_pir']} puntos de valoración)." if wing_diff != 0 else "Valoración media idéntica en el juego exterior.",
        },
        {
            "key": "BIG",
            "name": "Pívots",
            "subtitle": "Rebote, defensa y juego interior",
            "icon": "🛡️",
            "data_a": pos_a["BIG"],
            "data_b": pos_b["BIG"],
            "pct_a": big_pct_a,
            "pct_b": big_pct_b,
            "diff": big_diff,
            "leader": "a" if big_diff > 0 else ("b" if big_diff < 0 else "equal"),
            "why": f"Mayor valoración media bajo el aro ({pos_a['BIG']['avg_pir']} vs {pos_b['BIG']['avg_pir']} puntos de valoración)." if big_diff != 0 else "Valoración media idéntica bajo el aro.",
        },
    ]

    # Resumen natural global
    fav_team = team_a if prob_win_a_pct >= prob_win_b_pct else team_b
    fav_pct = prob_win_a_pct if prob_win_a_pct >= prob_win_b_pct else prob_win_b_pct
    underdog_team = team_b if fav_team == team_a else team_a
    underdog_pct = round(100.0 - fav_pct, 1)

    summary_text = (
        f"El favorito para ganar es **{fav_team.name}** con un **{fav_pct}%** de opciones de victoria, "
        f"frente al **{underdog_pct}%** del **{underdog_team.name}**."
    )

    return {
        "team_a": team_a,
        "team_b": team_b,
        "season": season,
        "h2h_data": h2h_data,
        "pos_a": pos_a,
        "pos_b": pos_b,
        "positional_duels": positional_duels,
        "hca": HCA,
        "summary_text": summary_text,
        "fav_team": fav_team,
        "fav_pct": fav_pct,
        "underdog_team": underdog_team,
        "underdog_pct": underdog_pct,
        "pythagorean": {
            "pyth_ratio_a": round(pyth_ratio_a, 4),
            "pyth_ratio_b": round(pyth_ratio_b, 4),
            "win_exp_a_pct": win_exp_a_pct,
            "win_exp_b_pct": win_exp_b_pct,
            "prob_a_pct": win_exp_a_pct,
            "prob_b_pct": win_exp_b_pct,
            "duel_prob_a_pct": prob_pyth_a_pct,
            "duel_prob_b_pct": prob_pyth_b_pct,
        },
        "logistic": {
            "net_rtg_a": net_rtg_a,
            "net_rtg_b": net_rtg_b,
            "delta_net": round(delta_net, 2),
            "z": round(z, 3),
            "prob_a_pct": prob_win_a_pct,
            "prob_b_pct": prob_win_b_pct,
            "prob_a_css": f"{prob_win_a_pct:.1f}",
            "prob_b_css": f"{prob_win_b_pct:.1f}",
        },
        "projected_score": {
            "score_a": int(proj_score_a),
            "score_b": int(proj_score_b),
            "winner": "a" if proj_score_a > proj_score_b else ("b" if proj_score_b > proj_score_a else "tie"),
            "margin": abs(int(proj_score_a) - int(proj_score_b)),
            "pace_a": round(pace_a, 1),
            "pace_b": round(pace_b, 1),
            "expected_pace": round(expected_pace, 1),
            "ortg_a": ortg_a,
            "drtg_a": drtg_a,
            "ortg_b": ortg_b,
            "drtg_b": drtg_b,
            "expected_ortg_a": round(expected_ortg_a, 1),
            "expected_ortg_b": round(expected_ortg_b, 1),
        },
    }
