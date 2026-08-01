from django.urls import path
from rest_framework.routers import DefaultRouter

from . import api_views

app_name = "reviews_api"

router = DefaultRouter()
router.register("reviews", api_views.ReviewViewSet, basename="review")

urlpatterns = [
    path("wishlist/", api_views.WishlistListView.as_view(), name="wishlist"),
    path("wishlist/toggle/", api_views.ToggleWishlistView.as_view(), name="wishlist-toggle"),
] + router.urls
