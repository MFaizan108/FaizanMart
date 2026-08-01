from django.urls import path

from . import api_views

app_name = "cart_api"

urlpatterns = [
    path("", api_views.CartDetailView.as_view(), name="detail"),
    path("items/", api_views.CartItemListView.as_view(), name="item-list"),
    path("items/<int:item_id>/", api_views.CartItemDetailView.as_view(), name="item-detail"),
    path("clear/", api_views.CartClearView.as_view(), name="clear"),
    path("merge/", api_views.CartMergeView.as_view(), name="merge"),
]
