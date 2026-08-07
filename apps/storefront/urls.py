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
    path("account/payment-methods/", views.payment_methods, name="payment_methods"),
    path("account/reviews/", views.my_reviews, name="my_reviews"),
    path("account/returns/", views.returns, name="returns"),
    path("account/messages/", views.messages_list, name="messages_list"),
    path("account/messages/<int:pk>/", views.message_thread, name="message_thread"),
    path("compare/", views.compare, name="compare"),
    path("about/", views.about, name="about"),
    path("careers/", views.careers, name="careers"),
    path("help/", views.help_center, name="help"),
    path("store/<slug:slug>/", views.seller_storefront, name="seller_storefront"),
    path("sell/", views.sell_with_us, name="sell_with_us"),
    path("seller/", views.seller_dashboard, name="seller_dashboard"),
    path("seller/products/", views.seller_products, name="seller_products"),
    path("seller/orders/", views.seller_orders, name="seller_orders"),
    path("seller/store/", views.seller_store_settings, name="seller_store_settings"),
    path("staff/review/", views.admin_review, name="admin_review"),
]
