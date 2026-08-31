from django.urls import re_path
from .consumers import MatchChatConsumer

websocket_urlpatterns = [
    re_path(r"^ws/chat/(?P<match_id>\d+)/$", MatchChatConsumer.as_asgi()),
]
