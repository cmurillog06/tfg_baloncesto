from django.urls import path
from .views import MatchChatHistoryView, DeleteChatMessageView

app_name = "chat"

urlpatterns = [
    path("<int:match_id>/history/", MatchChatHistoryView.as_view(), name="match_history"),
    path("message/<int:message_id>/delete/", DeleteChatMessageView.as_view(), name="delete_message"),
]
