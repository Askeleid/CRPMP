from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from workspace.models import GroupMembership, Paper, ResearchGroup, Tag

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def group_with_paper(db):
    alice = User.objects.create_user(username="alice", password="StrongPassword123!")
    bob = User.objects.create_user(username="bob", password="StrongPassword123!")
    outsider = User.objects.create_user(
        username="outsider", password="StrongPassword123!"
    )

    group = ResearchGroup.objects.create(
        name="ML Systems", description="Distributed ML", created_by=alice
    )
    GroupMembership.objects.create(
        group=group, user=alice, role=GroupMembership.Role.ADMIN
    )
    GroupMembership.objects.create(
        group=group, user=bob, role=GroupMembership.Role.MEMBER
    )

    tag = Tag.objects.create(name="systems")
    paper = Paper.objects.create(
        group=group,
        added_by=alice,
        title="ZeRO: Memory Optimizations Toward Training Trillion Parameter Models",
        authors="Samyam Rajbhandari, Jeff Rasley",
        year=2020,
        abstract="Zero Redundancy Optimizer for distributed training.",
    )
    paper.tags.add(tag)

    return {
        "alice": alice,
        "bob": bob,
        "outsider": outsider,
        "group": group,
        "paper": paper,
    }


@pytest.mark.django_db
def test_task_and_experiment_log_models(group_with_paper):
    from workspace.models import ExperimentLog, ResearchTask

    alice = group_with_paper["alice"]
    bob = group_with_paper["bob"]
    group = group_with_paper["group"]
    paper = group_with_paper["paper"]

    task = ResearchTask.objects.create(
        group=group,
        paper=paper,
        title="Benchmark ZeRO-3 memory footprint",
        description="Run 7B parameter test on 4 GPUs",
        assigned_to=bob,
        due_date=date(2026, 12, 15),
    )
    assert task.status == ResearchTask.Status.TODO
    assert task in group.tasks.all()

    log = ExperimentLog.objects.create(
        paper=paper,
        author=alice,
        title="Initial 4-GPU baseline",
        hypothesis="ZeRO-3 reduces per-GPU activation and optimizer memory by >50%.",
        parameters="batch_size=32, fp16=True, stage=3",
        result_summary="Peak VRAM dropped from 22GB to 9.4GB.",
    )
    assert log in paper.experiment_logs.all()


@pytest.mark.django_db
def test_group_detail_task_creation_and_status_transitions(client, group_with_paper):
    from workspace.models import ResearchTask

    alice = group_with_paper["alice"]
    bob = group_with_paper["bob"]
    group = group_with_paper["group"]
    paper = group_with_paper["paper"]

    client.force_login(alice)
    create_resp = client.post(
        reverse("group-detail", args=[group.id]),
        {
            "action": "add_task",
            "title": "Reproduce ablation table",
            "description": "Compare stage 1 vs stage 2",
            "paper": paper.id,
            "assigned_to": bob.id,
            "due_date": "2026-12-20",
        },
    )
    assert create_resp.status_code == 302

    task = ResearchTask.objects.get(title="Reproduce ablation table")
    assert task.status == ResearchTask.Status.TODO
    assert task.assigned_to == bob

    # Member Bob transitions status TODO -> IN_PROGRESS -> DONE
    client.force_login(bob)
    in_prog_resp = client.post(
        reverse("group-detail", args=[group.id]),
        {
            "action": "update_task_status",
            "task_id": task.id,
            "status": ResearchTask.Status.IN_PROGRESS,
        },
    )
    assert in_prog_resp.status_code == 302
    task.refresh_from_db()
    assert task.status == ResearchTask.Status.IN_PROGRESS

    done_resp = client.post(
        reverse("group-detail", args=[group.id]),
        {
            "action": "update_task_status",
            "task_id": task.id,
            "status": ResearchTask.Status.DONE,
        },
    )
    assert done_resp.status_code == 302
    task.refresh_from_db()
    assert task.status == ResearchTask.Status.DONE

    # Group detail page displays task and links paper title to paper-detail
    page_resp = client.get(reverse("group-detail", args=[group.id]))
    assert page_resp.status_code == 200
    html = page_resp.content.decode()
    assert "Reproduce ablation table" in html
    assert reverse("paper-detail", args=[paper.id]) in html


