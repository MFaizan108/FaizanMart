from django.urls import path

from . import api_views

app_name = "core_api"

urlpatterns = [
    path("audit-logs/", api_views.AuditLogListView.as_view(), name="audit-log-list"),
]
