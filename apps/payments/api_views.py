from django.shortcuts import get_object_or_404
from rest_framework import generics, mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.permissions import IsAccountant, IsSuperAdmin
from apps.orders.models import Order

from . import services
from .models import PaymentTransaction, SavedPaymentMethod, WalletTransaction
from .serializers import (
    AddMoneySerializer,
    AttachPaymentMethodSerializer,
    PaymentTransactionSerializer,
    SavedPaymentMethodSerializer,
    WalletSerializer,
    WalletTransactionSerializer,
)
from .services import stripe as stripe_gateway

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
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "payment"

    def post(self, request):
        serializer = AddMoneySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        wallet = services.credit_wallet(
            request.user, serializer.validated_data["amount"], reason=serializer.validated_data["reason"]
        )
        return Response(WalletSerializer(wallet).data)


class RefundOrderToWalletView(APIView):
    permission_classes = [permissions.IsAuthenticated, CAN_REFUND]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "payment"

    def post(self, request, order_id):
        order = get_object_or_404(Order, pk=order_id)
        try:
            services.refund_order_to_wallet(order)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response({"detail": f"Refunded {order.total_amount} to {order.customer.email}'s wallet."})


class RefundStripePaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated, CAN_REFUND]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "payment"

    def post(self, request, order_id):
        order = get_object_or_404(Order, pk=order_id)
        try:
            stripe_gateway.refund_payment_intent(order)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response({"detail": f"Refunded {order.total_amount} to the original Stripe payment method."})


class MyPaymentTransactionsView(generics.ListAPIView):
    serializer_class = PaymentTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return PaymentTransaction.objects.filter(order__customer=self.request.user)


class SavedPaymentMethodViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet
):
    serializer_class = SavedPaymentMethodSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_throttles(self):
        if self.action in ("setup_intent", "attach"):
            self.throttle_scope = "payment"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def get_queryset(self):
        return SavedPaymentMethod.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        services.delete_payment_method(instance)

    @action(detail=True, methods=["post"], url_path="set-default")
    def set_default(self, request, pk=None):
        payment_method = services.set_default_payment_method(self.get_object())
        return Response(self.get_serializer(payment_method).data)

    @action(detail=False, methods=["post"], url_path="setup-intent")
    def setup_intent(self, request):
        """Returns a client_secret the frontend uses with Stripe.js/Elements to collect a
        new card without it ever touching our servers. Call attach/ with the resulting
        payment_method_id once Stripe confirms the SetupIntent."""
        intent = stripe_gateway.create_setup_intent(request.user)
        return Response({"client_secret": intent.client_secret})

    @action(detail=False, methods=["post"], url_path="attach")
    def attach(self, request):
        serializer = AttachPaymentMethodSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment_method = stripe_gateway.attach_payment_method(
            request.user,
            serializer.validated_data["payment_method_id"],
            is_default=serializer.validated_data["is_default"],
        )
        return Response(self.get_serializer(payment_method).data, status=201)
