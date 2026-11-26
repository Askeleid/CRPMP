from django.db import transaction
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from workspace.models import GroupMembership, Paper, ResearchGroup
from workspace.permissions import IsGroupMember
from workspace.serializers import (
    HealthCheckSerializer,
    PaperSerializer,
    ResearchGroupSerializer,
)
from workspace.services import filter_papers_queryset


class HealthCheckView(APIView):
    """Health-check endpoint for verifying service availability."""

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Health Check",
        description="Returns the operational status of the API service.",
        responses={200: HealthCheckSerializer},
        tags=["Health"],
    )
    def get(self, request: Request) -> Response:
        """Return HTTP 200 with the current service status."""
        return Response({"status": "ok"}, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(
        summary="List Research Groups",
        description="List research groups the authenticated user belongs to.",
        tags=["Groups"],
    ),
    create=extend_schema(
        summary="Create Research Group",
        description="Create a new research group and assign the creator as ADMIN.",
        tags=["Groups"],
    ),
    retrieve=extend_schema(
        summary="Retrieve Research Group",
        description="Retrieve details for a research group the user belongs to.",
        tags=["Groups"],
    ),
    update=extend_schema(
        summary="Update Research Group",
        description="Update a research group the user belongs to.",
        tags=["Groups"],
    ),
    partial_update=extend_schema(
        summary="Partially Update Research Group",
        description="Partially update a research group the user belongs to.",
        tags=["Groups"],
    ),
    destroy=extend_schema(
        summary="Delete Research Group",
        description="Delete a research group the user belongs to.",
        tags=["Groups"],
    ),
)
class ResearchGroupViewSet(viewsets.ModelViewSet):
    """REST API endpoints for managing ResearchGroups."""

    serializer_class = ResearchGroupSerializer
    permission_classes = [IsAuthenticated, IsGroupMember]

    def get_queryset(self):
        base_qs = ResearchGroup.objects.order_by("-created_at")
        if self.action == "list":
            return base_qs.filter(memberships__user=self.request.user).distinct()
        return base_qs

    def perform_create(self, serializer):
        with transaction.atomic():
            group = serializer.save(created_by=self.request.user)
            GroupMembership.objects.create(
                group=group,
                user=self.request.user,
                role=GroupMembership.Role.ADMIN,
            )


@extend_schema_view(
    list=extend_schema(
        summary="List Papers",
        description=(
            "List papers across groups the authenticated user belongs to, "
            "with optional keyword search, tag, year, and group filtering."
        ),
        parameters=[
            OpenApiParameter(
                name="search",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter papers by keyword in title or authors.",
                required=False,
            ),
            OpenApiParameter(
                name="tag",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter papers by exact tag name (case-insensitive).",
                required=False,
            ),
            OpenApiParameter(
                name="year",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Filter papers by publication year.",
                required=False,
            ),
            OpenApiParameter(
                name="group",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Filter papers by research group ID.",
                required=False,
            ),
        ],
        tags=["Papers"],
    ),
    create=extend_schema(
        summary="Create Paper",
        description="Add a new paper with optional tags to a research group.",
        tags=["Papers"],
    ),
    retrieve=extend_schema(
        summary="Retrieve Paper",
        description="Retrieve a paper belonging to one of the user's research groups.",
        tags=["Papers"],
    ),
    update=extend_schema(
        summary="Update Paper",
        description="Update a paper belonging to one of the user's research groups.",
        tags=["Papers"],
    ),
    partial_update=extend_schema(
        summary="Partially Update Paper",
        description="Partially update a paper belonging to one of the user's research groups.",
        tags=["Papers"],
    ),
    destroy=extend_schema(
        summary="Delete Paper",
        description="Delete a paper belonging to one of the user's research groups.",
        tags=["Papers"],
    ),
)
class PaperViewSet(viewsets.ModelViewSet):
    """REST API endpoints for managing research Papers."""

    serializer_class = PaperSerializer
    permission_classes = [IsAuthenticated, IsGroupMember]

    def get_queryset(self):
        base_qs = (
            Paper.objects.select_related("group", "added_by")
            .prefetch_related("tags")
            .order_by("-created_at")
        )
        if self.action == "list":
            user_papers = base_qs.filter(
                group__memberships__user=self.request.user
            ).distinct()
            return filter_papers_queryset(
                user_papers,
                search=self.request.query_params.get("search"),
                tag=self.request.query_params.get("tag"),
                year=self.request.query_params.get("year"),
                group_id=self.request.query_params.get("group"),
            )
        return base_qs

    def _ensure_group_membership(self, group: ResearchGroup) -> None:
        if not GroupMembership.objects.filter(
            group=group, user=self.request.user
        ).exists():
            raise PermissionDenied("You must be a member of this group to add papers.")

    def perform_create(self, serializer):
        self._ensure_group_membership(serializer.validated_data["group"])
        serializer.save(added_by=self.request.user)

    def perform_update(self, serializer):
        target_group = serializer.validated_data.get(
            "group", serializer.instance.group
        )
        self._ensure_group_membership(target_group)
        serializer.save()
