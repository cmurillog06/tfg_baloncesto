from django.urls import path
from .views import (
    AnalyticsDashboardView,
    LeadersListView,
    TeamComparatorView,
    PlayerComparatorView,
    PredictiveModelView,
)

app_name = "analytics"

urlpatterns = [
    path("", AnalyticsDashboardView.as_view(), name="dashboard"),
    path("leaders/", LeadersListView.as_view(), name="leaders"),
    path("compare-teams/", TeamComparatorView.as_view(), name="compare_teams"),
    path("compare-players/", PlayerComparatorView.as_view(), name="compare_players"),
    path("predictive/", PredictiveModelView.as_view(), name="predictive_model"),
]
