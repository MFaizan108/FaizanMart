from channels.db import database_sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from . import services
from .middleware import JWTAuthMiddleware
from .models import Conversation, Message
from .routing import websocket_urlpatterns

User = get_user_model()


def access_token_for(user):
    return str(RefreshToken.for_user(user).access_token)


def ws_application():
    return JWTAuthMiddleware(URLRouter(websocket_urlpatterns))


class ChatRestTestBase(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            email="chatcustomer@example.com", password="S0meStrongPass!", role=User.Role.CUSTOMER
        )
        self.vendor = User.objects.create_user(
            email="chatvendor@example.com", password="S0meStrongPass!", role=User.Role.VENDOR
        )
        self.stranger = User.objects.create_user(
            email="chatstranger@example.com", password="S0meStrongPass!", role=User.Role.CUSTOMER
        )

    def login(self, email, password="S0meStrongPass!"):
        response = self.client.post(reverse("accounts_api:login"), {"email": email, "password": password})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")


class ConversationRestTests(ChatRestTestBase):
    def test_start_conversation_creates_it(self):
        self.login("chatcustomer@example.com")
        response = self.client.post(
            reverse("chat_api:conversation-start"),
            {"kind": Conversation.Kind.CUSTOMER_VENDOR, "counterpart_id": self.vendor.id},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Conversation.objects.count(), 1)

    def test_starting_same_conversation_twice_reuses_it(self):
        self.login("chatcustomer@example.com")
        first = self.client.post(
            reverse("chat_api:conversation-start"),
            {"kind": Conversation.Kind.CUSTOMER_VENDOR, "counterpart_id": self.vendor.id},
        )
        second = self.client.post(
            reverse("chat_api:conversation-start"),
            {"kind": Conversation.Kind.CUSTOMER_VENDOR, "counterpart_id": self.vendor.id},
        )
        self.assertEqual(first.data["id"], second.data["id"])
        self.assertEqual(Conversation.objects.count(), 1)

    def test_conversation_list_only_shows_own_conversations(self):
        conversation = services.get_or_create_conversation(
            customer=self.customer, counterpart=self.vendor, kind=Conversation.Kind.CUSTOMER_VENDOR
        )
        self.login("chatstranger@example.com")
        response = self.client.get(reverse("chat_api:conversation-list"))
        self.assertEqual(response.data["count"], 0)

        self.login("chatcustomer@example.com")
        response = self.client.get(reverse("chat_api:conversation-list"))
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], conversation.id)


class MessageRestTests(ChatRestTestBase):
    def setUp(self):
        super().setUp()
        self.conversation = services.get_or_create_conversation(
            customer=self.customer, counterpart=self.vendor, kind=Conversation.Kind.CUSTOMER_VENDOR
        )

    def test_participant_can_post_and_list_messages(self):
        self.login("chatcustomer@example.com")
        response = self.client.post(
            reverse("chat_api:message-list", args=[self.conversation.id]), {"text": "Hello!"}
        )
        self.assertEqual(response.status_code, 201)

        listing = self.client.get(reverse("chat_api:message-list", args=[self.conversation.id]))
        self.assertEqual(listing.data["count"], 1)
        self.assertEqual(listing.data["results"][0]["text"], "Hello!")

    def test_non_participant_cannot_post_or_list_messages(self):
        self.login("chatstranger@example.com")
        response = self.client.post(
            reverse("chat_api:message-list", args=[self.conversation.id]), {"text": "Hi"}
        )
        self.assertEqual(response.status_code, 403)

        response = self.client.get(reverse("chat_api:message-list", args=[self.conversation.id]))
        self.assertEqual(response.status_code, 403)

    def test_message_without_text_or_attachment_rejected(self):
        self.login("chatcustomer@example.com")
        response = self.client.post(reverse("chat_api:message-list", args=[self.conversation.id]), {})
        self.assertEqual(response.status_code, 400)

    def test_mark_read_only_flips_other_persons_messages(self):
        Message.objects.create(conversation=self.conversation, sender=self.customer, text="from customer")
        Message.objects.create(conversation=self.conversation, sender=self.vendor, text="from vendor")

        self.login("chatcustomer@example.com")
        response = self.client.post(reverse("chat_api:mark-read", args=[self.conversation.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["marked_read"]), 1)

        own_message = Message.objects.get(sender=self.customer)
        other_message = Message.objects.get(sender=self.vendor)
        self.assertFalse(own_message.is_read)
        self.assertTrue(other_message.is_read)


LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "chat-online-status-tests",
    }
}


