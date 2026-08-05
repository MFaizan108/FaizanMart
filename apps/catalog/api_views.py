from django.core.cache import cache
from django.db.models import Q
from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsVendor
from apps.vendors.models import Store

from . import cache as catalog_cache
from . import search as search_services
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

    def _is_public_unfiltered_request(self, request):
        user = request.user
        is_admin = user.is_authenticated and user.role == "super_admin"
        return not is_admin and "parent" not in request.query_params

    def list(self, request, *args, **kwargs):
        # Only the common "public, no filter" case is cached — the homepage category nav.
        if self._is_public_unfiltered_request(request):
            cached = cache.get(catalog_cache.PUBLIC_CATEGORY_LIST_KEY)
            if cached is not None:
                return Response(cached)
            response = super().list(request, *args, **kwargs)
            cache.set(catalog_cache.PUBLIC_CATEGORY_LIST_KEY, response.data, catalog_cache.CACHE_TTL)
            return response
        return super().list(request, *args, **kwargs)


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
    permission_classes = [IsSuperAdminOrReadOnly]


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
            queryset = queryset.filter(Q(status=Product.Status.PUBLISHED) | Q(store=user.store))
        else:
            queryset = queryset.filter(status=Product.Status.PUBLISHED)
        store_id = self.request.query_params.get("store")
        if store_id:
            queryset = queryset.filter(store_id=store_id)
        return queryset

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

    def retrieve(self, request, *args, **kwargs):
        # Only the plain published-product view is cached; a vendor viewing their own
        # possibly-unpublished product always hits the database, since that response can
        # differ (draft data) from what the cached, public-eyes version would return.
        pk = kwargs["pk"]
        cache_key = catalog_cache.product_detail_key(pk)
        if not (request.user.is_authenticated and hasattr(request.user, "store")):
            cached = cache.get(cache_key)
            if cached is not None:
                return Response(cached)
        response = super().retrieve(request, *args, **kwargs)
        if not (request.user.is_authenticated and hasattr(request.user, "store")):
            cache.set(cache_key, response.data, catalog_cache.CACHE_TTL)
        return response


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


class ProductSearchView(APIView):
    """Elasticsearch-backed product search: full-text (with typo-tolerant fuzzy matching and
    a "did you mean" suggestion), filters, and a lightweight smart-query parser that pulls
    brand/category out of free text (e.g. "nike shoes" -> brand=Nike, text="shoes")."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        params = request.query_params

        def _decimal(name):
            value = params.get(name)
            return value if value not in (None, "") else None

        try:
            page = max(int(params.get("page", 1)), 1)
            page_size = min(max(int(params.get("page_size", 20)), 1), 100)
        except ValueError:
            return Response({"detail": "page and page_size must be integers."}, status=400)

        store_param = params.get("store")
        if store_param:
            try:
                int(store_param)
            except ValueError:
                return Response({"detail": "store must be an integer."}, status=400)

        results = search_services.search_products(
            query=params.get("q", ""),
            category=params.get("category"),
            brand=params.get("brand"),
            store=store_param,
            min_price=_decimal("min_price"),
            max_price=_decimal("max_price"),
            min_rating=_decimal("min_rating"),
            in_stock_only=params.get("in_stock") == "true",
            sort=params.get("sort"),
            page=page,
            page_size=page_size,
        )
        return Response(results)