@pytest.mark.django_db
def test_paper_detail_access_control_and_experiment_log_creation(
    client, group_with_paper
):
    from workspace.models import ExperimentLog

    bob = group_with_paper["bob"]
    outsider = group_with_paper["outsider"]
    paper = group_with_paper["paper"]
    url = reverse("paper-detail", args=[paper.id])

    # Non-member receives HTTP 403 on GET and POST
    client.force_login(outsider)
    assert client.get(url).status_code == 403
    assert (
        client.post(
            url,
            {
                "title": "Unauthorized log",
                "hypothesis": "Should fail",
                "result_summary": "Denied",
            },
        ).status_code
        == 403
    )

    # Group member can view paper detail and add an ExperimentLog
    client.force_login(bob)
    get_resp = client.get(url)
    assert get_resp.status_code == 200
    assert paper.title in get_resp.content.decode()
    assert "systems" in get_resp.content.decode()

    post_resp = client.post(
        url,
        {
            "title": "Gradient accumulation run",
            "hypothesis": "Accumulating 4 steps preserves convergence.",
            "parameters": "grad_accum=4, lr=1e-4",
            "result_summary": "Validation loss matched baseline at 2.14.",
        },
    )
    assert post_resp.status_code == 302

    log = ExperimentLog.objects.get(title="Gradient accumulation run")
    assert log.paper == paper
    assert log.author == bob

    updated_html = client.get(url).content.decode()
    assert "Gradient accumulation run" in updated_html
    assert "Validation loss matched baseline at 2.14." in updated_html


@pytest.mark.django_db
def test_api_tasks_and_experiment_logs_endpoints(api_client, group_with_paper):
    from workspace.models import ResearchTask

    alice = group_with_paper["alice"]
    bob = group_with_paper["bob"]
    outsider = group_with_paper["outsider"]
    group = group_with_paper["group"]
    paper = group_with_paper["paper"]

    # Unauthenticated requests rejected
    assert api_client.get("/api/tasks/").status_code in (401, 403)
    assert api_client.get("/api/experiment-logs/").status_code in (401, 403)

    # Create a second group for group filter testing
    other_group = ResearchGroup.objects.create(name="Vision Lab", created_by=alice)
    GroupMembership.objects.create(
        group=other_group, user=alice, role=GroupMembership.Role.ADMIN
    )

    api_client.force_authenticate(user=alice)
    t1_resp = api_client.post(
        "/api/tasks/",
        {
            "group": group.id,
            "paper": paper.id,
            "title": "Run scaling study",
            "description": "Test 1 to 8 GPUs",
            "assigned_to": bob.id,
        },
        format="json",
    )
    assert t1_resp.status_code == 201
    task_id = t1_resp.data["id"]
    assert t1_resp.data["status"] == ResearchTask.Status.TODO

    t2_resp = api_client.post(
        "/api/tasks/",
        {
            "group": other_group.id,
            "title": "Prepare dataset split",
            "status": ResearchTask.Status.IN_PROGRESS,
        },
        format="json",
    )
    assert t2_resp.status_code == 201

    # Filter tasks by ?group= and ?status=
    group_filtered = api_client.get(f"/api/tasks/?group={group.id}")
    assert group_filtered.status_code == 200
    assert len(group_filtered.data) == 1
    assert group_filtered.data[0]["title"] == "Run scaling study"

    status_filtered = api_client.get("/api/tasks/?status=IN_PROGRESS")
    assert status_filtered.status_code == 200
    assert len(status_filtered.data) == 1
    assert status_filtered.data[0]["title"] == "Prepare dataset split"

    # PATCH status transition
    patch_resp = api_client.patch(
        f"/api/tasks/{task_id}/",
        {"status": ResearchTask.Status.DONE},
        format="json",
    )
    assert patch_resp.status_code == 200
    assert patch_resp.data["status"] == ResearchTask.Status.DONE

    # Create experiment log via API
    other_paper = Paper.objects.create(
        group=other_group, added_by=alice, title="ViT Paper", year=2020, authors="Alexey"
    )
    log_resp = api_client.post(
        "/api/experiment-logs/",
        {
            "paper": paper.id,
            "title": "API Experiment Log",
            "hypothesis": "FP16 speeds up throughput 2x",
            "parameters": "precision=fp16",
            "result_summary": "Measured 1.92x speedup",
        },
        format="json",
    )
    assert log_resp.status_code == 201
    log_id = log_resp.data["id"]
    assert log_resp.data["author"] == "alice"

    api_client.post(
        "/api/experiment-logs/",
        {
            "paper": other_paper.id,
            "title": "Other Paper Log",
            "hypothesis": "Patch size 16 works best",
            "result_summary": "Top-1 accuracy 81.2%",
        },
        format="json",
    )

    paper_logs = api_client.get(f"/api/experiment-logs/?paper={paper.id}")
    assert paper_logs.status_code == 200
    assert len(paper_logs.data) == 1
    assert paper_logs.data[0]["title"] == "API Experiment Log"

    # Outsider gets 403 on detail & create endpoints, and empty lists
    api_client.force_authenticate(user=outsider)
    assert api_client.get("/api/tasks/").data == []
    assert api_client.get("/api/experiment-logs/").data == []
    assert api_client.get(f"/api/tasks/{task_id}/").status_code == 403
    assert api_client.get(f"/api/experiment-logs/{log_id}/").status_code == 403
    assert (
        api_client.post(
            "/api/tasks/",
            {"group": group.id, "title": "Forbidden Task"},
            format="json",
        ).status_code
        == 403
    )
    assert (
        api_client.post(
            "/api/experiment-logs/",
            {
                "paper": paper.id,
                "title": "Forbidden Log",
                "hypothesis": "H",
                "result_summary": "R",
            },
            format="json",
        ).status_code
        == 403
    )

    # OpenAPI schema includes /api/tasks/ and /api/experiment-logs/
    schema_resp = api_client.get("/api/schema/")
    assert schema_resp.status_code == 200
    assert b"/api/tasks/" in schema_resp.content
    assert b"/api/experiment-logs/" in schema_resp.content


