from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from apps.matches.models import Match, DigitalScoreSheet, MatchEvent
from .models import Standing, PlayerMatchStat
from .services import recalculate_season_standings


@receiver([post_save, post_delete], sender=Match)
def sync_standings_on_match_change(sender, instance, **kwargs):
    """
    Sincroniza automáticamente la clasificación de la liga cada vez que un
    partido se crea, finaliza, modifica o elimina en cualquier parte del sistema.
    """
    if instance.season:
        recalculate_season_standings(instance.season)


@receiver([post_save, post_delete], sender=DigitalScoreSheet)
def sync_standings_on_scoresheet_change(sender, instance, **kwargs):
    """
    Sincroniza la clasificación cuando un acta oficial se cierra o modifica.
    """
    if instance.match and instance.match.season:
        recalculate_season_standings(instance.match.season)


@receiver(post_save, sender=MatchEvent)
def sync_player_stats_on_event_save(sender, instance, created, **kwargs):
    """
    Mantiene sincronizadas las estadísticas de jugador individuales (PlayerMatchStat)
    con cualquier evento anotado (canasta, tiro libre, falta) en tiempo real o desde Admin.
    """
    if not instance.player or not instance.match:
        return

    stat, _ = PlayerMatchStat.objects.get_or_create(
        match=instance.match,
        player=instance.player,
        defaults={"team": instance.team}
    )

    # Recalcular agregados del partido para este jugador a partir de todos sus eventos
    events = MatchEvent.objects.filter(match=instance.match, player=instance.player)
    
    total_pts = sum(ev.points for ev in events if ev.points > 0)
    t3_made = events.filter(event_type="3PT_MADE").count()
    t2_made = events.filter(event_type="2PT_MADE").count()
    ft_made = events.filter(event_type="1PT_MADE").count()
    fouls_comm = events.filter(event_type__in=["PF", "TF", "UF"]).count()

    stat.points = total_pts
    stat.three_points_made = t3_made
    stat.three_points_attempted = max(stat.three_points_attempted, t3_made)
    stat.field_goals_made = t3_made + t2_made
    stat.field_goals_attempted = max(stat.field_goals_attempted, t3_made + t2_made)
    stat.free_throws_made = ft_made
    stat.free_throws_attempted = max(stat.free_throws_attempted, ft_made)
    stat.fouls_committed = fouls_comm
    stat.compute_pir()
    stat.save()
