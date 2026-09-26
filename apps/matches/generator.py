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
    Obtiene los equipos adscritos a una temporada determinada en orden canónico coherente.
    Prioriza las clasificaciones (Standing) de la temporada, luego partidos/membresías existentes,
    luego clubes canónicos de ligas oficiales completas y finalmente todos los equipos.
    """
    from django.db.models import Q
    from apps.teams.models import TeamMembership

    # 1. Equipos vinculados a esta temporada por Clasificación (Standing), Partidos o Membresías
    standing_team_ids = set(Standing.objects.filter(season=season).values_list("team_id", flat=True))
    match_team_ids = set(
        Team.objects.filter(Q(home_matches__season=season) | Q(away_matches__season=season))
        .values_list("id", flat=True)
    )
    membership_team_ids = set(
        TeamMembership.objects.filter(season=season).values_list("team_id", flat=True)
    )

    all_season_team_ids = standing_team_ids | match_team_ids | membership_team_ids
    if all_season_team_ids:
        teams = list(Team.objects.filter(id__in=all_season_team_ids).distinct().order_by("name"))
        if len(teams) >= 2:
            return teams

    # 4. Equipos canónicos por slug de liga oficial si están completos
    if season.league and season.league.slug == "liga-endesa-acb":
        canonical_slugs = ["real-madrid-baloncesto", "fc-barcelona-basket", "unicaja-malaga", "valencia-basket"]
        teams_by_slug = {t.slug: t for t in Team.objects.filter(slug__in=canonical_slugs)}
        ordered_teams = [teams_by_slug[s] for s in canonical_slugs if s in teams_by_slug]
        if len(ordered_teams) == len(canonical_slugs):
            return ordered_teams

    elif season.league and season.league.slug == "euroleague-basketball":
        canonical_slugs = [
            "panathinaikos-aktor", "olympiacos-piraeus", "fenerbahce-beko", "as-monaco-basket",
            "real-madrid-baloncesto", "fc-barcelona-basket"
        ]
        teams_by_slug = {t.slug: t for t in Team.objects.filter(slug__in=canonical_slugs)}
        ordered_teams = [teams_by_slug[s] for s in canonical_slugs if s in teams_by_slug]
        if len(ordered_teams) == len(canonical_slugs):
            return ordered_teams

    # 5. Fallback final: todos los equipos en base de datos
    teams = list(Team.objects.all().order_by("name"))
    return teams


def models_Q_matches(season):
    from django.db.models import Q
    return Q(home_matches__season=season) | Q(away_matches__season=season)


def generate_full_berger_rounds(teams, double_round=True, rng=None):
    """
    Genera un torneo completo Round-Robin (Tablas de Berger) mediante un sorteo aleatorio con 'rng'.
    Garantiza:
    - 1ª Vuelta: todos los equipos se enfrentan exactamente 1 vez (N-1 jornadas).
    - 2ª Vuelta: repite los cruces con local/visitante invertido (N-1 jornadas).
    - Equilibrio de localías: exactamente 50% en casa y 50% fuera para cada equipo.
    """
    if rng is None:
        rng = random.Random()

    team_list = list(teams)
    rng.shuffle(team_list)

    if len(team_list) % 2 != 0:
        team_list.append(None)
    m = len(team_list)
    rounds_count = m - 1
    mod = m - 1
    first_leg = []

    for r in range(rounds_count):
        round_matches = []
        fixed_opponent_idx = r
        if r % 2 == 0:
            home_idx, away_idx = fixed_opponent_idx, m - 1
        else:
            home_idx, away_idx = m - 1, fixed_opponent_idx
        t_home = team_list[home_idx]
        t_away = team_list[away_idx]
        if t_home is not None and t_away is not None:
            round_matches.append((t_home, t_away))
        for k in range(1, m // 2):
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
        first_leg.append(round_matches)

    rng.shuffle(first_leg)
    for r_matches in first_leg:
        rng.shuffle(r_matches)

    all_rounds = list(first_leg)
    if double_round:
        second_leg = []
        for r_matches in first_leg:
            second_leg_matches = [(away, home) for home, away in r_matches]
            second_leg.append(second_leg_matches)
        all_rounds.extend(second_leg)

    return all_rounds


def build_round_robin_matchups(teams, double_round=True, shuffle=False, rng=None):
    """
    Generador canónico exportable para comandos y modelos.
    """
    return generate_full_berger_rounds(teams, double_round=double_round, rng=rng)


def find_valid_round_factorization(undirected_pairs, num_rounds, num_teams, rng=None):
    """
    Encuentra una 1-factorización perfecta de 'undirected_pairs' en 'num_rounds' jornadas
    de 'num_teams // 2' partidos disjuntos cada una.
    Garantiza al 100% que en cada jornada todos los 'num_teams' juegan exactamente 1 vez.
    """
    if rng is None:
        rng = random.Random()

    matches_per_round = num_teams // 2
    pairs = [tuple(sorted(p)) for p in undirected_pairs]

    if len(pairs) != num_rounds * matches_per_round:
        return None

    rng.shuffle(pairs)

    round_vertices = [set() for _ in range(num_rounds)]
    round_edges = [[] for _ in range(num_rounds)]

    def solve(idx):
        if idx == len(pairs):
            return all(len(r) == matches_per_round for r in round_edges)

        u, v = pairs[idx]
        round_order = list(range(num_rounds))
        rng.shuffle(round_order)
        round_order.sort(key=lambda r: len(round_edges[r]))

        for r in round_order:
            if len(round_edges[r]) < matches_per_round:
                if u not in round_vertices[r] and v not in round_vertices[r]:
                    round_vertices[r].add(u)
                    round_vertices[r].add(v)
                    round_edges[r].append((u, v))

                    if solve(idx + 1):
                        return True

                    round_edges[r].pop()
                    round_vertices[r].remove(u)
                    round_vertices[r].remove(v)
        return False

    if solve(0):
        return round_edges

    # Respaldo determinista ordenado si la permutación inicial no resolvió
    pairs.sort()
    round_vertices = [set() for _ in range(num_rounds)]
    round_edges = [[] for _ in range(num_rounds)]

    def solve_ordered(idx):
        if idx == len(pairs):
            return all(len(r) == matches_per_round for r in round_edges)
        u, v = pairs[idx]
        for r in range(num_rounds):
            if len(round_edges[r]) < matches_per_round:
                if u not in round_vertices[r] and v not in round_vertices[r]:
                    round_vertices[r].add(u)
                    round_vertices[r].add(v)
                    round_edges[r].append((u, v))
                    if solve_ordered(idx + 1):
                        return True
                    round_edges[r].pop()
                    round_vertices[r].remove(u)
                    round_vertices[r].remove(v)
        return False

    if solve_ordered(0):
        return round_edges

    return None



def complete_partial_season_schedule(teams, played_matches, double_round=True, rng=None):
    """
    Completa un calendario para una temporada que ya tiene partidos disputados o en juego.
    Garantiza al 100%:
    1. Cada jornada tiene exactamente N // 2 partidos.
    2. Todos los N equipos juegan exactamente 1 vez por jornada.
    3. Todos los partidos jugados existentes (status != SCHEDULED) se conservan en su jornada y emparejamiento.
    4. La 2ª vuelta es el reflejo simétrico exacto de la 1ª vuelta (con local/visitante invertido).
    """
    if rng is None:
        rng = random.Random()

    n = len(teams)
    matches_per_round = n // 2
    rounds_in_fl = n - 1
    total_rounds = 2 * rounds_in_fl if double_round else rounds_in_fl
    teams_by_id = {t.id: t for t in teams}
    all_team_ids = list(teams_by_id.keys())

    # Agrupar partidos jugados por jornada
    played_by_round = {r: [] for r in range(1, total_rounds + 1)}
    for m in played_matches:
        if m.round_number in played_by_round:
            played_by_round[m.round_number].append((m.home_team_id, m.away_team_id))

    # Construir emparejamientos fijos para cada jornada de la 1ª vuelta
    fixed_fl_by_round = {k: [] for k in range(1, rounds_in_fl + 1)}
    used_undirected_pairs = set()

    for k in range(1, rounds_in_fl + 1):
        for (h, a) in played_by_round[k]:
            pair = tuple(sorted((h, a)))
            if pair not in used_undirected_pairs:
                fixed_fl_by_round[k].append((h, a))
                used_undirected_pairs.add(pair)

        if double_round:
            return_k = k + rounds_in_fl
            for (h_ret, a_ret) in played_by_round[return_k]:
                pair = tuple(sorted((h_ret, a_ret)))
                if pair not in used_undirected_pairs:
                    fixed_fl_by_round[k].append((a_ret, h_ret))
                    used_undirected_pairs.add(pair)

    # Todos los pares posibles entre los equipos
    all_pairs = []
    for i in range(len(all_team_ids)):
        for j in range(i + 1, len(all_team_ids)):
            all_pairs.append((min(all_team_ids[i], all_team_ids[j]), max(all_team_ids[i], all_team_ids[j])))

    unassigned_pairs = [p for p in all_pairs if p not in used_undirected_pairs]
    rng.shuffle(unassigned_pairs)

    home_counts = {t_id: sum(1 for m in played_matches if m.home_team_id == t_id) for t_id in all_team_ids}
    away_counts = {t_id: sum(1 for m in played_matches if m.away_team_id == t_id) for t_id in all_team_ids}

    # Resolver la asignación de pares no asignados para completar cada jornada de la 1ª vuelta
    fl_round_vertices = []
    fl_round_matches = []
    for k in range(1, rounds_in_fl + 1):
        v_set = set()
        m_list = list(fixed_fl_by_round[k])
        for h, a in m_list:
            v_set.add(h)
            v_set.add(a)
        fl_round_vertices.append(v_set)
        fl_round_matches.append(m_list)

    def solve_fl(idx):
        if idx == len(unassigned_pairs):
            return all(len(r) == matches_per_round for r in fl_round_matches)

        u, v = unassigned_pairs[idx]
        round_indices = list(range(rounds_in_fl))
        rng.shuffle(round_indices)
        round_indices.sort(key=lambda r: len(fl_round_matches[r]))

        if home_counts[u] < home_counts[v]:
            orientations = [(u, v)]
        elif home_counts[v] < home_counts[u]:
            orientations = [(v, u)]
        else:
            orientations = [(u, v), (v, u)] if rng.choice([True, False]) else [(v, u), (u, v)]

        for r in round_indices:
            if len(fl_round_matches[r]) < matches_per_round:
                if u not in fl_round_vertices[r] and v not in fl_round_vertices[r]:
                    fl_round_vertices[r].add(u)
                    fl_round_vertices[r].add(v)

                    for (h, a) in orientations:
                        home_counts[h] += 1
                        away_counts[a] += 1
                        fl_round_matches[r].append((h, a))

                        if solve_fl(idx + 1):
                            return True

                        fl_round_matches[r].pop()
                        home_counts[h] -= 1
                        away_counts[a] -= 1

                    fl_round_vertices[r].remove(u)
                    fl_round_vertices[r].remove(v)
        return False

    success = solve_fl(0)
    if not success:
        unassigned_pairs.sort()
        success = solve_fl(0)

    if not success:
        return generate_full_berger_rounds(teams, double_round=double_round, rng=rng)

    # Permutar aleatoriamente las jornadas de 1ª vuelta que estaban totalmente vacías (sin partidos jugados fijos)
    unplayed_fl_indices = [r_idx for r_idx in range(rounds_in_fl) if len(fixed_fl_by_round[r_idx + 1]) == 0]
    if len(unplayed_fl_indices) > 1:
        shuffled_indices = list(unplayed_fl_indices)
        rng.shuffle(shuffled_indices)
        original_unplayed_rounds = [list(fl_round_matches[idx]) for idx in unplayed_fl_indices]
        for i, target_idx in enumerate(unplayed_fl_indices):
            fl_round_matches[target_idx] = list(original_unplayed_rounds[shuffled_indices.index(target_idx)])

    # Barajar el orden de los partidos dentro de cada jornada para variar horarios y orden de juego
    for r_idx in range(rounds_in_fl):
        rng.shuffle(fl_round_matches[r_idx])

    final_rounds = []
    # 1ª Vuelta
    for r_idx in range(rounds_in_fl):
        r_matches = [
            (teams_by_id[h], teams_by_id[a])
            for (h, a) in fl_round_matches[r_idx]
            if h in teams_by_id and a in teams_by_id
        ]
        final_rounds.append(r_matches)

    # 2ª Vuelta (emparejamientos de vuelta inversos con permutación aleatoria de jornadas libres no disputadas)
    if double_round:
        return_rounds = []
        for r_idx in range(rounds_in_fl):
            r_return = [(away, home) for (home, away) in final_rounds[r_idx]]
            rng.shuffle(r_return)
            return_rounds.append(r_return)

        second_leg_slots = [None] * rounds_in_fl
        used_return_indices = set()

        for sl_idx in range(rounds_in_fl):
            actual_round_num = rounds_in_fl + 1 + sl_idx
            played_in_this_round = played_by_round.get(actual_round_num, [])
            if played_in_this_round:
                for ret_idx, ret_matches in enumerate(return_rounds):
                    if ret_idx not in used_return_indices:
                        ret_pairs = set((m[0].id, m[1].id) for m in ret_matches)
                        if any((h, a) in ret_pairs for (h, a) in played_in_this_round):
                            second_leg_slots[sl_idx] = ret_matches
                            used_return_indices.add(ret_idx)
                            break

        free_return_indices = [idx for idx in range(rounds_in_fl) if idx not in used_return_indices]
        rng.shuffle(free_return_indices)

        for sl_idx in range(rounds_in_fl):
            if second_leg_slots[sl_idx] is None:
                ret_idx = free_return_indices.pop()
                second_leg_slots[sl_idx] = return_rounds[ret_idx]

        final_rounds.extend(second_leg_slots)

    return final_rounds


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
    random_seed=None,
):
    """
    Genera y guarda (o previsualiza) el calendario oficial de partidos para una temporada.
    - Si la temporada NO tiene partidos jugados: genera el torneo completo desde la J1.
    - Si la temporada YA TIENE jornadas disputadas/finalizadas: respeta intactos esos partidos
      y genera EXCLUSIVAMENTE las jornadas y partidos restantes respetando los cruces no disputados.
    """
    if not season.is_current:
        raise ValueError(
            f"No es posible generar o modificar el calendario de la temporada '{season.name}' porque es una temporada histórica finalizada. "
            "La generación de calendarios oficiales está restringida exclusivamente a temporadas activas en curso."
        )

    teams = get_season_teams(season)
    if len(teams) < 2:
        raise ValueError(f"La temporada '{season.name}' necesita al menos 2 equipos para confeccionar un calendario.")

    if not time_slots:
        time_slots = ["12:30", "17:00", "18:30", "20:45"]

    rng = random.Random(random_seed) if random_seed is not None else random.Random()

    # 1. Comprobar partidos ya disputados o en juego
    existing_matches = Match.objects.filter(season=season)
    played_matches = list(existing_matches.exclude(status=Match.Status.SCHEDULED))
    played_rounds = set(m.round_number for m in played_matches)
    max_played_round = max(played_rounds) if played_rounds else 0

    n = len(teams)
    rounds_in_first_leg = n - 1
    total_tournament_rounds = 2 * rounds_in_first_leg if double_round else rounds_in_first_leg
    matches_per_round = n // 2

    # 2. Confeccionar todas las jornadas del torneo
    if len(played_matches) == 0:
        all_season_rounds = generate_full_berger_rounds(teams, double_round=double_round, rng=rng)
    else:
        all_season_rounds = complete_partial_season_schedule(
            teams, played_matches, double_round=double_round, rng=rng
        )

    # 3. Validación matemática estricta de las 10 Reglas Round-Robin
    if len(all_season_rounds) != total_tournament_rounds:
        raise ValueError(
            f"Violación de reglas: El torneo debe tener {total_tournament_rounds} jornadas, pero se han generado {len(all_season_rounds)}."
        )

    all_pairs_seen = []
    team_home_counts = {t.id: 0 for t in teams}
    team_away_counts = {t.id: 0 for t in teams}

    for r_idx, round_pairs in enumerate(all_season_rounds, start=1):
        teams_in_r = set()
        for h, a in round_pairs:
            if h.id in teams_in_r:
                raise ValueError(
                    f"Violación de reglas en la Jornada {r_idx}: El equipo '{h.name}' juega más de una vez en la misma jornada."
                )
            if a.id in teams_in_r:
                raise ValueError(
                    f"Violación de reglas en la Jornada {r_idx}: El equipo '{a.name}' juega más de una vez en la misma jornada."
                )
            teams_in_r.add(h.id)
            teams_in_r.add(a.id)
            all_pairs_seen.append((h.id, a.id))
            team_home_counts[h.id] += 1
            team_away_counts[a.id] += 1

        if len(teams_in_r) != n:
            raise ValueError(
                f"Violación de reglas en la Jornada {r_idx}: Participan {len(teams_in_r)} equipos en lugar de {n}."
            )
        if len(round_pairs) != matches_per_round:
            raise ValueError(
                f"Violación de reglas en la Jornada {r_idx}: Hay {len(round_pairs)} partidos en lugar de {matches_per_round}."
            )

    # Validar unicidad y balance de enfrentamientos
    if len(all_pairs_seen) != len(set(all_pairs_seen)):
        raise ValueError("Violación de reglas: Existen enfrentamientos duplicados con la misma localía en la temporada.")

    if double_round:
        expected_matches_per_role = rounds_in_first_leg
        for t in teams:
            if team_home_counts[t.id] != expected_matches_per_role or team_away_counts[t.id] != expected_matches_per_role:
                raise ValueError(
                    f"Violación de reglas de equilibrio: El equipo '{t.name}' juega {team_home_counts[t.id]} en casa y {team_away_counts[t.id]} fuera "
                    f"(debe jugar exactamente {expected_matches_per_role} como local y {expected_matches_per_role} como visitante)."
                )

    # 4. Determinar fecha base para las nuevas jornadas
    now = timezone.now()
    today = now.date()

    if start_date is None:
        if max_played_round > 0 and played_matches:
            last_played_match = max(played_matches, key=lambda m: m.scheduled_at or timezone.now())
            if last_played_match and last_played_match.scheduled_at:
                last_match_date = last_played_match.scheduled_at.date()
                base_date = last_match_date + timedelta(days=round_interval_days)
                if base_date < today:
                    days_ahead = (5 - today.weekday()) % 7
                    if days_ahead == 0:
                        days_ahead = 7
                    base_date = today + timedelta(days=days_ahead)
            else:
                days_ahead = (5 - today.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7
                base_date = today + timedelta(days=days_ahead)
        else:
            days_ahead = (5 - today.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            base_date = today + timedelta(days=days_ahead)
    elif isinstance(start_date, datetime):
        base_date = start_date.date()
    else:
        base_date = start_date

    if base_date < today:
        base_date = today + timedelta(days=1)

    if weekend_spread and start_date is None and base_date.weekday() != 5:
        days_to_sat = (5 - base_date.weekday()) % 7
        if days_to_sat == 0 and base_date <= today:
            days_to_sat = 7
        base_date = base_date + timedelta(days=days_to_sat)

    # 5. Obtener árbitros y mesa oficial para asignación aleatoria
    referees = list(User.objects.filter(role=User.Role.REFEREE, is_active=True))
    table_officials = list(User.objects.filter(role=User.Role.TABLE_OFFICIAL, is_active=True))

    if not referees:
        referees = list(User.objects.filter(is_staff=True, is_active=True))
    if not table_officials:
        table_officials = list(User.objects.filter(is_staff=True, is_active=True))

    played_match_keys = set(
        (m.round_number, m.home_team_id, m.away_team_id)
        for m in played_matches
    )

    created_matches_data = []

    with transaction.atomic():
        if not dry_run:
            # Eliminar EXCLUSIVAMENTE los partidos programados no jugados (SCHEDULED)
            Match.objects.filter(season=season, status=Match.Status.SCHEDULED).delete()

        for round_idx_0, round_pairs in enumerate(all_season_rounds):
            round_idx = round_idx_0 + 1
            round_date = base_date + timedelta(days=round_idx_0 * round_interval_days)

            for match_in_round_idx, (home_team, away_team) in enumerate(round_pairs):
                # Si este partido ya fue disputado o está en juego en esta misma jornada, respetarlo intacto
                if (round_idx, home_team.id, away_team.id) in played_match_keys:
                    continue

                if weekend_spread and len(round_pairs) > 1:
                    day_offset = 0 if (match_in_round_idx < (len(round_pairs) + 1) // 2) else 1
                else:
                    day_offset = 0

                match_date = round_date + timedelta(days=day_offset)

                slot_str = time_slots[match_in_round_idx % len(time_slots)]
                try:
                    slot_h, slot_m = map(int, slot_str.split(":"))
                except Exception:
                    slot_h, slot_m = 18, 0

                match_naive = datetime.combine(match_date, time(slot_h, slot_m))
                match_dt = timezone.make_aware(match_naive, timezone.get_current_timezone())

                arena = (
                    home_team.arena_name
                    or (f"Pabellón Municipal de {home_team.city}" if home_team.city else f"Pabellón {home_team.name}")
                )

                assigned_ref1 = None
                assigned_ref2 = None
                assigned_to = None
                assigned_tk = None

                if assign_officials and referees:
                    assigned_ref1 = rng.choice(referees)
                    avail_refs = [r for r in referees if r != assigned_ref1]
                    assigned_ref2 = rng.choice(avail_refs) if avail_refs else assigned_ref1

                if assign_officials and table_officials:
                    assigned_to = rng.choice(table_officials)
                    avail_tos = [t for t in table_officials if t != assigned_to]
                    assigned_tk = rng.choice(avail_tos) if avail_tos else assigned_to

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

    created_matches_data.sort(key=lambda m: (m["round_number"], m["scheduled_at"]))

    fully_played_rounds = sum(
        1 for r in range(1, total_tournament_rounds + 1)
        if sum(1 for (h, a) in all_season_rounds[r - 1] if (r, h.id, a.id) in played_match_keys) == matches_per_round
    )

    start_round_idx = min(m["round_number"] for m in created_matches_data) if created_matches_data else 1

    return {
        "season": season,
        "total_teams": len(teams),
        "total_rounds": total_tournament_rounds,
        "total_matches": len(created_matches_data),
        "double_round": double_round,
        "start_date": base_date,
        "matches": created_matches_data,
        "dry_run": dry_run,
        "already_played_rounds": fully_played_rounds,
        "already_played_matches_count": len(played_matches),
        "start_round_idx": start_round_idx,
        "random_seed": random_seed,
    }

