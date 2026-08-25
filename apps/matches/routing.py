from django.urls import re_path
from .consumers import MatchLiveConsumer

websocket_urlpatterns = [
    re_path(r"^ws/matches/(?P<match_id>\d+)/live/$", MatchLiveConsumer.as_asgi()),
]
