from django.urls import path
from rest_framework.routers import DefaultRouter

from . import api_views, webhook_views

app_name = "payments_api"

router = DefaultRouter()
router.register("payment-methods", api_views.SavedPaymentMethodViewSet, basename="payment-method")

urlpatterns = [
    path("wallet/", api_views.MyWalletView.as_view(), name="wallet"),
    path("wallet/transactions/", api_views.WalletTransactionListView.as_view(), name="wallet-transactions"),
    path("wallet/add-money/", api_views.AddMoneyView.as_view(), name="wallet-add-money"),
    path(
        "orders/<int:order_id>/refund-to-wallet/",
        api_views.RefundOrderToWalletView.as_view(),
        name="refund-to-wallet",
    ),
    path(
        "orders/<int:order_id>/refund-stripe/",
        api_views.RefundStripePaymentView.as_view(),
        name="refund-stripe",
    ),
    path("transactions/", api_views.MyPaymentTransactionsView.as_view(), name="my-transactions"),
    path("webhooks/stripe/", webhook_views.stripe_webhook, name="stripe-webhook"),
    path("callbacks/jazzcash/", webhook_views.jazzcash_callback, name="jazzcash-callback"),
    path("callbacks/easypaisa/", webhook_views.easypaisa_callback, name="easypaisa-callback"),
] + router.urls
