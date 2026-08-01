from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsSuperAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == "super_admin"
        )


class HasRole(BasePermission):
    """Base class for role-gated permissions. Subclass and set `role`."""

    role = None

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == self.role
        )


class IsSuperAdmin(HasRole):
    role = "super_admin"


class IsVendor(HasRole):
    role = "vendor"


class IsCustomer(HasRole):
    role = "customer"


class IsWarehouseManager(HasRole):
    role = "warehouse_manager"


class IsDeliveryBoy(HasRole):
    role = "delivery_boy"


class IsSupportStaff(HasRole):
    role = "support_staff"


class IsAccountant(HasRole):
    role = "accountant"
