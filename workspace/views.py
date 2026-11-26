from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from workspace.forms import (
    AddMemberForm,
    ExperimentLogForm,
    PaperForm,
    ResearchGroupForm,
    ResearchTaskForm,
)
from workspace.models import GroupMembership, Paper, ResearchGroup, ResearchTask, Tag
from workspace.patterns.citations import (
    CITATION_FORMATS,
    CitationExporter,
    get_citation_strategy,
)
from workspace.services import (
    assign_tags_to_paper,
    create_group_with_admin,
    filter_papers_queryset,
    is_group_member,
)

User = get_user_model()


def register_view(request):
    """Register a new user account and log them in."""
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Account created successfully.")
            return redirect("dashboard")
    else:
        form = UserCreationForm()

    return render(request, "registration/register.html", {"form": form})


@login_required
def dashboard_view(request):
    """Display the logged-in user's research groups and handle group creation."""
    if request.method == "POST":
        form = ResearchGroupForm(request.POST)
        if form.is_valid():
            group = create_group_with_admin(
                name=form.cleaned_data["name"],
                description=form.cleaned_data["description"],
                user=request.user,
            )
            messages.success(request, f"Created research group '{group.name}'.")
            return redirect("dashboard")
    else:
        form = ResearchGroupForm()

    groups = (
        ResearchGroup.objects.filter(memberships__user=request.user)
        .distinct()
        .order_by("-created_at")
    )
    return render(
        request,
        "workspace/dashboard.html",
        {"groups": groups, "form": form},
    )


def _handle_add_member(request, group: ResearchGroup, is_admin: bool):
    """Process an add-member form submission for a research group."""
    if not is_admin:
        return None, HttpResponseForbidden("Only group admins can add members.")

    member_form = AddMemberForm(request.POST)
    if member_form.is_valid():
        username = member_form.cleaned_data["username"].strip()
        target_user = User.objects.filter(username=username).first()
        if target_user is None:
            member_form.add_error("username", "No user found with this username.")
        elif GroupMembership.objects.filter(group=group, user=target_user).exists():
            member_form.add_error(
                "username", "This user is already a member of the group."
            )
        else:
            GroupMembership.objects.create(
                group=group,
                user=target_user,
                role=GroupMembership.Role.MEMBER,
            )
            messages.success(request, f"Added '{target_user.username}' to {group.name}.")
            return member_form, redirect("group-detail", pk=group.pk)

    return member_form, None


def _handle_add_task(request, group: ResearchGroup):
    """Process creation of a ResearchTask inside a research group."""
    task_form = ResearchTaskForm(request.POST, group=group)
    if task_form.is_valid():
        task = task_form.save(commit=False)
        task.group = group
        task.save()
        messages.success(request, f"Added task '{task.title}'.")
        return task_form, redirect("group-detail", pk=group.pk)
    return task_form, None


def _handle_update_task_status(request, group: ResearchGroup):
    """Update the status of an existing ResearchTask within the group."""
    task = get_object_or_404(ResearchTask, pk=request.POST.get("task_id"), group=group)
    new_status = request.POST.get("status", "").strip().upper()
    if new_status in ResearchTask.Status.values:
        task.status = new_status
        task.save(update_fields=["status"])
        messages.success(request, f"Updated '{task.title}' to {task.get_status_display()}.")
    else:
        messages.error(request, "Invalid task status selected.")
    return redirect("group-detail", pk=group.pk)


@login_required
def group_detail_view(request, pk: int):
    """Display a research group's members, tasks, and searchable papers."""
    group = get_object_or_404(ResearchGroup, pk=pk)
    membership = GroupMembership.objects.filter(group=group, user=request.user).first()
    if membership is None:
        return HttpResponseForbidden("You are not a member of this research group.")

    is_admin = membership.role == GroupMembership.Role.ADMIN
    member_form = AddMemberForm()
    paper_form = PaperForm()
    task_form = ResearchTaskForm(group=group)

    if request.method == "POST":
        action = request.POST.get("action", "add_paper")
        if action == "add_member":
            member_form, response = _handle_add_member(request, group, is_admin)
            if response is not None:
                return response
        elif action == "add_task":
            task_form, response = _handle_add_task(request, group)
            if response is not None:
                return response
        elif action == "update_task_status":
            return _handle_update_task_status(request, group)
        else:
            paper_form = PaperForm(request.POST, request.FILES)
            if paper_form.is_valid():
                paper = paper_form.save(commit=False)
                paper.group = group
                paper.added_by = request.user
                paper.save()
                assign_tags_to_paper(paper, paper_form.cleaned_data.get("tags", ""))
                messages.success(request, f"Added paper '{paper.title}'.")
                return redirect("group-detail", pk=group.pk)

    search_query = request.GET.get("search", "").strip()
    tag_query = request.GET.get("tag", "").strip()
    year_query = request.GET.get("year", "").strip()

    papers = filter_papers_queryset(
        group.papers.select_related("added_by")
        .prefetch_related("tags")
        .order_by("-created_at"),
        search=search_query,
        tag=tag_query,
        year=year_query,
    )
    tasks = group.tasks.select_related("paper", "assigned_to").order_by("-created_at")
    memberships = group.memberships.select_related("user").order_by("role", "joined_at")
    available_tags = (
        Tag.objects.filter(papers__group=group).distinct().order_by("name")
    )

    return render(
        request,
        "workspace/group_detail.html",
        {
            "group": group,
            "membership": membership,
            "is_admin": is_admin,
            "memberships": memberships,
            "papers": papers,
            "tasks": tasks,
            "task_statuses": ResearchTask.Status.choices,
            "available_tags": available_tags,
            "member_form": member_form,
            "paper_form": paper_form,
            "task_form": task_form,
            "search_query": search_query,
            "tag_query": tag_query,
            "year_query": year_query,
        },
    )


@login_required
def paper_detail_view(request, paper_id: int):
    """Display paper metadata, tags, and experiment logs for group members."""
    paper = get_object_or_404(
        Paper.objects.select_related("group", "added_by").prefetch_related("tags"),
        pk=paper_id,
    )
    if not is_group_member(paper.group, request.user):
        return HttpResponseForbidden("You are not a member of this paper's group.")

    if request.method == "POST":
        log_form = ExperimentLogForm(request.POST)
        if log_form.is_valid():
            log = log_form.save(commit=False)
            log.paper = paper
            log.author = request.user
            log.save()
            messages.success(request, f"Logged experiment '{log.title}'.")
            return redirect("paper-detail", paper_id=paper.id)
    else:
        log_form = ExperimentLogForm()

    experiment_logs = paper.experiment_logs.select_related("author").order_by(
        "-logged_at"
    )

    cite_format = (request.GET.get("cite_format") or "bibtex").strip().lower()
    try:
        strategy = get_citation_strategy(cite_format)
    except ValueError:
        cite_format = "bibtex"
        strategy = get_citation_strategy("bibtex")
    citation = CitationExporter(strategy).export(paper)

    return render(
        request,
        "workspace/paper_detail.html",
        {
            "paper": paper,
            "experiment_logs": experiment_logs,
            "log_form": log_form,
            "cite_format": cite_format,
            "citation": citation,
            "citation_formats": CITATION_FORMATS,
        },
    )
