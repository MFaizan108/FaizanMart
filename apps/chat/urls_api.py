from django.urls import path

from . import api_views

app_name = "chat_api"

urlpatterns = [
    path("conversations/", api_views.ConversationListView.as_view(), name="conversation-list"),
    path("conversations/start/", api_views.StartConversationView.as_view(), name="conversation-start"),
    path(
        "conversations/<int:conversation_id>/messages/",
        api_views.MessageListCreateView.as_view(),
        name="message-list",
    ),
    path(
        "conversations/<int:conversation_id>/mark-read/",
        api_views.MarkReadView.as_view(),
        name="mark-read",
    ),
    path("online-status/", api_views.OnlineStatusView.as_view(), name="online-status"),
]
