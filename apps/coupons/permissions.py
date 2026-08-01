from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsCouponOwnerOrSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if request.user.role == "super_admin":
            return True
        if obj.store_id is None:
            return False  # only super_admin manages platform-wide coupons
        return obj.store.owner_id == request.user.id