@pytest.mark.django_db
def test_task_assignee_must_be_group_member(client, api_client, group_with_paper):
    from workspace.forms import ResearchTaskForm
    from workspace.models import ResearchTask

    alice = group_with_paper["alice"]
    bob = group_with_paper["bob"]
    outsider = group_with_paper["outsider"]
    group = group_with_paper["group"]

    # Form queryset excludes non-members and validation rejects non-member assignment
    form = ResearchTaskForm(
        data={"title": "Invalid task", "assigned_to": outsider.id},
        group=group,
    )
    assert not form.is_valid()
    assert "assigned_to" in form.errors
    assert outsider not in form.fields["assigned_to"].queryset
    assert bob in form.fields["assigned_to"].queryset

    # Web UI POST with non-member assignee does not create a task
    client.force_login(alice)
    ui_resp = client.post(
        reverse("group-detail", args=[group.id]),
        {
            "action": "add_task",
            "title": "UI non-member task",
            "assigned_to": outsider.id,
        },
    )
    assert ui_resp.status_code == 200
    assert not ResearchTask.objects.filter(title="UI non-member task").exists()

    # API POST and PATCH reject non-member assignee with HTTP 400
    api_client.force_authenticate(user=alice)
    api_create_resp = api_client.post(
        "/api/tasks/",
        {
            "group": group.id,
            "title": "API non-member task",
            "assigned_to": outsider.id,
        },
        format="json",
    )
    assert api_create_resp.status_code == 400
    assert "assigned_to" in api_create_resp.data

    valid_task = ResearchTask.objects.create(group=group, title="Valid task")
    api_patch_resp = api_client.patch(
        f"/api/tasks/{valid_task.id}/",
        {"assigned_to": outsider.id},
        format="json",
    )
    assert api_patch_resp.status_code == 400
    assert "assigned_to" in api_patch_resp.data
