from django.db.models import Q
from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.core.permissions import IsVendor
from apps.vendors.models import Store

from .models import Brand, Category, Product, ProductImage, ProductSpecification, ProductVariant, Tag
from .permissions import IsProductOwnerOrReadOnly, IsSuperAdminOrReadOnly
from .serializers import (
    BrandSerializer,
    CategorySerializer,
    ProductImageSerializer,
    ProductReadSerializer,
    ProductSpecificationSerializer,
    ProductVariantSerializer,
    ProductWriteSerializer,
    TagSerializer,
)


class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [IsSuperAdminOrReadOnly]

    def get_queryset(self):
        queryset = Category.objects.all()
        user = self.request.user
        if not (user.is_authenticated and user.role == "super_admin"):
            queryset = queryset.filter(is_active=True)
        parent_id = self.request.query_params.get("parent")
        if parent_id is not None:
            queryset = queryset.filter(parent_id=parent_id or None)
        return queryset


class BrandViewSet(viewsets.ModelViewSet):
    serializer_class = BrandSerializer
    permission_classes = [IsSuperAdminOrReadOnly]

    def get_queryset(self):
        queryset = Brand.objects.all()
        user = self.request.user
        if not (user.is_authenticated and user.role == "super_admin"):
            queryset = queryset.filter(is_active=True)
        return queryset


class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class ProductViewSet(viewsets.ModelViewSet):
    permission_classes = [IsProductOwnerOrReadOnly]

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return ProductReadSerializer
        return ProductWriteSerializer

    def get_queryset(self):
        queryset = Product.objects.select_related("store", "category", "brand").prefetch_related(
            "tags", "images", "variants", "specifications"
        )
        user = self.request.user
        if user.is_authenticated and hasattr(user, "store"):
            return queryset.filter(Q(status=Product.Status.PUBLISHED) | Q(store=user.store))
        return queryset.filter(status=Product.Status.PUBLISHED)

    def _require_approved_store(self, user):
        store = getattr(user, "store", None)
        if store is None or store.status != Store.Status.APPROVED:
            raise PermissionDenied("You need an approved store to manage products.")
        return store

    def perform_create(self, serializer):
        store = self._require_approved_store(self.request.user)
        serializer.save(store=store)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        output = ProductReadSerializer(serializer.instance, context=self.get_serializer_context())
        headers = self.get_success_headers(output.data)
        return Response(output.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        output = ProductReadSerializer(serializer.instance, context=self.get_serializer_context())
        return Response(output.data)


class VendorScopedChildViewSet(viewsets.ModelViewSet):
    """Base for image/variant/specification viewsets: scoped to the caller's own products."""

    permission_classes = [permissions.IsAuthenticated, IsVendor, IsProductOwnerOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        store = getattr(user, "store", None)
        if store is None:
            return self.queryset_model.objects.none()
        return self.queryset_model.objects.filter(product__store=store)


class ProductImageViewSet(VendorScopedChildViewSet):
    queryset_model = ProductImage
    serializer_class = ProductImageSerializer


class ProductVariantViewSet(VendorScopedChildViewSet):
    queryset_model = ProductVariant
    serializer_class = ProductVariantSerializer


class ProductSpecificationViewSet(VendorScopedChildViewSet):
    queryset_model = ProductSpecification
    serializer_class = ProductSpecificationSerializer
