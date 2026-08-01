from rest_framework import permissions, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import Coupon
from .permissions import IsCouponOwnerOrSuperAdmin
from .serializers import CouponSerializer, ValidateCouponSerializer


class CouponViewSet(viewsets.ModelViewSet):
    queryset = Coupon.objects.all()
    serializer_class = CouponSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsCouponOwnerOrSuperAdmin]

    def perform_create(self, serializer):
        user = self.request.user
        store = serializer.validated_data.get("store")
        if store is None:
            if user.role != "super_admin":
                raise PermissionDenied("Only a super admin can create platform-wide coupons.")
        elif not (user.role == "super_admin" or (hasattr(user, "store") and user.store.id == store.id)):
            raise PermissionDenied("You can only create coupons for your own store.")
        serializer.save()


class ValidateCouponView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ValidateCouponSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            coupon = services.validate_coupon(
                serializer.validated_data["code"], request.user, serializer.validated_data["subtotal"]
            )
        except ValueError as exc:
            return Response({"valid": False, "detail": str(exc)}, status=400)
        discount = services.compute_discount(coupon, serializer.validated_data["subtotal"])
        return Response({"valid": True, "discount_type": coupon.discount_type, "estimated_discount": discount})
