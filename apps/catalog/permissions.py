from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.core.permissions import IsSuperAdminOrReadOnly  # noqa: F401  (re-exported for callers)


class IsProductOwnerOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        # obj is a Product (has `store` directly) or a Product-child row (has `product.store`).
        store = obj.store if hasattr(obj, "store") else obj.product.store
        return store.owner_id == request.user.id
