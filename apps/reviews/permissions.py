from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsReviewOwnerOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return obj.customer_id == request.user.id or request.user.role == "super_admin"
