from rest_framework import generics, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsSuperAdmin, IsSuperAdminOrReadOnly, IsWarehouseManager

from . import services
from .models import Courier, DeliveryAssignment, Shipment, ShippingRule
from .serializers import (
    CourierSerializer,
    DeliveryAssignCreateSerializer,
    DeliveryAssignmentSerializer,
    DeliveryStatusUpdateSerializer,
    ShipmentSerializer,
    ShipmentStatusUpdateSerializer,
    ShippingQuoteSerializer,
    ShippingRuleSerializer,
)

MANAGES_DELIVERY = IsWarehouseManager | IsSuperAdmin


def _is_staff_role(user):
    return user.is_authenticated and user.role in ("warehouse_manager", "super_admin")


class ShippingRuleViewSet(viewsets.ModelViewSet):
    queryset = ShippingRule.objects.select_related("store", "warehouse")
    serializer_class = ShippingRuleSerializer
    permission_classes = [IsSuperAdminOrReadOnly]


class ShippingQuoteView(APIView):
    """Lets the frontend preview a shipping cost before checkout (checkout itself always
    recomputes this server-side and never trusts a client-supplied shipping_cost)."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from apps.vendors.models import Store

        serializer = ShippingQuoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        store = Store.objects.filter(pk=data["store"]).first() if data["store"] else None

        cost = services.calculate_shipping_cost(
            country=data["country"], province=data["province"], city=data["city"],
            store=store, total_weight=data["weight"], order_amount=data["order_amount"],
        )
        return Response({"shipping_cost": cost if cost is not None else None, "matched": cost is not None})


class DeliveryAssignmentViewSet(viewsets.ModelViewSet):
    serializer_class = DeliveryAssignmentSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_permissions(self):
        if self.action == "create":
            return [permissions.IsAuthenticated(), MANAGES_DELIVERY()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        queryset = DeliveryAssignment.objects.select_related("order", "delivery_boy")
        user = self.request.user
        if _is_staff_role(user):
            return queryset
        if user.role == "delivery_boy":
            return queryset.filter(delivery_boy=user)
        return queryset.none()

    def create(self, request, *args, **kwargs):
        serializer = DeliveryAssignCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            assignment = services.assign_delivery(
                serializer.validated_data["order"], serializer.validated_data["delivery_boy"], assigned_by=request.user
            )
        except ValueError as exc:
            raise ValidationError(str(exc))
        return Response(DeliveryAssignmentSerializer(assignment).data, status=201)

    @action(detail=True, methods=["post"], url_path="update-status")
    def update_status(self, request, pk=None):
        assignment = self.get_object()
        if not (_is_staff_role(request.user) or assignment.delivery_boy_id == request.user.id):
            raise PermissionDenied("You cannot update this delivery.")
        serializer = DeliveryStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.update_delivery_status(
                assignment,
                serializer.validated_data["status"],
                user=request.user,
                failure_reason=serializer.validated_data["failure_reason"],
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(DeliveryAssignmentSerializer(assignment).data)


class MyDeliveriesView(generics.ListAPIView):
    """The delivery boy's dashboard: their assigned/in-progress/completed deliveries."""

    serializer_class = DeliveryAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = DeliveryAssignment.objects.filter(delivery_boy=self.request.user).select_related("order")
        status_param = self.request.query_params.get("status")
        if status_param:
            queryset = queryset.filter(status=status_param)
        return queryset


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
