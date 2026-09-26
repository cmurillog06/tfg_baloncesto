from django.contrib import admin
from .models import ChatMessage


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("match", "user", "message", "created_at")
    list_filter = ("created_at", "match")
    search_fields = ("user__username", "message")
