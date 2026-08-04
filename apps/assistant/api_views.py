from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from . import services
from .serializers import AssistantQuerySerializer


class AssistantQueryView(APIView):
    """POST {"query": "laptop under 150000 for programming"} -> a grounded reply plus the
    real products it's based on. Public like product search — no account needed to ask."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "assistant"

    def post(self, request):
        serializer = AssistantQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = services.ask_shopping_assistant(serializer.validated_data["query"])
        return Response(result, status=status.HTTP_200_OK)
