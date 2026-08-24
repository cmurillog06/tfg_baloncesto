from django.db import models
from django.conf import settings
from apps.matches.models import Match


class ChatMessage(models.Model):
    """
    Mensaje emitido en la sala de chat en vivo vinculada a un partido.
    """

    match = models.ForeignKey(
        Match, on_delete=models.CASCADE, related_name="chat_messages", verbose_name="Partido"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_messages",
        verbose_name="Usuario",
    )
    message = models.TextField(max_length=500, verbose_name="Mensaje")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha y Hora")

    class Meta:
        verbose_name = "Mensaje de Chat"
        verbose_name_plural = "Mensajes de Chat"
        ordering = ["created_at"]

    def __str__(self):
        return f"[{self.created_at.strftime('%H:%M')}] {self.user.username}: {self.message[:30]}"
