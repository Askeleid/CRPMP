from django.db import transaction
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from workspace.models import (
    ExperimentLog,
    GroupMembership,
    Notification,
    Paper,
    ResearchGroup,
    ResearchTask,
)
from workspace.patterns.citations import CitationExporter, get_citation_strategy
from workspace.permissions import IsGroupMember, IsNotificationRecipient
from workspace.serializers import (
    ExperimentLogSerializer,
    HealthCheckSerializer,
    NotificationSerializer,
    PaperCitationSerializer,
    PaperImportMetadataSerializer,
    PaperSerializer,
    ResearchGroupSerializer,
    ResearchTaskSerializer,
)
from workspace.services import (
    filter_experiment_logs_queryset,
    filter_papers_queryset,
    filter_tasks_queryset,
    import_paper_from_metadata,
    is_group_member,
    notify_paper_added,
    notify_task_assigned,
    notify_task_created,
)


class CitationContentNegotiation(DefaultContentNegotiation):
    """Select JSON renderer so ?format= can specify citation style instead."""

    def select_renderer(self, request, renderers, format_suffix=None):
        return (renderers[0], renderers[0].media_type)


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
        paper = serializer.save(added_by=self.request.user)
        notify_paper_added(paper, self.request.user)

    def perform_update(self, serializer):
        target_group = serializer.validated_data.get(
            "group", serializer.instance.group
        )
        self._ensure_group_membership(target_group)
        serializer.save()

    def get_content_negotiator(self):
        if getattr(self, "action", None) == "cite":
            return CitationContentNegotiation()
        return super().get_content_negotiator()

    @extend_schema(
        summary="Cite Paper",
        description="Format a paper citation in BibTeX, APA, or IEEE style.",
        parameters=[
            OpenApiParameter(
                name="format",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Citation format (bibtex, apa, or ieee). Defaults to bibtex.",
                required=False,
                enum=["bibtex", "apa", "ieee"],
            ),
        ],
        responses={200: PaperCitationSerializer},
        tags=["Papers"],
    )
    @action(detail=True, methods=["get"], url_path="cite")
    def cite(self, request: Request, pk=None) -> Response:
        """Return a formatted citation for the requested paper."""
        paper = self.get_object()
        raw_format = request.query_params.get("format")
        format_name = raw_format.strip().lower() if raw_format else "bibtex"
        try:
            strategy = get_citation_strategy(format_name)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        citation = CitationExporter(strategy).export(paper)
        return Response(
            {
                "paper_id": paper.id,
                "format": format_name,
                "citation": citation,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Import Paper from Metadata",
        description=(
            "Fetch paper metadata from arXiv or CrossRef and create a Paper "
            "inside the specified research group."
        ),
        request=PaperImportMetadataSerializer,
        responses={201: PaperSerializer},
        tags=["Papers"],
    )
    @action(detail=False, methods=["post"], url_path="import-metadata")
    def import_metadata(self, request: Request) -> Response:
        """Import a paper using an external metadata provider."""
        serializer = PaperImportMetadataSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        group = serializer.validated_data["group"]
        self._ensure_group_membership(group)

        try:
            paper = import_paper_from_metadata(
                group=group,
                added_by=request.user,
                source=serializer.validated_data["source"],
                identifier=serializer.validated_data["identifier"],
                tag_names=serializer.validated_data.get("tags", []),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        output = PaperSerializer(paper, context={"request": request})
        return Response(output.data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    list=extend_schema(
        summary="List Research Tasks",
        description=(
            "List tasks across groups the authenticated user belongs to, "
            "with optional group and status filtering."
        ),
        parameters=[
            OpenApiParameter(
                name="group",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Filter tasks by research group ID.",
                required=False,
            ),
            OpenApiParameter(
                name="status",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter tasks by status (TODO, IN_PROGRESS, DONE).",
                required=False,
            ),
        ],
        tags=["Tasks"],
    ),
    create=extend_schema(
        summary="Create Research Task",
        description="Create a new task inside a research group.",
        tags=["Tasks"],
    ),
    retrieve=extend_schema(
        summary="Retrieve Research Task",
        description="Retrieve a research task belonging to one of the user's groups.",
        tags=["Tasks"],
    ),
    update=extend_schema(
        summary="Update Research Task",
        description="Update a research task belonging to one of the user's groups.",
        tags=["Tasks"],
    ),
    partial_update=extend_schema(
        summary="Partially Update Research Task",
        description="Partially update a research task (e.g., status transition).",
        tags=["Tasks"],
    ),
    destroy=extend_schema(
        summary="Delete Research Task",
        description="Delete a research task belonging to one of the user's groups.",
        tags=["Tasks"],
    ),
)
class ResearchTaskViewSet(viewsets.ModelViewSet):
    """REST API endpoints for managing ResearchTasks."""

    serializer_class = ResearchTaskSerializer
    permission_classes = [IsAuthenticated, IsGroupMember]

    def get_queryset(self):
        base_qs = ResearchTask.objects.select_related(
            "group", "paper", "assigned_to"
        ).order_by("-created_at")
        if self.action == "list":
            user_tasks = base_qs.filter(
                group__memberships__user=self.request.user
            ).distinct()
            return filter_tasks_queryset(
                user_tasks,
                group_id=self.request.query_params.get("group"),
                status_value=self.request.query_params.get("status"),
            )
        return base_qs

    def _ensure_group_membership(self, group: ResearchGroup) -> None:
        if not is_group_member(group, self.request.user):
            raise PermissionDenied(
                "You must be a member of this group to manage tasks."
            )

    def perform_create(self, serializer):
        self._ensure_group_membership(serializer.validated_data["group"])
        task = serializer.save()
        notify_task_created(task, self.request.user)

    def perform_update(self, serializer):
        target_group = serializer.validated_data.get(
            "group", serializer.instance.group
        )
        self._ensure_group_membership(target_group)
        previous_assignee_id = serializer.instance.assigned_to_id
        task = serializer.save()
        if task.assigned_to_id and task.assigned_to_id != previous_assignee_id:
            notify_task_assigned(task, self.request.user)


@extend_schema_view(
    list=extend_schema(
        summary="List Experiment Logs",
        description=(
            "List experiment logs across groups the authenticated user belongs to, "
            "optionally filtered by paper."
        ),
        parameters=[
            OpenApiParameter(
                name="paper",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Filter experiment logs by paper ID.",
                required=False,
            ),
        ],
        tags=["Experiment Logs"],
    ),
    create=extend_schema(
        summary="Create Experiment Log",
        description="Log a new experiment entry against a paper.",
        tags=["Experiment Logs"],
    ),
    retrieve=extend_schema(
        summary="Retrieve Experiment Log",
        description="Retrieve an experiment log from a group the user belongs to.",
        tags=["Experiment Logs"],
    ),
    update=extend_schema(
        summary="Update Experiment Log",
        description="Update an experiment log from a group the user belongs to.",
        tags=["Experiment Logs"],
    ),
    partial_update=extend_schema(
        summary="Partially Update Experiment Log",
        description="Partially update an experiment log from a group the user belongs to.",
        tags=["Experiment Logs"],
    ),
    destroy=extend_schema(
        summary="Delete Experiment Log",
        description="Delete an experiment log from a group the user belongs to.",
        tags=["Experiment Logs"],
    ),
)
class ExperimentLogViewSet(viewsets.ModelViewSet):
    """REST API endpoints for managing ExperimentLogs."""

    serializer_class = ExperimentLogSerializer
    permission_classes = [IsAuthenticated, IsGroupMember]

    def get_queryset(self):
        base_qs = ExperimentLog.objects.select_related(
            "paper", "paper__group", "author"
        ).order_by("-logged_at")
        if self.action == "list":
            user_logs = base_qs.filter(
                paper__group__memberships__user=self.request.user
            ).distinct()
            return filter_experiment_logs_queryset(
                user_logs,
                paper_id=self.request.query_params.get("paper"),
            )
        return base_qs

    def _ensure_paper_group_membership(self, paper: Paper) -> None:
        if not is_group_member(paper.group, self.request.user):
            raise PermissionDenied(
                "You must be a member of this paper's group to log experiments."
            )

    def perform_create(self, serializer):
        self._ensure_paper_group_membership(serializer.validated_data["paper"])
        serializer.save(author=self.request.user)

    def perform_update(self, serializer):
        target_paper = serializer.validated_data.get(
            "paper", serializer.instance.paper
        )
        self._ensure_paper_group_membership(target_paper)
        serializer.save()


@extend_schema_view(
    list=extend_schema(
        summary="List Notifications",
        description="List in-app notifications for the authenticated user.",
        tags=["Notifications"],
    ),
    retrieve=extend_schema(
        summary="Retrieve Notification",
        description="Retrieve a specific notification belonging to the authenticated user.",
        tags=["Notifications"],
    ),
)
class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """REST API endpoints for reading and acknowledging user Notifications."""

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated, IsNotificationRecipient]

    def get_queryset(self):
        base_qs = Notification.objects.select_related("group").order_by("-created_at")
        if self.action == "list":
            return base_qs.filter(recipient=self.request.user)
        return base_qs

    @extend_schema(
        summary="Mark Notification as Read",
        description="Mark a specific notification as read.",
        request=None,
        responses={200: NotificationSerializer},
        tags=["Notifications"],
    )
    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request: Request, pk=None) -> Response:
        """Mark the target notification as read."""
        notification = self.get_object()
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=["is_read"])
        serializer = self.get_serializer(notification)
        return Response(serializer.data, status=status.HTTP_200_OK)
