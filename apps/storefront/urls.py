from django.urls import path

from . import views

app_name = "storefront"

urlpatterns = [
    path("", views.home, name="home"),
    path("products/", views.product_list, name="product_list"),
    path("products/<int:pk>/", views.product_detail, name="product_detail"),
    path("cart/", views.cart, name="cart"),
    path("wishlist/", views.wishlist, name="wishlist"),
    path("checkout/", views.checkout, name="checkout"),
    path("checkout/success/", views.order_success, name="order_success"),
    path("account/", views.account_dashboard, name="account_dashboard"),
    path("orders/", views.order_list, name="order_list"),
    path("orders/<int:pk>/", views.order_detail, name="order_detail"),
    path("account/notifications/", views.notifications, name="notifications"),
    path("account/wallet/", views.wallet, name="wallet"),
    path("account/addresses/", views.addresses, name="addresses"),
    path("help/", views.help_center, name="help"),
]
