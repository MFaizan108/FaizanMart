from django.urls import path

from . import api_views

app_name = "payments_api"

urlpatterns = [
    path("wallet/", api_views.MyWalletView.as_view(), name="wallet"),
    path("wallet/transactions/", api_views.WalletTransactionListView.as_view(), name="wallet-transactions"),
    path("wallet/add-money/", api_views.AddMoneyView.as_view(), name="wallet-add-money"),
    path(
        "orders/<int:order_id>/refund-to-wallet/",
        api_views.RefundOrderToWalletView.as_view(),
        name="refund-to-wallet",
    ),
    path("transactions/", api_views.MyPaymentTransactionsView.as_view(), name="my-transactions"),
]
