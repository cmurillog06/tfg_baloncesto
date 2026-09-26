import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import ChatMessage
from apps.matches.models import Match


class MatchChatConsumer(AsyncJsonWebsocketConsumer):
    """
    Consumidor WebSocket para la sala de chat en vivo por partido.
    Permite a los aficionados, entrenadores y oficiales comentar en directo.
    """

    async def connect(self):
        self.match_id = self.scope["url_route"]["kwargs"]["match_id"]
        self.room_group_name = f"chat_{self.match_id}"
        self.user = self.scope.get("user")

        # Solo permitir conexiones de usuarios autenticados
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        # Unirse a la sala de chat del partido
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )
        await self.accept()

        # Enviar historial reciente de mensajes al usuario que entra
        history = await self.get_recent_messages(self.match_id)
        await self.send_json(
            {
                "type": "chat_history",
                "messages": history,
            }
        )

    async def disconnect(self, close_code):
        # Abandonar la sala de chat
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name,
        )

    async def receive_json(self, content):
        """
        Recibe mensajes o acciones de moderación desde el cliente.
        """
        action = content.get("action", "send_message")

        # 1. Enviar nuevo mensaje
        if action == "send_message":
            raw_text = content.get("message", "").strip()
            if not raw_text:
                return

            # Limitar longitud a 500 caracteres
            message_text = raw_text[:500]

            msg_data = await self.save_message(self.match_id, self.user, message_text)
            if msg_data:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "chat_message",
                        "data": msg_data,
                    },
                )

        # 2. Moderación: Eliminar mensaje (por Administradores o el propio autor)
        elif action == "delete_message":
            message_id = content.get("message_id")
            success = await self.delete_message_record(message_id, self.user)
            if success:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "message_deleted",
                        "message_id": message_id,
                    },
                )

    # --------------------------------------------------------------------------
    # Handlers para enviar eventos al grupo WebSocket
    # --------------------------------------------------------------------------

    async def chat_message(self, event):
        await self.send_json(
            {
                "type": "new_message",
                "data": event["data"],
            }
        )

    async def message_deleted(self, event):
        await self.send_json(
            {
                "type": "message_deleted",
                "message_id": event["message_id"],
            }
        )

    # --------------------------------------------------------------------------
    # Consultas Asíncronas a la Base de Datos con database_sync_to_async
    # --------------------------------------------------------------------------

    @database_sync_to_async
    def get_recent_messages(self, match_id):
        try:
            messages = ChatMessage.objects.filter(
                match_id=match_id
            ).select_related("user", "user__profile").order_by("created_at")[:50]

            return [
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
        except Exception:
            return []

    @database_sync_to_async
    def save_message(self, match_id, user, text):
        try:
            match = Match.objects.get(id=match_id)
            msg = ChatMessage.objects.create(
                match=match,
                user=user,
                message=text
            )
            return {
                "id": msg.id,
                "user_id": user.id,
                "username": user.username,
                "full_name": user.get_full_name() or user.username,
                "role": user.role,
                "role_display": user.get_role_display(),
                "avatar_url": user.profile.avatar.url if hasattr(user, "profile") and user.profile.avatar else None,
                "message": msg.message,
                "created_at": msg.created_at.strftime("%H:%M"),
            }
        except Exception:
            return None

    @database_sync_to_async
    def delete_message_record(self, message_id, user):
        try:
            msg = ChatMessage.objects.get(id=message_id)
            # Solo el administrador o el autor del mensaje pueden borrarlo
            if user.is_superuser or user.role == "ADMIN" or msg.user == user:
                msg.delete()
                return True
            return False
        except ChatMessage.DoesNotExist:
            return False
