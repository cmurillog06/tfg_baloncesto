from django.urls import path
from .views import (
    LeagueListView,
    LeagueDetailView,
    TeamListView,
    TeamDetailView,
    PlayerDetailView,
    CoachRosterManageView,
)

app_name = "teams"

urlpatterns = [
    # Ligas
    path("leagues/", LeagueListView.as_view(), name="league_list"),
    path("leagues/<slug:slug>/", LeagueDetailView.as_view(), name="league_detail"),
    # Equipos
    path("", TeamListView.as_view(), name="team_list"),
    path("<slug:slug>/", TeamDetailView.as_view(), name="team_detail"),
    path("<slug:slug>/manage-roster/", CoachRosterManageView.as_view(), name="roster_manage"),
    # Jugadores
    path("players/<int:pk>/", PlayerDetailView.as_view(), name="player_detail"),
]
