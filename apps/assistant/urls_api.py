from django.urls import path

from . import api_views

app_name = "assistant_api"

urlpatterns = [
    path("query/", api_views.AssistantQueryView.as_view(), name="query"),
]
