from django.db.models import Sum
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Product
from apps.core.permissions import IsSuperAdmin, IsSuperAdminOrReadOnly, IsWarehouseManager

from . import services
from .models import InventoryLog, Stock, StockTransfer, Warehouse
from .serializers import (
    AdjustActionSerializer,
    InventoryLogSerializer,
    ReserveReleaseActionSerializer,
    RestockActionSerializer,
    StockSerializer,
    StockTransferSerializer,
    WarehouseSerializer,
)

MANAGES_INVENTORY = IsWarehouseManager | IsSuperAdmin


def _is_staff_inventory_role(user):
    return user.is_authenticated and user.role in ("warehouse_manager", "super_admin")


class WarehouseViewSet(viewsets.ModelViewSet):
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperAdminOrReadOnly]


class StockViewSet(viewsets.ModelViewSet):
    serializer_class = StockSerializer

    def get_permissions(self):
        if self.action == "list" or self.action == "retrieve":
            classes = [permissions.IsAuthenticated]
        else:
            classes = [permissions.IsAuthenticated, MANAGES_INVENTORY]
        return [permission() for permission in classes]

    def get_queryset(self):
        queryset = Stock.objects.select_related("product", "warehouse", "product__store")
        user = self.request.user
        if _is_staff_inventory_role(user):
            return queryset
        if hasattr(user, "store"):
            return queryset.filter(product__store=user.store)
        return queryset.none()

    @action(detail=True, methods=["post"])
    def restock(self, request, pk=None):
        stock = self.get_object()
        serializer = RestockActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.adjust_stock(
                product=stock.product,
                warehouse=stock.warehouse,
                delta=serializer.validated_data["quantity"],
                change_type=InventoryLog.ChangeType.RESTOCK,
                note=serializer.validated_data.get("note", ""),
                user=request.user,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        stock.refresh_from_db()
        return Response(StockSerializer(stock).data)

    @action(detail=True, methods=["post"])
    def adjust(self, request, pk=None):
        stock = self.get_object()
        serializer = AdjustActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.adjust_stock(
                product=stock.product,
                warehouse=stock.warehouse,
                delta=serializer.validated_data["delta"],
                change_type=InventoryLog.ChangeType.ADJUSTMENT,
                note=serializer.validated_data.get("note", ""),
                user=request.user,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        stock.refresh_from_db()
        return Response(StockSerializer(stock).data)

    @action(detail=True, methods=["post"])
    def reserve(self, request, pk=None):
        stock = self.get_object()
        serializer = ReserveReleaseActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.reserve_stock(
                product=stock.product,
                warehouse=stock.warehouse,
                quantity=serializer.validated_data["quantity"],
                note=serializer.validated_data.get("note", ""),
                user=request.user,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        stock.refresh_from_db()
        return Response(StockSerializer(stock).data)

    @action(detail=True, methods=["post"])
    def release(self, request, pk=None):
        stock = self.get_object()
        serializer = ReserveReleaseActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.release_stock(
                product=stock.product,
                warehouse=stock.warehouse,
                quantity=serializer.validated_data["quantity"],
                note=serializer.validated_data.get("note", ""),
                user=request.user,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        stock.refresh_from_db()
        return Response(StockSerializer(stock).data)


class TransferViewSet(viewsets.ModelViewSet):
    queryset = StockTransfer.objects.select_related("product", "from_warehouse", "to_warehouse")
    serializer_class = StockTransferSerializer
    permission_classes = [permissions.IsAuthenticated, MANAGES_INVENTORY]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            transfer = services.create_transfer(
                product=serializer.validated_data["product"],
                from_warehouse=serializer.validated_data["from_warehouse"],
                to_warehouse=serializer.validated_data["to_warehouse"],
                quantity=serializer.validated_data["quantity"],
                requested_by=request.user,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(StockTransferSerializer(transfer).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        transfer = self.get_object()
        try:
            services.complete_transfer(transfer, user=request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(StockTransferSerializer(transfer).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        transfer = self.get_object()
        try:
            services.cancel_transfer(transfer)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(StockTransferSerializer(transfer).data)


class InventoryLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = InventoryLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = InventoryLog.objects.select_related("product", "warehouse")
        user = self.request.user
        if _is_staff_inventory_role(user):
            return queryset
        if hasattr(user, "store"):
            return queryset.filter(product__store=user.store)
        return queryset.none()


class LowStockAlertView(generics.ListAPIView):
    serializer_class = StockSerializer
    permission_classes = [permissions.IsAuthenticated, MANAGES_INVENTORY]
    queryset = Stock.objects.low_stock().select_related("product", "warehouse")


class OutOfStockAlertView(generics.ListAPIView):
    serializer_class = StockSerializer
    permission_classes = [permissions.IsAuthenticated, MANAGES_INVENTORY]
    queryset = Stock.objects.out_of_stock().select_related("product", "warehouse")


class ProductStockDistributionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, product_id):
        product = get_object_or_404(Product, pk=product_id)
        user = request.user
        owns_product = hasattr(user, "store") and user.store.id == product.store_id
        if not (_is_staff_inventory_role(user) or owns_product):
            raise PermissionDenied("You do not have access to this product's stock.")
        stocks = Stock.objects.filter(product=product).select_related("warehouse")
        return Response(StockSerializer(stocks, many=True).data)


class WarehouseReportView(APIView):
    permission_classes = [permissions.IsAuthenticated, MANAGES_INVENTORY]

    def get(self, request, pk):
        warehouse = get_object_or_404(Warehouse, pk=pk)
        stocks = Stock.objects.filter(warehouse=warehouse)
        return Response(
            {
                "warehouse": WarehouseSerializer(warehouse).data,
                "total_products_stocked": stocks.count(),
                "total_quantity": stocks.aggregate(total=Sum("quantity"))["total"] or 0,
                "low_stock_count": stocks.low_stock().count(),
                "out_of_stock_count": stocks.out_of_stock().count(),
            }
        )
