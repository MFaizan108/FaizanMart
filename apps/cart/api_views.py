from django.shortcuts import get_object_or_404
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import CartItem
from .serializers import AddCartItemSerializer, CartSerializer, UpdateCartItemSerializer


def _cart_payload(cart):
    totals = services.cart_totals(cart)
    return {
        "id": cart.id,
        "guest_token": cart.guest_token,
        "items": cart.items.select_related("product", "variant"),
        "items_count": totals["items_count"],
        "subtotal": totals["subtotal"],
    }


class CartDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        cart, _ = services.resolve_cart(request)
        return Response(CartSerializer(_cart_payload(cart)).data)


class CartItemListView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        cart, _ = services.resolve_cart(request)
        serializer = AddCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.add_item(cart=cart, **serializer.validated_data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(CartSerializer(_cart_payload(cart)).data, status=201)


class CartItemDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    def _resolve(self, request, item_id):
        cart, _ = services.resolve_cart(request)
        item = get_object_or_404(CartItem, pk=item_id, cart=cart)
        return cart, item

    def patch(self, request, item_id):
        cart, item = self._resolve(request, item_id)
        serializer = UpdateCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.update_item_quantity(item, serializer.validated_data["quantity"])
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(CartSerializer(_cart_payload(cart)).data)

    def delete(self, request, item_id):
        cart, item = self._resolve(request, item_id)
        services.remove_item(item)
        return Response(CartSerializer(_cart_payload(cart)).data)


class CartClearView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        cart, _ = services.resolve_cart(request)
        services.clear_cart(cart)
        return Response(CartSerializer(_cart_payload(cart)).data)


class CartMergeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        guest_token = request.data.get("guest_token")
        if not guest_token:
            return Response({"detail": "guest_token is required."}, status=400)
        try:
            cart = services.merge_guest_cart(request.user, guest_token)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(CartSerializer(_cart_payload(cart)).data)
