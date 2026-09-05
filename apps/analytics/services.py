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

    # Inicializar contadores por equipo
    teams = Team.objects.filter(
        Q(home_matches__season=season) | Q(away_matches__season=season)
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

    # Guardar / Actualizar registros en Standing y purgar obsoletos
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

    # Agrupado por jugador
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

    # Estadísticas globales de la temporada para cada equipo en esta competición
    def _compute_team_stats(team):
        standing_qs = Standing.objects.filter(team=team)
        if season:
            standing_qs = standing_qs.filter(season=season)
        standing = standing_qs.first()

        # Partidos jugados en la competición
        matches_team_qs = Match.objects.filter(
            Q(home_team=team) | Q(away_team=team),
            status=Match.Status.FINISHED
        )
        if season:
            matches_team_qs = matches_team_qs.filter(season=season)
        
        matches_count = matches_team_qs.count()
        games = standing.games_played if (standing and standing.games_played > 0) else matches_count

        # Calcular puntos a favor y en contra si no estuvieran en standing
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

        # Porcentajes de acierto colectivo
        fga = agg["total_fga"] or 0
        fgm = agg["total_fgm"] or 0
        pct_fg = round((fgm / fga * 100), 1) if fga > 0 else 0.0

        t3a = agg["total_t3a"] or 0
        t3m = agg["total_t3m"] or 0
        pct_t3 = round((t3m / t3a * 100), 1) if t3a > 0 else 0.0

        fta = agg["total_fta"] or 0
        ftm = agg["total_ftm"] or 0
        pct_ft = round((ftm / fta * 100), 1) if fta > 0 else 0.0

        return {
            "standing": standing,
            "games": games,
            "wins": standing.wins if standing else 0,
            "losses": standing.losses if standing else 0,
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
            "pct_fg": pct_fg,
            "pct_t3": pct_t3,
            "pct_ft": pct_ft,
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
            "name": "Valoración Media (PIR)",
            "unit": "val",
            "val_a": sa["pir"],
            "val_b": sb["pir"],
            "bar_a": _calc_bars(sa["pir"], sb["pir"])[0],
            "bar_b": _calc_bars(sa["pir"], sb["pir"])[1],
            "leader": "a" if sa["pir"] > sb["pir"] else ("b" if sb["pir"] > sa["pir"] else "equal"),
        },
        {
            "name": "Rebotes por Partido (RPP)",
            "unit": "reb",
            "val_a": sa["reb"],
            "val_b": sb["reb"],
            "bar_a": _calc_bars(sa["reb"], sb["reb"])[0],
            "bar_b": _calc_bars(sa["reb"], sb["reb"])[1],
            "leader": "a" if sa["reb"] > sb["reb"] else ("b" if sb["reb"] > sa["reb"] else "equal"),
        },
        {
            "name": "Asistencias por Partido (APP)",
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

    return {
        "player_a": player_a,
        "player_b": player_b,
        "color_a": color_a,
        "color_b": color_b,
        "stats_a": sa,
        "stats_b": sb,
        "metrics": metrics,
    }
