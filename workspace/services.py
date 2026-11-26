from collections.abc import Iterable

from django.db import transaction
from django.db.models import Q, QuerySet

from workspace.models import (
    ExperimentLog,
    GroupMembership,
    Paper,
    ResearchGroup,
    ResearchTask,
    Tag,
)
from workspace.patterns.metadata import get_metadata_adapter
from workspace.patterns.observers import get_default_publisher


def is_group_member(group: ResearchGroup, user) -> bool:
    """Return True if the user is a member of the given research group."""
    return GroupMembership.objects.filter(group=group, user=user).exists()


def create_group_with_admin(
    *, name: str, description: str, user
) -> ResearchGroup:
    """Create a ResearchGroup and enroll its creator as an ADMIN member."""
    with transaction.atomic():
        group = ResearchGroup.objects.create(
            name=name,
            description=description,
            created_by=user,
        )
        GroupMembership.objects.create(
            group=group,
            user=user,
            role=GroupMembership.Role.ADMIN,
        )
    return group


def parse_tag_names(raw_tags: str | Iterable[str]) -> list[str]:
    """Normalize a comma-separated string or iterable into unique lowercase tags."""
    if isinstance(raw_tags, str):
        candidates = raw_tags.split(",")
    else:
        candidates = raw_tags

    seen: set[str] = set()
    normalized: list[str] = []
    for item in candidates:
        name = str(item).strip().lower()
        if name and name not in seen:
            seen.add(name)
            normalized.append(name)
    return normalized


def assign_tags_to_paper(paper: Paper, raw_tags: str | Iterable[str]) -> None:
    """Resolve Tag records for normalized tag names and attach them to a paper."""
    tag_names = parse_tag_names(raw_tags)
    tag_objects = [Tag.objects.get_or_create(name=name)[0] for name in tag_names]
    paper.tags.set(tag_objects)


def filter_papers_queryset(
    queryset: QuerySet[Paper],
    *,
    search: str | None = None,
    tag: str | None = None,
    year: str | int | None = None,
    group_id: str | int | None = None,
) -> QuerySet[Paper]:
    """Filter a Paper queryset by search keyword, tag name, year, and group."""
    if search:
        term = search.strip()
        if term:
            queryset = queryset.filter(
                Q(title__icontains=term) | Q(authors__icontains=term)
            )

    if tag:
        tag_name = tag.strip().lower()
        if tag_name:
            queryset = queryset.filter(tags__name__iexact=tag_name).distinct()

    if year not in (None, ""):
        try:
            queryset = queryset.filter(year=int(year))
        except (TypeError, ValueError):
            pass

    if group_id not in (None, ""):
        try:
            queryset = queryset.filter(group_id=int(group_id))
        except (TypeError, ValueError):
            pass

    return queryset


def filter_tasks_queryset(
    queryset: QuerySet[ResearchTask],
    *,
    group_id: str | int | None = None,
    status_value: str | None = None,
) -> QuerySet[ResearchTask]:
    """Filter a ResearchTask queryset by group ID and status."""
    if group_id not in (None, ""):
        try:
            queryset = queryset.filter(group_id=int(group_id))
        except (TypeError, ValueError):
            pass

    if status_value:
        normalized_status = status_value.strip().upper()
        if normalized_status in ResearchTask.Status.values:
            queryset = queryset.filter(status=normalized_status)

    return queryset


def filter_experiment_logs_queryset(
    queryset: QuerySet[ExperimentLog],
    *,
    paper_id: str | int | None = None,
) -> QuerySet[ExperimentLog]:
    """Filter an ExperimentLog queryset by paper ID."""
    if paper_id not in (None, ""):
        try:
            queryset = queryset.filter(paper_id=int(paper_id))
        except (TypeError, ValueError):
            pass

    return queryset


def import_paper_from_metadata(
    group: ResearchGroup,
    added_by,
    source: str,
    identifier: str,
    tag_names: list[str] | None = None,
) -> Paper:
    """Fetch normalized metadata from an external source and create a Paper."""
    metadata = get_metadata_adapter(source).fetch(identifier)
    with transaction.atomic():
        paper = Paper.objects.create(
            group=group,
            added_by=added_by,
            title=metadata["title"],
            authors=metadata["authors"],
            year=metadata["year"],
            doi=metadata["doi"],
            arxiv_id=metadata["arxiv_id"],
            url=metadata["url"],
            abstract=metadata["abstract"],
        )
        if tag_names:
            assign_tags_to_paper(paper, tag_names)
    notify_paper_added(paper, added_by)
    return paper


def notify_paper_added(paper: Paper, actor) -> None:
    """Publish a notification event when a paper is added to a group."""
    actor_name = getattr(actor, "username", "Someone")
    message = f"{actor_name} added paper '{paper.title}' to {paper.group.name}."
    get_default_publisher().notify("paper_added", paper.group, actor, message)


def notify_task_created(task: ResearchTask, actor) -> None:
    """Publish a notification event when a research task is created."""
    actor_name = getattr(actor, "username", "Someone")
    if task.assigned_to is not None:
        message = (
            f"{actor_name} created task '{task.title}' "
            f"(assigned to {task.assigned_to.username}) in {task.group.name}."
        )
    else:
        message = f"{actor_name} created task '{task.title}' in {task.group.name}."
    get_default_publisher().notify("task_created", task.group, actor, message)


def notify_task_assigned(task: ResearchTask, actor) -> None:
    """Publish a notification event when a research task is assigned."""
    if task.assigned_to is None:
        return
    actor_name = getattr(actor, "username", "Someone")
    message = (
        f"{actor_name} assigned task '{task.title}' "
        f"to {task.assigned_to.username} in {task.group.name}."
    )
    get_default_publisher().notify("task_assigned", task.group, actor, message)
