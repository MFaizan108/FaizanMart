from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import Order
from .serializers import CancelSerializer, CheckoutSerializer, OrderSerializer, TransitionSerializer


def _is_staff_order_role(user):
    return user.is_authenticated and user.role in ("warehouse_manager", "super_admin")


class CheckoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            orders = services.place_order(user=request.user, order_fields=serializer.validated_data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(OrderSerializer(orders, many=True).data, status=201)


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
