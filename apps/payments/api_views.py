from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAccountant, IsSuperAdmin
from apps.orders.models import Order

from . import services
from .models import PaymentTransaction, WalletTransaction
from .serializers import (
    AddMoneySerializer,
    PaymentTransactionSerializer,
    WalletSerializer,
    WalletTransactionSerializer,
)

CAN_REFUND = IsAccountant | IsSuperAdmin


class MyWalletView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        wallet = services.get_or_create_wallet(request.user)
        return Response(WalletSerializer(wallet).data)


class WalletTransactionListView(generics.ListAPIView):
    serializer_class = WalletTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        wallet = services.get_or_create_wallet(self.request.user)
        return WalletTransaction.objects.filter(wallet=wallet)


class AddMoneyView(APIView):
    """Simulates an instant successful top-up (no real gateway is wired up yet,
    same honesty as COD: no external dependency, but not a real money movement)."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = AddMoneySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        wallet = services.credit_wallet(
            request.user, serializer.validated_data["amount"], reason=serializer.validated_data["reason"]
        )
        return Response(WalletSerializer(wallet).data)


class RefundOrderToWalletView(APIView):
    permission_classes = [permissions.IsAuthenticated, CAN_REFUND]

    def post(self, request, order_id):
        order = get_object_or_404(Order, pk=order_id)
        try:
            services.refund_order_to_wallet(order)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response({"detail": f"Refunded {order.total_amount} to {order.customer.email}'s wallet."})


class MyPaymentTransactionsView(generics.ListAPIView):
    serializer_class = PaymentTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return PaymentTransaction.objects.filter(order__customer=self.request.user)
