from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Conversation(TimeStampedModel):
    class Kind(models.TextChoices):
        CUSTOMER_VENDOR = "customer_vendor", "Customer <-> Vendor"
        CUSTOMER_SUPPORT = "customer_support", "Customer <-> Support"

    kind = models.CharField(max_length=20, choices=Kind.choices)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_conversations_as_customer"
    )
    counterpart = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_conversations_as_counterpart"
    )
    store = models.ForeignKey(
        "vendors.Store", on_delete=models.SET_NULL, null=True, blank=True, related_name="chat_conversations"
    )
    ticket = models.ForeignKey(
        "support.Ticket", on_delete=models.SET_NULL, null=True, blank=True, related_name="chat_conversations"
    )

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["customer"]),
            models.Index(fields=["counterpart"]),
        ]

    def __str__(self):
        return f"Conversation #{self.pk} ({self.kind})"

    def is_participant(self, user):
        return bool(user) and user.is_authenticated and user.id in (self.customer_id, self.counterpart_id)


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_messages")
    text = models.TextField(blank=True)
    attachment = models.FileField(upload_to="chat_attachments/", null=True, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["conversation", "created_at"])]

    def __str__(self):
        return f"Message #{self.pk} in conversation #{self.conversation_id}"
