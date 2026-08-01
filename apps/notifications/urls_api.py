from rest_framework.routers import DefaultRouter

from . import api_views

app_name = "notifications_api"

router = DefaultRouter()
router.register("", api_views.NotificationViewSet, basename="notification")

urlpatterns = router.urls
