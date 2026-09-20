import pytest
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from config.asgi import application
from apps.chat.models import ChatMessage


@database_sync_to_async
def db_create_chat_message(match, user, message):
    return ChatMessage.objects.create(match=match, user=user, message=message)


@database_sync_to_async
def db_chat_message_exists(match, message):
    return ChatMessage.objects.filter(match=match, message=message).exists()


@database_sync_to_async
def db_chat_message_id_exists(msg_id):
    return ChatMessage.objects.filter(id=msg_id).exists()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestMatchChatConsumer:
    """Pruebas asíncronas y de tiempo real para MatchChatConsumer usando WebsocketCommunicator."""

    async def test_chat_consumer_unauthenticated_connection_rejected(self, live_match):
        communicator = WebsocketCommunicator(application, f"/ws/chat/{live_match.id}/")
        communicator.scope["user"] = AnonymousUser()
        connected, close_code = await communicator.connect()
        assert connected is False or close_code == 4001
        await communicator.disconnect()

    async def test_chat_consumer_authenticated_connection_accepted(self, live_match, fan_user):
        communicator = WebsocketCommunicator(application, f"/ws/chat/{live_match.id}/")
        communicator.scope["user"] = fan_user
        connected, _ = await communicator.connect()
        assert connected is True
        await communicator.disconnect()

    async def test_chat_consumer_connect_receives_chat_history(self, live_match, fan_user):
        communicator = WebsocketCommunicator(application, f"/ws/chat/{live_match.id}/")
        communicator.scope["user"] = fan_user
        await communicator.connect()
        response = await communicator.receive_json_from()
        assert response["type"] == "chat_history"
        assert "messages" in response
        await communicator.disconnect()

    async def test_chat_consumer_chat_history_contains_previous_messages(self, live_match, fan_user):
        await db_create_chat_message(live_match, fan_user, "¡Gran partido!")
        communicator = WebsocketCommunicator(application, f"/ws/chat/{live_match.id}/")
        communicator.scope["user"] = fan_user
        await communicator.connect()
        response = await communicator.receive_json_from()
        assert len(response["messages"]) >= 1
        assert response["messages"][0]["message"] == "¡Gran partido!"
        await communicator.disconnect()

    async def test_chat_consumer_chat_history_contains_user_avatars_and_roles(self, live_match, fan_user):
        await db_create_chat_message(live_match, fan_user, "Mensaje con rol")
        communicator = WebsocketCommunicator(application, f"/ws/chat/{live_match.id}/")
        communicator.scope["user"] = fan_user
        await communicator.connect()
        response = await communicator.receive_json_from()
        msg = response["messages"][0]
        assert "role" in msg
        assert "username" in msg
        await communicator.disconnect()

    async def test_chat_consumer_disconnect_leaves_group(self, live_match, fan_user):
        communicator = WebsocketCommunicator(application, f"/ws/chat/{live_match.id}/")
        communicator.scope["user"] = fan_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.disconnect()

    async def test_chat_consumer_send_message_success(self, live_match, fan_user):
        communicator = WebsocketCommunicator(application, f"/ws/chat/{live_match.id}/")
        communicator.scope["user"] = fan_user
        await communicator.connect()
        await communicator.receive_json_from()  # history
        await communicator.send_json_to({"action": "send_message", "message": "¡Vamos RMB!"})
        response = await communicator.receive_json_from()
        assert response["type"] == "new_message"
        assert response["data"]["message"] == "¡Vamos RMB!"
        await communicator.disconnect()

    async def test_chat_consumer_send_message_creates_chatmessage_in_db(self, live_match, fan_user):
        communicator = WebsocketCommunicator(application, f"/ws/chat/{live_match.id}/")
        communicator.scope["user"] = fan_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({"action": "send_message", "message": "Comentario guardado en BD"})
        await communicator.receive_json_from()
        exists = await db_chat_message_exists(live_match, "Comentario guardado en BD")
        assert exists is True
        await communicator.disconnect()

    async def test_chat_consumer_send_message_broadcasts_new_message(self, live_match, fan_user):
        communicator = WebsocketCommunicator(application, f"/ws/chat/{live_match.id}/")
        communicator.scope["user"] = fan_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({"action": "send_message", "message": "Broadcast test"})
        response = await communicator.receive_json_from()
        assert response["type"] == "new_message"
        await communicator.disconnect()

    async def test_chat_consumer_send_message_contains_author_username(self, live_match, fan_user):
        communicator = WebsocketCommunicator(application, f"/ws/chat/{live_match.id}/")
        communicator.scope["user"] = fan_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({"action": "send_message", "message": "Hola a todos"})
        response = await communicator.receive_json_from()
        assert response["data"]["username"] == fan_user.username
        await communicator.disconnect()

    async def test_chat_consumer_send_message_contains_timestamp(self, live_match, fan_user):
        communicator = WebsocketCommunicator(application, f"/ws/chat/{live_match.id}/")
        communicator.scope["user"] = fan_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({"action": "send_message", "message": "Con timestamp"})
        response = await communicator.receive_json_from()
        assert "created_at" in response["data"]
        await communicator.disconnect()

    async def test_chat_consumer_send_empty_message_ignored(self, live_match, fan_user):
        communicator = WebsocketCommunicator(application, f"/ws/chat/{live_match.id}/")
        communicator.scope["user"] = fan_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({"action": "send_message", "message": ""})
        assert await communicator.receive_nothing() is True
        await communicator.disconnect()

    async def test_chat_consumer_send_whitespace_message_ignored(self, live_match, fan_user):
        communicator = WebsocketCommunicator(application, f"/ws/chat/{live_match.id}/")
        communicator.scope["user"] = fan_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({"action": "send_message", "message": "   "})
        assert await communicator.receive_nothing() is True
        await communicator.disconnect()

    async def test_chat_consumer_send_long_message_truncated_to_500_chars(self, live_match, fan_user):
        long_text = "A" * 600
        communicator = WebsocketCommunicator(application, f"/ws/chat/{live_match.id}/")
        communicator.scope["user"] = fan_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({"action": "send_message", "message": long_text})
        response = await communicator.receive_json_from()
        assert len(response["data"]["message"]) == 500
        await communicator.disconnect()

    async def test_chat_consumer_delete_message_by_author_success(self, live_match, fan_user):
        msg = await db_create_chat_message(live_match, fan_user, "Mensaje a borrar")
        communicator = WebsocketCommunicator(application, f"/ws/chat/{live_match.id}/")
        communicator.scope["user"] = fan_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({"action": "delete_message", "message_id": msg.id})
        response = await communicator.receive_json_from()
        assert response["type"] == "message_deleted"
        assert response["message_id"] == msg.id
        await communicator.disconnect()

    async def test_chat_consumer_delete_message_by_admin_success(self, live_match, fan_user, admin_user):
        msg = await db_create_chat_message(live_match, fan_user, "Mensaje borrado por admin")
        communicator = WebsocketCommunicator(application, f"/ws/chat/{live_match.id}/")
        communicator.scope["user"] = admin_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({"action": "delete_message", "message_id": msg.id})
        response = await communicator.receive_json_from()
        assert response["type"] == "message_deleted"
        await communicator.disconnect()

    async def test_chat_consumer_delete_message_by_other_user_fails(self, live_match, fan_user, coach_user):
        msg = await db_create_chat_message(live_match, fan_user, "Mensaje ajeno")
        communicator = WebsocketCommunicator(application, f"/ws/chat/{live_match.id}/")
        communicator.scope["user"] = coach_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({"action": "delete_message", "message_id": msg.id})
        assert await communicator.receive_nothing() is True
        exists = await db_chat_message_id_exists(msg.id)
        assert exists is True
        await communicator.disconnect()

    async def test_chat_consumer_delete_message_removes_from_db(self, live_match, fan_user):
        msg = await db_create_chat_message(live_match, fan_user, "Borrar de la BD")
        communicator = WebsocketCommunicator(application, f"/ws/chat/{live_match.id}/")
        communicator.scope["user"] = fan_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({"action": "delete_message", "message_id": msg.id})
        await communicator.receive_json_from()
        exists = await db_chat_message_id_exists(msg.id)
        assert exists is False
        await communicator.disconnect()

    async def test_chat_consumer_delete_message_broadcasts_message_deleted(self, live_match, fan_user):
        msg = await db_create_chat_message(live_match, fan_user, "Broadcast delete")
        communicator = WebsocketCommunicator(application, f"/ws/chat/{live_match.id}/")
        communicator.scope["user"] = fan_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({"action": "delete_message", "message_id": msg.id})
        response = await communicator.receive_json_from()
        assert response["type"] == "message_deleted"
        await communicator.disconnect()

    async def test_chat_consumer_multi_client_message_broadcasting(self, live_match, fan_user, coach_user):
        comm1 = WebsocketCommunicator(application, f"/ws/chat/{live_match.id}/")
        comm1.scope["user"] = fan_user
        await comm1.connect()
        await comm1.receive_json_from()

        comm2 = WebsocketCommunicator(application, f"/ws/chat/{live_match.id}/")
        comm2.scope["user"] = coach_user
        await comm2.connect()
        await comm2.receive_json_from()

        await comm1.send_json_to({"action": "send_message", "message": "Mensaje para ambos"})
        r1 = await comm1.receive_json_from()
        r2 = await comm2.receive_json_from()
        assert r1["data"]["message"] == "Mensaje para ambos"
        assert r2["data"]["message"] == "Mensaje para ambos"

        await comm1.disconnect()
        await comm2.disconnect()

    async def test_chat_consumer_multiple_messages_history_order(self, live_match, fan_user):
        await db_create_chat_message(live_match, fan_user, "Primero")
        await db_create_chat_message(live_match, fan_user, "Segundo")
        communicator = WebsocketCommunicator(application, f"/ws/chat/{live_match.id}/")
        communicator.scope["user"] = fan_user
        await communicator.connect()
        response = await communicator.receive_json_from()
        assert response["messages"][0]["message"] == "Primero"
        assert response["messages"][1]["message"] == "Segundo"
        await communicator.disconnect()

    async def test_chat_consumer_str_representation_model(self, live_match, fan_user):
        msg = await db_create_chat_message(live_match, fan_user, "Test de representación")
        assert fan_user.username in str(msg)
        assert "Test de representación" in str(msg)

    async def test_chat_consumer_special_characters_handling(self, live_match, fan_user):
        communicator = WebsocketCommunicator(application, f"/ws/chat/{live_match.id}/")
        communicator.scope["user"] = fan_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({"action": "send_message", "message": "🏀 ¡2+1 y tiro libre! 🇪🇸 <script>alert(1)</script>"})
        response = await communicator.receive_json_from()
        assert "🏀" in response["data"]["message"]
        await communicator.disconnect()

    async def test_chat_consumer_role_display_in_message_payload(self, live_match, coach_user):
        communicator = WebsocketCommunicator(application, f"/ws/chat/{live_match.id}/")
        communicator.scope["user"] = coach_user
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({"action": "send_message", "message": "Instrucciones de pizarra"})
        response = await communicator.receive_json_from()
        assert response["data"]["role"] == "COACH"
        assert response["data"]["role_display"] == "Entrenador"
        await communicator.disconnect()
