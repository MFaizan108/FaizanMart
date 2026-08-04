from django.urls import path
from rest_framework.routers import DefaultRouter

from . import api_views

app_name = "sitesettings_api"

router = DefaultRouter()
router.register("email-templates", api_views.EmailTemplateViewSet, basename="email-template")

urlpatterns = [
    path("", api_views.SiteSettingsView.as_view(), name="settings"),
] + router.urls
