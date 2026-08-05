from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsSuperAdmin, IsVendor

from . import services
from .models import Store
from .serializers import (
    PublicStoreSerializer,
    StoreAdminListSerializer,
    StoreRejectSerializer,
    StoreSerializer,
    VendorRegisterSerializer,
)


class VendorRegisterView(generics.CreateAPIView):
    serializer_class = VendorRegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        store = serializer.save()
        return Response(StoreSerializer(store).data, status=status.HTTP_201_CREATED)


class PublicStoreDetailView(generics.RetrieveAPIView):
    serializer_class = PublicStoreSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "slug"
    queryset = Store.objects.filter(status=Store.Status.APPROVED)


class MyStoreView(generics.RetrieveUpdateAPIView):
    serializer_class = StoreSerializer
    permission_classes = [permissions.IsAuthenticated, IsVendor]

    def get_object(self):
        return get_object_or_404(Store, owner=self.request.user)


class StoreResubmitView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsVendor]

    def post(self, request):
        store = get_object_or_404(Store, owner=request.user)
        try:
            services.resubmit_store(store)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(StoreSerializer(store).data)


class VendorApplicationListView(generics.ListAPIView):
    serializer_class = StoreAdminListSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]

    def get_queryset(self):
        queryset = Store.objects.all()
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        else:
            queryset = queryset.filter(status=Store.Status.PENDING)
        return queryset


class VendorApproveView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]

    def post(self, request, pk):
        store = get_object_or_404(Store, pk=pk)
        services.approve_store(store, request.user)
        return Response(StoreSerializer(store).data)


class VendorRejectView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]
    serializer_class = StoreRejectSerializer

    def post(self, request, pk):
        serializer = StoreRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        store = get_object_or_404(Store, pk=pk)
        services.reject_store(store, request.user, serializer.validated_data["reason"])
        return Response(StoreSerializer(store).data)
