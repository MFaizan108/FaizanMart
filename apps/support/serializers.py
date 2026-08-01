from rest_framework import serializers

from .models import FAQ, Ticket, TicketMessage


class TicketMessageSerializer(serializers.ModelSerializer):
    sender_email = serializers.EmailField(source="sender.email", read_only=True)

    class Meta:
        model = TicketMessage
        fields = ["id", "sender_email", "message", "created_at"]
        read_only_fields = fields


class TicketSerializer(serializers.ModelSerializer):
    customer_email = serializers.EmailField(source="customer.email", read_only=True)
    messages = TicketMessageSerializer(many=True, read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id",
            "customer_email",
            "subject",
            "description",
            "status",
            "priority",
            "assigned_to",
            "messages",
            "created_at",
        ]
        read_only_fields = ["id", "customer_email", "status", "assigned_to", "messages", "created_at"]


class TicketCreateSerializer(serializers.Serializer):
    subject = serializers.CharField(max_length=200)
    description = serializers.CharField()
    priority = serializers.ChoiceField(choices=Ticket.Priority.choices, required=False, default=Ticket.Priority.MEDIUM)


class AddMessageSerializer(serializers.Serializer):
    message = serializers.CharField()


class TicketStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Ticket.Status.choices)


class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = ["id", "question", "answer", "category", "sort_order", "is_published"]
        read_only_fields = ["id"]
