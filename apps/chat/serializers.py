from rest_framework import serializers

from . import services
from .models import Conversation, Message


class MessageSerializer(serializers.ModelSerializer):
    sender_email = serializers.EmailField(source="sender.email", read_only=True)

    class Meta:
        model = Message
        fields = [
            "id", "conversation", "sender", "sender_email", "text",
            "attachment", "is_read", "read_at", "created_at",
        ]
        read_only_fields = ["id", "sender", "sender_email", "is_read", "read_at", "created_at"]


class ConversationSerializer(serializers.ModelSerializer):
    customer_email = serializers.EmailField(source="customer.email", read_only=True)
    counterpart_email = serializers.EmailField(source="counterpart.email", read_only=True)
    counterpart_online = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "id", "kind", "customer", "customer_email", "counterpart", "counterpart_email",
            "counterpart_online", "store", "ticket", "last_message", "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_counterpart_online(self, obj):
        return services.is_user_online(obj.counterpart_id)

    def get_last_message(self, obj):
        last = obj.messages.order_by("-created_at").first()
        return MessageSerializer(last).data if last else None


class StartConversationSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=Conversation.Kind.choices)
    counterpart_id = serializers.IntegerField()
    store_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    ticket_id = serializers.IntegerField(required=False, allow_null=True, default=None)
