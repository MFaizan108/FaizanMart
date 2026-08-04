from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import Conversation, Message
from .serializers import ConversationSerializer, MessageSerializer, StartConversationSerializer

User = get_user_model()


def _broadcast_message(conversation_id, message):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        f"chat_{conversation_id}",
        {
            "type": "chat.message",
            "message": {
                "id": message.id,
                "conversation": conversation_id,
                "sender": message.sender_id,
                "sender_email": message.sender.email,
                "text": message.text,
                "attachment": message.attachment.url if message.attachment else None,
                "created_at": message.created_at.isoformat(),
            },
        },
    )


class StartConversationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = StartConversationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        counterpart = get_object_or_404(User, pk=data["counterpart_id"])
        store = None
        if data["store_id"]:
            from apps.vendors.models import Store

            store = get_object_or_404(Store, pk=data["store_id"])
        ticket = None
        if data["ticket_id"]:
            from apps.support.models import Ticket

            ticket = get_object_or_404(Ticket, pk=data["ticket_id"])

        conversation = services.get_or_create_conversation(
            customer=request.user, counterpart=counterpart, kind=data["kind"], store=store, ticket=ticket
        )
        return Response(ConversationSerializer(conversation).data, status=201)


class ConversationListView(generics.ListAPIView):
    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Conversation.objects.filter(Q(customer=user) | Q(counterpart=user)).select_related(
            "customer", "counterpart"
        )


class MessageListCreateView(generics.ListCreateAPIView):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def _get_conversation(self):
        conversation = get_object_or_404(Conversation, pk=self.kwargs["conversation_id"])
        if not conversation.is_participant(self.request.user):
            raise PermissionDenied("You are not part of this conversation.")
        return conversation

    def get_queryset(self):
        conversation = self._get_conversation()
        return Message.objects.filter(conversation=conversation).select_related("sender")

    def create(self, request, *args, **kwargs):
        conversation = self._get_conversation()
        text = request.data.get("text", "")
        attachment = request.data.get("attachment")
        if not text and not attachment:
            raise ValidationError("A message needs text or an attachment.")
        message = services.create_message(
            conversation=conversation, sender=request.user, text=text, attachment=attachment
        )
        _broadcast_message(conversation.id, message)
        return Response(MessageSerializer(message).data, status=201)


class MarkReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, conversation_id):
        conversation = get_object_or_404(Conversation, pk=conversation_id)
        if not conversation.is_participant(request.user):
            raise PermissionDenied("You are not part of this conversation.")
        message_ids = services.mark_messages_read(conversation=conversation, reader=request.user)
        return Response({"marked_read": message_ids})


class OnlineStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user_id = request.query_params.get("user_id")
        if not user_id:
            raise ValidationError("user_id query parameter is required.")
        return Response({"user_id": int(user_id), "online": services.is_user_online(user_id)})
