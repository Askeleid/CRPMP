from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from workspace.forms import AddMemberForm, PaperForm, ResearchGroupForm
from workspace.models import GroupMembership, ResearchGroup, Tag
from workspace.services import (
    assign_tags_to_paper,
    create_group_with_admin,
    filter_papers_queryset,
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


@login_required
def group_detail_view(request, pk: int):
    """Display a research group's members and searchable papers, enforcing membership."""
    group = get_object_or_404(ResearchGroup, pk=pk)
    membership = GroupMembership.objects.filter(group=group, user=request.user).first()
    if membership is None:
        return HttpResponseForbidden("You are not a member of this research group.")

    is_admin = membership.role == GroupMembership.Role.ADMIN
    member_form = AddMemberForm()
    paper_form = PaperForm()

    if request.method == "POST":
        action = request.POST.get("action", "add_paper")
        if action == "add_member":
            member_form, response = _handle_add_member(request, group, is_admin)
            if response is not None:
                return response
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
            "available_tags": available_tags,
            "member_form": member_form,
            "paper_form": paper_form,
            "search_query": search_query,
            "tag_query": tag_query,
            "year_query": year_query,
        },
    )
