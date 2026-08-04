from rest_framework import generics, permissions

from .models import AuditLog
from .permissions import IsSuperAdmin
from .serializers import AuditLogSerializer


class AuditLogListView(generics.ListAPIView):
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]
    queryset = AuditLog.objects.select_related("user")

    def get_queryset(self):
        queryset = super().get_queryset()
        model_name = self.request.query_params.get("model_name")
        object_id = self.request.query_params.get("object_id")
        if model_name:
            queryset = queryset.filter(model_name=model_name)
        if object_id:
            queryset = queryset.filter(object_id=object_id)
        return queryset
