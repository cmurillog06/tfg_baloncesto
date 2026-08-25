from django.urls import path
from .views import (
    MatchListView,
    MatchLiveView,
    OfficialTableScorekeeperView,
    ScoreSheetDetailView,
)

app_name = "matches"

urlpatterns = [
    path("", MatchListView.as_view(), name="match_list"),
    path("<int:pk>/live/", MatchLiveView.as_view(), name="match_live"),
    path("<int:pk>/scorekeeper/", OfficialTableScorekeeperView.as_view(), name="scorekeeper"),
    path("<int:pk>/scoresheet/", ScoreSheetDetailView.as_view(), name="scoresheet_detail"),
]
