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



