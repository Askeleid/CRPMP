from rest_framework import serializers


class HealthCheckSerializer(serializers.Serializer):
    """Serializer representing the API health-check response."""

    status = serializers.CharField(help_text="Service health status indicator.")
