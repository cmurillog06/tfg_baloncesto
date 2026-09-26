from django.views.generic import TemplateView, RedirectView
from django.urls import reverse_lazy
from apps.matches.models import Match
from apps.teams.models import League
from apps.analytics.models import Standing


class HomeView(TemplateView):
    """
    Vista principal de inicio que muestra los partidos en vivo, competiciones y accesos rápidos.
    """

    template_name = "core/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["live_matches"] = Match.objects.filter(
            status=Match.Status.LIVE
        ).select_related("home_team", "away_team", "season__league")
        context["recent_matches"] = Match.objects.filter(
            status=Match.Status.FINISHED
        ).select_related("home_team", "away_team")[:4]
        context["upcoming_matches"] = Match.objects.filter(
            status=Match.Status.SCHEDULED
        ).select_related("home_team", "away_team")[:4]
        context["leagues"] = League.objects.filter(is_active=True)
        context["standings"] = Standing.objects.select_related(
            "team", "season"
        )[:4]
        return context


class DashboardView(HomeView):
    """
    Panel de inicio / dashboard principal de Quinto Cuarto.
    """
    pass
