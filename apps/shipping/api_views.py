from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.core.permissions import IsSuperAdminOrReadOnly

from . import services
from .models import Courier, Shipment
from .serializers import CourierSerializer, ShipmentSerializer, ShipmentStatusUpdateSerializer


def _is_staff_role(user):
    return user.is_authenticated and user.role in ("warehouse_manager", "super_admin")


class CourierViewSet(viewsets.ModelViewSet):
    queryset = Courier.objects.all()
    serializer_class = CourierSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperAdminOrReadOnly]


class ShipmentViewSet(viewsets.ModelViewSet):
    serializer_class = ShipmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Shipment.objects.select_related("order", "courier")
        user = self.request.user
        if _is_staff_role(user):
            return queryset
        if hasattr(user, "store"):
            return queryset.filter(order__store=user.store)
        return queryset.filter(order__customer=user)

    def _can_manage(self, request, order):
        user = request.user
        if _is_staff_role(user):
            return True
        return hasattr(user, "store") and order.store_id == user.store.id

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.validated_data["order"]
        if not self._can_manage(request, order):
            raise PermissionDenied("You cannot create a shipment for this order.")
        try:
            shipment = services.create_shipment(
                order, serializer.validated_data["courier"], serializer.validated_data.get("tracking_number", "")
            )
        except ValueError as exc:
            raise ValidationError(str(exc))
        return Response(ShipmentSerializer(shipment).data, status=201)

    @action(detail=True, methods=["post"])
    def update_status(self, request, pk=None):
        shipment = self.get_object()
        if not self._can_manage(request, shipment.order):
            raise PermissionDenied("You cannot update this shipment.")
        serializer = ShipmentStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.update_shipment_status(shipment, serializer.validated_data["status"])
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(ShipmentSerializer(shipment).data)
