from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.payments.services import easypaisa as easypaisa_gateway
from apps.payments.services import jazzcash as jazzcash_gateway
from apps.payments.services import stripe as stripe_gateway

from . import services
from .models import Order, ReturnRequest
from .serializers import (
    CancelSerializer,
    CheckoutSerializer,
    OrderSerializer,
    ReturnRequestRespondSerializer,
    ReturnRequestSerializer,
    TransitionSerializer,
)


def _is_staff_order_role(user):
    return user.is_authenticated and user.role in ("warehouse_manager", "super_admin")


class CheckoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "checkout"

    def post(self, request):
        serializer = CheckoutSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            orders = services.place_order(user=request.user, order_fields=serializer.validated_data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)

        payload = OrderSerializer(orders, many=True).data
        payment_method = orders[0].payment_method

        # None of these gateways are trusted to have paid yet: the frontend completes the
        # provider's flow (Stripe PaymentIntent confirmation / JazzCash & EasyPaisa hosted
        # checkout redirect), and only that provider's server-to-server callback/webhook
        # (verified below in webhook_views / callback_views) moves the order out of PENDING.
        if payment_method == Order.PaymentMethod.STRIPE:
            try:
                intent = stripe_gateway.create_payment_intent_for_orders(orders, request.user)
            except RuntimeError as exc:
                return Response({"detail": str(exc)}, status=503)
            return Response({"orders": payload, "client_secret": intent.client_secret}, status=201)

        if payment_method == Order.PaymentMethod.JAZZCASH:
            try:
                payment_request = jazzcash_gateway.build_payment_request(orders)
            except RuntimeError as exc:
                return Response({"detail": str(exc)}, status=503)
            return Response({"orders": payload, **payment_request}, status=201)

        if payment_method == Order.PaymentMethod.EASYPAISA:
            try:
                payment_request = easypaisa_gateway.build_payment_request(orders)
            except RuntimeError as exc:
                return Response({"detail": str(exc)}, status=503)
            return Response({"orders": payload, **payment_request}, status=201)

        return Response(payload, status=201)


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Order.objects.select_related("customer", "store").prefetch_related(
            "items", "status_history"
        )
        user = self.request.user
        if _is_staff_order_role(user):
            return queryset
        if hasattr(user, "store"):
            return queryset.filter(store=user.store)
        return queryset.filter(customer=user)

    def _can_manage(self, request, order):
        user = request.user
        if _is_staff_order_role(user):
            return True
        return hasattr(user, "store") and order.store_id == user.store.id

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        order = self.get_object()
        if not self._can_manage(request, order):
            raise PermissionDenied("You cannot manage this order.")
        serializer = TransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.transition_status(
                order,
                serializer.validated_data["status"],
                user=request.user,
                note=serializer.validated_data["note"],
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        order.refresh_from_db()
        return Response(OrderSerializer(order).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        order = self.get_object()
        can_cancel = order.customer_id == request.user.id or self._can_manage(request, order)
        if not can_cancel:
            raise PermissionDenied("You cannot cancel this order.")
        serializer = CancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.transition_status(
                order, Order.Status.CANCELLED, user=request.user, note=serializer.validated_data["reason"]
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        order.refresh_from_db()
        return Response(OrderSerializer(order).data)


class ReturnRequestViewSet(viewsets.ModelViewSet):
    """Customer-initiated return/refund requests for delivered orders.

    A request only records intent to return; approving it moves the order to
    RETURNED (services.transition_status already allows DELIVERED -> RETURNED).
    Issuing the actual refund stays a separate, deliberate staff action via the
    existing refund-to-wallet/refund-stripe endpoints in apps.payments.
    """

    serializer_class = ReturnRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        queryset = ReturnRequest.objects.select_related("order", "order__store", "order__customer")
        user = self.request.user
        if _is_staff_order_role(user):
            return queryset
        if hasattr(user, "store"):
            return queryset.filter(order__store=user.store)
        return queryset.filter(order__customer=user)

    def perform_create(self, serializer):
        order = serializer.validated_data["order"]
        if order.customer_id != self.request.user.id:
            raise PermissionDenied("You cannot request a return for an order that isn't yours.")
        if order.status != Order.Status.DELIVERED:
            raise ValidationError("Only delivered orders are eligible for a return.")
        if order.return_requests.filter(status=ReturnRequest.Status.REQUESTED).exists():
            raise ValidationError("A return request is already pending for this order.")
        serializer.save()

    def _can_manage(self, request, return_request):
        user = request.user
        if _is_staff_order_role(user):
            return True
        return hasattr(user, "store") and return_request.order.store_id == user.store.id

    @action(detail=True, methods=["post"])
    def respond(self, request, pk=None):
        return_request = self.get_object()
        if not self._can_manage(request, return_request):
            raise PermissionDenied("You cannot manage this return request.")
        if return_request.status != ReturnRequest.Status.REQUESTED:
            return Response({"detail": "This return request has already been resolved."}, status=400)

        serializer = ReturnRequestRespondSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data["status"]

        if new_status == ReturnRequest.Status.APPROVED:
            try:
                services.transition_status(return_request.order, Order.Status.RETURNED, user=request.user)
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=400)

        return_request.status = new_status
        return_request.staff_note = serializer.validated_data["staff_note"]
        return_request.save(update_fields=["status", "staff_note", "updated_at"])
        return Response(ReturnRequestSerializer(return_request).data)
