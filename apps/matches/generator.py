"""
Módulo de Generación Aleatoria de Calendario Deportivo, Sedes y Designaciones Oficiales.
Implementa el algoritmo canónico de Round-Robin (Tablas de Berger) con rotación equilibrada
de localías, asignación de pabellones y designación equitativa de árbitros y mesa arbitral.
"""

import random
from datetime import datetime, timedelta, time
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model

from apps.teams.models import Team, Season
from apps.matches.models import Match
from apps.analytics.models import Standing

User = get_user_model()


def get_season_teams(season):
    """
    Obtiene los equipos adscritos a una temporada determinada.
    Prioriza las clasificaciones (Standing), luego partidos existentes, y finalmente todos los equipos activos.
    """
    teams = list(
        Team.objects.filter(standings__season=season).distinct().order_by("name")
    )
    if not teams:
        teams = list(
            Team.objects.filter(
                models_Q_matches(season)
            ).distinct().order_by("name")
        )
    if not teams:
        teams = list(Team.objects.all().order_by("name"))
    return teams


def models_Q_matches(season):
    from django.db.models import Q
    return Q(home_matches__season=season) | Q(away_matches__season=season)


def build_round_robin_matchups(teams, double_round=True):
    """
    Genera la estructura de jornadas y emparejamientos utilizando las Tablas Canónicas de Berger.
    Garantiza un balance perfecto de localías (máxima diferencia de 1 partido local/visitante
    en ligas a una vuelta y paridad exacta del 50% en ligas a doble vuelta).
    
    Retorna una lista de jornadas, donde cada jornada es una lista de tuplas (home_team, away_team).
    """
    team_list = list(teams)
    random.shuffle(team_list)

    # Si el número de equipos es impar, se añade un elemento ficticio 'None' para descansos
    if len(team_list) % 2 != 0:
        team_list.append(None)

    n = len(team_list)
    rounds_count = n - 1
    mod = n - 1

    first_leg_rounds = []

    for r in range(rounds_count):
        round_matches = []

        # 1. Emparejamiento del equipo fijo (índice n - 1) con el equipo del ciclo r
        fixed_opponent_idx = r
        if r % 2 == 0:
            home_idx, away_idx = fixed_opponent_idx, n - 1
        else:
            home_idx, away_idx = n - 1, fixed_opponent_idx

        t_home = team_list[home_idx]
        t_away = team_list[away_idx]
        if t_home is not None and t_away is not None:
            round_matches.append((t_home, t_away))

        # 2. Resto de emparejamientos del ciclo para esta jornada
        for k in range(1, n // 2):
            t1_idx = (r - k) % mod
            t2_idx = (r + k) % mod

            if k % 2 == 1:
                home_idx, away_idx = t1_idx, t2_idx
            else:
                home_idx, away_idx = t2_idx, t1_idx

            t_home = team_list[home_idx]
            t_away = team_list[away_idx]
            if t_home is not None and t_away is not None:
                round_matches.append((t_home, t_away))

        first_leg_rounds.append(round_matches)

    all_rounds = list(first_leg_rounds)

    # Si es a doble vuelta (ida y vuelta), la segunda vuelta invierte local/visitante de forma simétrica
    if double_round:
        for r_matches in first_leg_rounds:
            second_leg_matches = [(away, home) for home, away in r_matches]
            all_rounds.append(second_leg_matches)

    return all_rounds


def generate_season_schedule(
    season,
    double_round=True,
    start_date=None,
    round_interval_days=7,
    time_slots=None,
    weekend_spread=True,
    assign_officials=True,
    clear_existing=True,
    dry_run=False,
):
    """
    Genera y guarda (o previsualiza) el calendario oficial de partidos para una temporada.

    Parámetros:
    - season: Instancia de Season
    - double_round: True para Ida y Vuelta (doble vuelta), False para Solo Ida
    - start_date: Fecha inicial del calendario (datetime.date o datetime.datetime)
    - round_interval_days: Días entre jornadas consecutivas (defecto: 7 días / semanal)
    - time_slots: Lista de strings con horas ("12:30", "17:00", "18:30", "20:45")
    - weekend_spread: Si es True, divide los partidos de cada jornada entre sábado y domingo
    - assign_officials: Si es True, designa árbitros, anotadores y cronometradores
    - clear_existing: Si es True, elimina partidos previos en estado SCHEDULED de la temporada
    - dry_run: Si es True, no persiste en la base de datos y solo retorna la previsualización

    Retorna un diccionario con estadísticas y lista detallada de partidos generados.
    """
    teams = get_season_teams(season)
    if len(teams) < 2:
        raise ValueError(f"La temporada '{season.name}' necesita al menos 2 equipos para confeccionar un calendario.")

    if not time_slots:
        time_slots = ["12:30", "17:00", "18:30", "20:45"]

    # Determinar fecha inicial consistente para toda la competición
    now = timezone.now()
    today = now.date()

    if start_date is None:
        # Próximo sábado a partir de hoy
        days_ahead = (5 - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        current_date = today + timedelta(days=days_ahead)
    elif isinstance(start_date, datetime):
        current_date = start_date.date()
    else:
        current_date = start_date

    # Si la fecha elegida es anterior a hoy, ajustar al día siguiente
    if current_date < today:
        current_date = today + timedelta(days=1)
    elif current_date == today:
        # Si es hoy, comprobar si la primera franja horaria ya transcurrió para comenzar mañana
        first_slot = time_slots[0] if time_slots else "12:30"
        try:
            sh, sm = map(int, first_slot.split(":"))
        except Exception:
            sh, sm = 12, 30
        if now.time() >= time(sh, sm):
            current_date = today + timedelta(days=1)

    # Obtener personal arbitral
    referees = list(User.objects.filter(role=User.Role.REFEREE, is_active=True))
    table_officials = list(User.objects.filter(role=User.Role.TABLE_OFFICIAL, is_active=True))

    # Si no hay usuarios con rol REFEREE, buscar administradores o staff como fallback
    if not referees:
        referees = list(User.objects.filter(is_staff=True, is_active=True))
    if not table_officials:
        table_officials = list(User.objects.filter(is_staff=True, is_active=True))

    round_matchups = build_round_robin_matchups(teams, double_round=double_round)

    created_matches_data = []
    matches_to_create = []

    ref_idx = 0
    to_idx = 0

    with transaction.atomic():
        if not dry_run and clear_existing:
            # Eliminar partidos programados previamente que no hayan comenzado
            Match.objects.filter(season=season, status=Match.Status.SCHEDULED).delete()

        for round_idx, round_pairs in enumerate(round_matchups, start=1):
            # Fecha base uniforme para esta jornada
            round_date = current_date + timedelta(days=(round_idx - 1) * round_interval_days)

            # Distribuir partidos en la jornada de forma cronológica ordenada
            for match_in_round_idx, (home_team, away_team) in enumerate(round_pairs):
                # Si weekend_spread está activo, repartir la mitad el sábado (offset 0) y la otra el domingo (offset 1)
                if weekend_spread and len(round_pairs) > 1:
                    day_offset = 0 if (match_in_round_idx < (len(round_pairs) + 1) // 2) else 1
                else:
                    day_offset = 0

                match_date = round_date + timedelta(days=day_offset)

                # Franja horaria correspondiente
                slot_str = time_slots[match_in_round_idx % len(time_slots)]
                try:
                    slot_h, slot_m = map(int, slot_str.split(":"))
                except Exception:
                    slot_h, slot_m = 18, 0

                match_naive = datetime.combine(match_date, time(slot_h, slot_m))
                match_dt = timezone.make_aware(match_naive, timezone.get_current_timezone())

                # Pabellón de la sede local
                arena = (
                    home_team.arena_name
                    or (f"Pabellón Municipal de {home_team.city}" if home_team.city else f"Pabellón {home_team.name}")
                )

                # Designación arbitral (2 árbitros: Principal y Auxiliar) y oficiales de mesa (Anotador y Cronometrador)
                assigned_ref1 = None
                assigned_ref2 = None
                assigned_to = None
                assigned_tk = None

                if assign_officials and referees:
                    assigned_ref1 = referees[ref_idx % len(referees)]
                    ref_idx += 1

                    if len(referees) > 1:
                        assigned_ref2 = referees[ref_idx % len(referees)]
                        ref_idx += 1
                    else:
                        assigned_ref2 = assigned_ref1

                if assign_officials and table_officials:
                    assigned_to = table_officials[to_idx % len(table_officials)]
                    to_idx += 1

                    if len(table_officials) > 1:
                        assigned_tk = table_officials[to_idx % len(table_officials)]
                        to_idx += 1
                    else:
                        assigned_tk = assigned_to

                match_obj = Match(
                    season=season,
                    round_number=round_idx,
                    home_team=home_team,
                    away_team=away_team,
                    scheduled_at=match_dt,
                    location=arena,
                    referee=assigned_ref1,
                    second_referee=assigned_ref2,
                    table_official=assigned_to,
                    timekeeper=assigned_tk,
                    status=Match.Status.SCHEDULED,
                    current_period=Match.Period.NOT_STARTED,
                    game_clock="10:00",
                    home_score=0,
                    away_score=0,
                )

                if not dry_run:
                    match_obj.save()

                created_matches_data.append({
                    "round_number": round_idx,
                    "home_team": home_team,
                    "away_team": away_team,
                    "scheduled_at": match_dt,
                    "location": arena,
                    "referee": assigned_ref1,
                    "second_referee": assigned_ref2,
                    "table_official": assigned_to,
                    "timekeeper": assigned_tk,
                })

    # Asegurar orden estrictamente cronológico por jornada y fecha/hora
    created_matches_data.sort(key=lambda m: (m["round_number"], m["scheduled_at"]))

    return {
        "season": season,
        "total_teams": len(teams),
        "total_rounds": len(round_matchups),
        "total_matches": len(created_matches_data),
        "double_round": double_round,
        "start_date": current_date,
        "matches": created_matches_data,
        "dry_run": dry_run,
    }
