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

    # Guardar / Actualizar registros en Standing
    for team_id, data in stats_by_team.items():
        standing, _ = Standing.objects.get_or_create(
            season=season,
            team=data["team"],
        )
        standing.wins = data["wins"]
        standing.losses = data["losses"]
        standing.points_for = data["points_for"]
        standing.points_against = data["points_against"]
        standing.save()


def get_league_leaders(season=None, limit=5):
    """
    Obtiene los líderes estadísticos individuales (Puntos, Valoración, Asistencias, Rebotes).
    """
    qs = PlayerMatchStat.objects.all()
    if season:
        qs = qs.filter(match__season=season)

    # Agrupado por jugador
    aggregated = (
        qs.values("player__id", "player__first_name", "player__last_name", "player__position", "team__name", "team__acronym", "team__primary_color")
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
    Compara el rendimiento de dos equipos cara a cara y su historial directo.
    """
    matches_h2h = Match.objects.filter(
        Q(home_team=team_a, away_team=team_b) | Q(home_team=team_b, away_team=team_a),
        status=Match.Status.FINISHED
    ).order_by("-scheduled_at")

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

    # Estadísticas globales de la temporada para cada equipo
    standing_a = Standing.objects.filter(team=team_a).first()
    standing_b = Standing.objects.filter(team=team_b).first()

    avg_points_a = (standing_a.points_for / standing_a.games_played) if standing_a and standing_a.games_played > 0 else 0
    avg_points_b = (standing_b.points_for / standing_b.games_played) if standing_b and standing_b.games_played > 0 else 0

    avg_against_a = (standing_a.points_against / standing_a.games_played) if standing_a and standing_a.games_played > 0 else 0
    avg_against_b = (standing_b.points_against / standing_b.games_played) if standing_b and standing_b.games_played > 0 else 0

    return {
        "team_a": team_a,
        "team_b": team_b,
        "matches_h2h": matches_h2h,
        "team_a_h2h_wins": team_a_h2h_wins,
        "team_b_h2h_wins": team_b_h2h_wins,
        "standing_a": standing_a,
        "standing_b": standing_b,
        "avg_points_a": round(avg_points_a, 1),
        "avg_points_b": round(avg_points_b, 1),
        "avg_against_a": round(avg_against_a, 1),
        "avg_against_b": round(avg_against_b, 1),
    }


def compare_players_head_to_head(player_a, player_b):
    """
    Compara las estadísticas medias y métricas biométricas de dos atletas.
    """
    stats_a = PlayerMatchStat.objects.filter(player=player_a).aggregate(
        games=Count("id"),
        avg_pts=Avg("points"),
        avg_pir=Avg("valuation_pir"),
        avg_ast=Avg("assists"),
        avg_reb=Avg(F("rebounds_off") + F("rebounds_def")),
        avg_stl=Avg("steals"),
        avg_3pm=Avg("three_points_made"),
        avg_fg_pct=Avg("field_goals_made"),
    )
    stats_b = PlayerMatchStat.objects.filter(player=player_b).aggregate(
        games=Count("id"),
        avg_pts=Avg("points"),
        avg_pir=Avg("valuation_pir"),
        avg_ast=Avg("assists"),
        avg_reb=Avg(F("rebounds_off") + F("rebounds_def")),
        avg_stl=Avg("steals"),
        avg_3pm=Avg("three_points_made"),
        avg_fg_pct=Avg("field_goals_made"),
    )

    return {
        "player_a": player_a,
        "player_b": player_b,
        "stats_a": {
            "games": stats_a["games"] or 0,
            "pts": round(stats_a["avg_pts"] or 0, 1),
            "pir": round(stats_a["avg_pir"] or 0, 1),
            "ast": round(stats_a["avg_ast"] or 0, 1),
            "reb": round(stats_a["avg_reb"] or 0, 1),
            "stl": round(stats_a["avg_stl"] or 0, 1),
            "t3": round(stats_a["avg_3pm"] or 0, 1),
        },
        "stats_b": {
            "games": stats_b["games"] or 0,
            "pts": round(stats_b["avg_pts"] or 0, 1),
            "pir": round(stats_b["avg_pir"] or 0, 1),
            "ast": round(stats_b["avg_ast"] or 0, 1),
            "reb": round(stats_b["avg_reb"] or 0, 1),
            "stl": round(stats_b["avg_stl"] or 0, 1),
            "t3": round(stats_b["avg_3pm"] or 0, 1),
        },
    }
