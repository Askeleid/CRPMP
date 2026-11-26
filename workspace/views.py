from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from workspace.serializers import HealthCheckSerializer


class HealthCheckView(APIView):
    """Health-check endpoint for verifying service availability."""

    @extend_schema(
        summary="Health Check",
        description="Returns the operational status of the API service.",
        responses={200: HealthCheckSerializer},
        tags=["Health"],
    )
    def get(self, request: Request) -> Response:
        """Return HTTP 200 with the current service status."""
        return Response({"status": "ok"}, status=status.HTTP_200_OK)
