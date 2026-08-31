from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.generic import ListView

from .models import ChatMessage
from apps.matches.models import Match


class MatchChatHistoryView(LoginRequiredMixin, View):
    """
    Endpoint JSON para obtener el historial de mensajes de un partido.
    """

    def get(self, request, match_id, *args, **kwargs):
        match = get_object_or_404(Match, id=match_id)
        messages = ChatMessage.objects.filter(match=match).select_related("user", "user__profile").order_by("created_at")[:50]

        data = [
            {
                "id": msg.id,
                "user_id": msg.user.id,
                "username": msg.user.username,
                "full_name": msg.user.get_full_name() or msg.user.username,
                "role": msg.user.role,
                "role_display": msg.user.get_role_display(),
                "avatar_url": msg.user.profile.avatar.url if hasattr(msg.user, "profile") and msg.user.profile.avatar else None,
                "message": msg.message,
                "created_at": msg.created_at.strftime("%H:%M"),
            }
            for msg in messages
        ]

        return JsonResponse({"messages": data})


class DeleteChatMessageView(LoginRequiredMixin, View):
    """
    Endpoint para eliminar un mensaje por su autor o administradores.
    """

    def post(self, request, message_id, *args, **kwargs):
        msg = get_object_or_404(ChatMessage, id=message_id)
        user = request.user

        if not (user.is_superuser or user.role == "ADMIN" or msg.user == user):
            raise PermissionDenied("No tienes permisos para eliminar este mensaje.")

        msg.delete()
        return JsonResponse({"success": True, "message_id": message_id})
