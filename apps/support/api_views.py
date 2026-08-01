from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from . import services
from .models import FAQ, Ticket
from .serializers import (
    AddMessageSerializer,
    FAQSerializer,
    TicketCreateSerializer,
    TicketSerializer,
    TicketStatusSerializer,
)


def _is_support_staff(user):
    return user.is_authenticated and user.role in ("support_staff", "super_admin")


class TicketViewSet(viewsets.ModelViewSet):
    serializer_class = TicketSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        queryset = Ticket.objects.select_related("customer").prefetch_related("messages")
        if _is_support_staff(self.request.user):
            return queryset
        return queryset.filter(customer=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = TicketCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = services.create_ticket(customer=request.user, **serializer.validated_data)
        return Response(TicketSerializer(ticket).data, status=201)

    @action(detail=True, methods=["post"])
    def reply(self, request, pk=None):
        ticket = self.get_object()
        if not (_is_support_staff(request.user) or ticket.customer_id == request.user.id):
            raise PermissionDenied("You cannot reply to this ticket.")
        serializer = AddMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.add_message(ticket, request.user, serializer.validated_data["message"])
        # get_queryset() prefetches "messages"; refresh_from_db() drops that cache so the
        # message just added is actually included in the response instead of the stale prefetch.
        ticket.refresh_from_db()
        return Response(TicketSerializer(ticket).data)

    @action(detail=True, methods=["post"])
    def set_status(self, request, pk=None):
        ticket = self.get_object()
        if not _is_support_staff(request.user):
            raise PermissionDenied("Only support staff can change ticket status.")
        serializer = TicketStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.update_status(ticket, serializer.validated_data["status"])
        return Response(TicketSerializer(ticket).data)


class FAQViewSet(viewsets.ModelViewSet):
    serializer_class = FAQSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        queryset = FAQ.objects.all()
        user = self.request.user
        if not (user.is_authenticated and _is_support_staff(user)):
            queryset = queryset.filter(is_published=True)
        return queryset

    def perform_create(self, serializer):
        if not _is_support_staff(self.request.user):
            raise PermissionDenied("Only support staff can manage FAQs.")
        serializer.save()

    def perform_update(self, serializer):
        if not _is_support_staff(self.request.user):
            raise PermissionDenied("Only support staff can manage FAQs.")
        serializer.save()

    def perform_destroy(self, instance):
        if not _is_support_staff(self.request.user):
            raise PermissionDenied("Only support staff can manage FAQs.")
        instance.delete()
