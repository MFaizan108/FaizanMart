from django.core.cache import cache
from django.utils import timezone

from .models import Conversation, Message

ONLINE_TTL_SECONDS = 90


def get_or_create_conversation(*, customer, counterpart, kind, store=None, ticket=None):
    if kind == Conversation.Kind.CUSTOMER_VENDOR:
        conversation, _ = Conversation.objects.get_or_create(
            kind=kind, customer=customer, store=store, defaults={"counterpart": counterpart}
        )
        return conversation
    conversation, _ = Conversation.objects.get_or_create(
        kind=kind, customer=customer, ticket=ticket, defaults={"counterpart": counterpart}
    )
    return conversation


def create_message(*, conversation, sender, text="", attachment=None):
    message = Message.objects.create(conversation=conversation, sender=sender, text=text, attachment=attachment)
    conversation.save(update_fields=["updated_at"])
    return message


def mark_messages_read(*, conversation, reader):
    unread = Message.objects.filter(conversation=conversation, is_read=False).exclude(sender=reader)
    ids = list(unread.values_list("id", flat=True))
    unread.update(is_read=True, read_at=timezone.now())
    return ids


def set_user_online(user_id, online):
    key = f"chat:online:{user_id}"
    if online:
        cache.set(key, True, ONLINE_TTL_SECONDS)
    else:
        cache.delete(key)


def is_user_online(user_id):
    return bool(cache.get(f"chat:online:{user_id}"))
