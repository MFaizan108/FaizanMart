from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from . import services
from .models import Conversation, Message


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get("user")
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        allowed = await self._user_can_access_conversation()
        if not allowed:
            await self.close(code=4003)
            return

        self.group_name = f"chat_{self.conversation_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        await database_sync_to_async(services.set_user_online)(self.user.id, True)
        await self.channel_layer.group_send(
            self.group_name, {"type": "presence.update", "user_id": self.user.id, "online": True}
        )

    async def disconnect(self, close_code):
        if not hasattr(self, "group_name"):
            return
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        await database_sync_to_async(services.set_user_online)(self.user.id, False)
        await self.channel_layer.group_send(
            self.group_name, {"type": "presence.update", "user_id": self.user.id, "online": False}
        )

    async def receive_json(self, content, **kwargs):
        message_type = content.get("type")
        if message_type == "message":
            await self._handle_message(content)
        elif message_type == "typing":
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "typing.broadcast",
                    "user_id": self.user.id,
                    "is_typing": bool(content.get("is_typing", True)),
                },
            )
        elif message_type == "read":
            await self._handle_read(content.get("message_ids", []))
        elif message_type == "heartbeat":
            await database_sync_to_async(services.set_user_online)(self.user.id, True)

    async def _handle_message(self, content):
        text = (content.get("text") or "").strip()
        if not text:
            return
        message = await self._create_message(text)
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat.message",
                "message": {
                    "id": message.id,
                    "conversation": self.conversation_id,
                    "sender": self.user.id,
                    "sender_email": self.user.email,
                    "text": message.text,
                    "attachment": message.attachment.url if message.attachment else None,
                    "created_at": message.created_at.isoformat(),
                },
            },
        )

    async def _handle_read(self, message_ids):
        updated_ids = await self._mark_read(message_ids)
        if updated_ids:
            await self.channel_layer.group_send(
                self.group_name, {"type": "read.receipt", "reader_id": self.user.id, "message_ids": updated_ids}
            )

    # --- channel_layer.group_send handlers (dispatched by "type", dots -> underscores) ---

    async def chat_message(self, event):
        await self.send_json({"type": "message", **event["message"]})

    async def typing_broadcast(self, event):
        if event["user_id"] != self.user.id:
            await self.send_json({"type": "typing", "user_id": event["user_id"], "is_typing": event["is_typing"]})

    async def read_receipt(self, event):
        await self.send_json(
            {"type": "read_receipt", "reader_id": event["reader_id"], "message_ids": event["message_ids"]}
        )

    async def presence_update(self, event):
        if event["user_id"] != self.user.id:
            await self.send_json({"type": "presence", "user_id": event["user_id"], "online": event["online"]})

    # --- DB helpers ---

    @database_sync_to_async
    def _user_can_access_conversation(self):
        conversation = Conversation.objects.filter(pk=self.conversation_id).first()
        return conversation is not None and conversation.is_participant(self.user)

    @database_sync_to_async
    def _create_message(self, text):
        conversation = Conversation.objects.get(pk=self.conversation_id)
        return services.create_message(conversation=conversation, sender=self.user, text=text)

    @database_sync_to_async
    def _mark_read(self, message_ids):
        ids = list(
            Message.objects.filter(
                conversation_id=self.conversation_id, id__in=message_ids, is_read=False
            ).exclude(sender=self.user).values_list("id", flat=True)
        )
        if ids:
            from django.utils import timezone

            Message.objects.filter(id__in=ids).update(is_read=True, read_at=timezone.now())
        return ids
