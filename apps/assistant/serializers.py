from rest_framework import serializers


class AssistantQuerySerializer(serializers.Serializer):
    query = serializers.CharField(max_length=500, allow_blank=False, trim_whitespace=True)