@override_settings(CACHES=LOCMEM_CACHE)
class OnlineStatusTests(ChatRestTestBase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def test_reflects_presence_cache(self):
        self.login("chatcustomer@example.com")
        response = self.client.get(reverse("chat_api:online-status"), {"user_id": self.vendor.id})
        self.assertFalse(response.data["online"])

        services.set_user_online(self.vendor.id, True)
        response = self.client.get(reverse("chat_api:online-status"), {"user_id": self.vendor.id})
        self.assertTrue(response.data["online"])


class ChatConsumerTests(TransactionTestCase):
    """Uses TransactionTestCase (not TestCase) because database_sync_to_async runs DB work
    on a separate thread — TestCase's per-test wrapping transaction isn't visible across
    threads, which causes 'connection already closed' errors under a plain TestCase here."""

    def setUp(self):
        self.customer = User.objects.create_user(
            email="chatcustomer@example.com", password="S0meStrongPass!", role=User.Role.CUSTOMER
        )
        self.vendor = User.objects.create_user(
            email="chatvendor@example.com", password="S0meStrongPass!", role=User.Role.VENDOR
        )
        self.stranger = User.objects.create_user(
            email="chatstranger@example.com", password="S0meStrongPass!", role=User.Role.CUSTOMER
        )

    async def test_connect_without_token_is_rejected(self):
        conversation = await self._make_conversation()
        communicator = WebsocketCommunicator(ws_application(), f"/ws/chat/{conversation.id}/")
        connected, _ = await communicator.connect()
        self.assertFalse(connected)
        await communicator.disconnect()

    async def test_connect_as_non_participant_is_rejected(self):
        conversation = await self._make_conversation()
        token = await database_sync_to_async(access_token_for)(self.stranger)
        communicator = WebsocketCommunicator(ws_application(), f"/ws/chat/{conversation.id}/?token={token}")
        connected, _ = await communicator.connect()
        self.assertFalse(connected)
        await communicator.disconnect()

    async def test_send_message_is_broadcast_to_participant(self):
        conversation = await self._make_conversation()
        customer_token = await database_sync_to_async(access_token_for)(self.customer)
        vendor_token = await database_sync_to_async(access_token_for)(self.vendor)

        customer_ws = WebsocketCommunicator(ws_application(), f"/ws/chat/{conversation.id}/?token={customer_token}")
        vendor_ws = WebsocketCommunicator(ws_application(), f"/ws/chat/{conversation.id}/?token={vendor_token}")
        self.assertTrue((await customer_ws.connect())[0])
        self.assertTrue((await vendor_ws.connect())[0])

        # Both sides receive a presence.update when the other connects.
        await customer_ws.receive_json_from()

        await customer_ws.send_json_to({"type": "message", "text": "Hello vendor"})
        received = await vendor_ws.receive_json_from()
        self.assertEqual(received["type"], "message")
        self.assertEqual(received["text"], "Hello vendor")

        await customer_ws.disconnect()
        await vendor_ws.disconnect()

    async def test_typing_indicator_is_not_echoed_back_to_sender(self):
        conversation = await self._make_conversation()
        customer_token = await database_sync_to_async(access_token_for)(self.customer)
        vendor_token = await database_sync_to_async(access_token_for)(self.vendor)

        customer_ws = WebsocketCommunicator(ws_application(), f"/ws/chat/{conversation.id}/?token={customer_token}")
        vendor_ws = WebsocketCommunicator(ws_application(), f"/ws/chat/{conversation.id}/?token={vendor_token}")
        await customer_ws.connect()
        await vendor_ws.connect()
        await customer_ws.receive_json_from()  # presence update from vendor joining

        await customer_ws.send_json_to({"type": "typing", "is_typing": True})
        received = await vendor_ws.receive_json_from()
        self.assertEqual(received["type"], "typing")
        self.assertTrue(received["is_typing"])
        self.assertTrue(await customer_ws.receive_nothing())

        await customer_ws.disconnect()
        await vendor_ws.disconnect()

    async def _make_conversation(self):
        return await database_sync_to_async(services.get_or_create_conversation)(
            customer=self.customer, counterpart=self.vendor, kind=Conversation.Kind.CUSTOMER_VENDOR
        )
