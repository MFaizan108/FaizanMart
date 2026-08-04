from django.contrib import admin

from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ["sender", "text", "attachment", "is_read", "read_at", "created_at"]
    can_delete = False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["id", "kind", "customer", "counterpart", "store", "ticket", "updated_at"]
    list_filter = ["kind"]
    search_fields = ["customer__email", "counterpart__email"]
    inlines = [MessageInline]
