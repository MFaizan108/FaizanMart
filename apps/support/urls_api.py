from rest_framework.routers import DefaultRouter

from . import api_views

app_name = "support_api"

router = DefaultRouter()
router.register("tickets", api_views.TicketViewSet, basename="ticket")
router.register("faq", api_views.FAQViewSet, basename="faq")

urlpatterns = router.urls
