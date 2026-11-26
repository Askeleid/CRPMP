from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from workspace.models import GroupMembership, Paper, ResearchGroup

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def group_members(db):
    alice = User.objects.create_user(
        username="alice",
        email="alice@example.com",
        password="StrongPassword123!",
    )
    bob = User.objects.create_user(
        username="bob",
        email="bob@example.com",
        password="StrongPassword123!",
    )
    charlie_no_email = User.objects.create_user(
        username="charlie",
        email="",
        password="StrongPassword123!",
    )
    outsider = User.objects.create_user(
        username="outsider",
        email="outsider@example.com",
        password="StrongPassword123!",
    )

    group = ResearchGroup.objects.create(name="Observer Lab", created_by=alice)
    GroupMembership.objects.create(
        group=group, user=alice, role=GroupMembership.Role.ADMIN
    )
    GroupMembership.objects.create(
        group=group, user=bob, role=GroupMembership.Role.MEMBER
    )
    GroupMembership.objects.create(
        group=group, user=charlie_no_email, role=GroupMembership.Role.MEMBER
    )
    return {
        "alice": alice,
        "bob": bob,
        "charlie": charlie_no_email,
        "outsider": outsider,
        "group": group,
    }


def test_event_publisher_attach_detach_notify():
    from workspace.patterns.observers import EventPublisher, ResearchObserver

    publisher = EventPublisher()
    obs1 = MagicMock(spec=ResearchObserver)
    obs2 = MagicMock(spec=ResearchObserver)

    publisher.attach(obs1)
    publisher.attach(obs2)
    publisher.detach(obs1)

    publisher.notify("paper_added", group="grp", actor="alice", message="New paper")

    obs1.update.assert_not_called()
    obs2.update.assert_called_once_with("paper_added", "grp", "alice", "New paper")


@pytest.mark.django_db
def test_in_app_and_email_observers_exclude_actor(group_members):
    from workspace.models import Notification
    from workspace.patterns.observers import (
        EmailObserver,
        InAppObserver,
        get_default_publisher,
    )

    alice = group_members["alice"]
    bob = group_members["bob"]
    charlie = group_members["charlie"]
    outsider = group_members["outsider"]
    group = group_members["group"]

    publisher = get_default_publisher()
    assert any(isinstance(o, InAppObserver) for o in publisher._observers)
    assert any(isinstance(o, EmailObserver) for o in publisher._observers)

    with patch("django.core.mail.send_mail") as mock_send_mail:
        publisher.notify(
            "paper_added",
            group=group,
            actor=alice,
            message="alice added a new paper.",
        )

    # InAppObserver creates notifications for bob and charlie, not alice or outsider
    recipients = set(
        Notification.objects.values_list("recipient__username", flat=True)
    )
    assert recipients == {"bob", "charlie"}
    assert not Notification.objects.filter(recipient=alice).exists()
    assert not Notification.objects.filter(recipient=outsider).exists()
    assert all(not n.is_read for n in Notification.objects.all())

    # EmailObserver emails only non-actor members with non-empty email (bob only)
    mock_send_mail.assert_called_once()
    call_kwargs = mock_send_mail.call_args.kwargs
    recipient_list = (
        call_kwargs.get("recipient_list")
        if "recipient_list" in call_kwargs
        else mock_send_mail.call_args.args[3]
    )
    assert recipient_list == ["bob@example.com"]


@pytest.mark.django_db
def test_paper_and_task_creation_triggers_notifications_ui_and_api(
    client, api_client, group_members
):
    from workspace.models import Notification

    alice = group_members["alice"]
    bob = group_members["bob"]
    group = group_members["group"]

    # Adding a paper via API triggers notifications for Bob
    api_client.force_authenticate(user=alice)
    with patch("django.core.mail.send_mail") as mock_mail:
        paper_resp = api_client.post(
            "/api/papers/",
            {
                "group": group.id,
                "title": "Observer Paper",
                "authors": "Alice",
                "year": 2025,
            },
            format="json",
        )
    assert paper_resp.status_code == 201
    assert Notification.objects.filter(
        recipient=bob, group=group, message__icontains="Observer Paper"
    ).exists()
    assert mock_mail.call_count == 1

    # Creating a task via Web UI triggers notifications for Bob
    client.force_login(alice)
    with patch("django.core.mail.send_mail") as mock_mail_ui:
        task_resp = client.post(
            reverse("group-detail", args=[group.id]),
            {
                "action": "add_task",
                "title": "Review Observer Paper",
                "assigned_to": bob.id,
            },
        )
    assert task_resp.status_code == 302
    assert Notification.objects.filter(
        recipient=bob, group=group, message__icontains="Review Observer Paper"
    ).exists()
    assert mock_mail_ui.call_count == 1


@pytest.mark.django_db
def test_notifications_api_and_navbar_ui(client, api_client, group_members):
    from workspace.models import Notification

    alice = group_members["alice"]
    bob = group_members["bob"]
    group = group_members["group"]

    n1 = Notification.objects.create(
        recipient=bob, group=group, message="Unread alert 1"
    )
    n2 = Notification.objects.create(
        recipient=bob, group=group, message="Read alert 2", is_read=True
    )
    other_n = Notification.objects.create(
        recipient=alice, group=group, message="Alice alert"
    )

    # Unauthenticated access rejected
    assert api_client.get("/api/notifications/").status_code in (401, 403)

    # Bob sees only his notifications
    api_client.force_authenticate(user=bob)
    list_resp = api_client.get("/api/notifications/")
    assert list_resp.status_code == 200
    assert {item["id"] for item in list_resp.data} == {n1.id, n2.id}

    # Bob cannot access or mark Alice's notification read
    assert api_client.get(f"/api/notifications/{other_n.id}/").status_code == 403
    assert (
        api_client.post(f"/api/notifications/{other_n.id}/mark-read/").status_code
        == 403
    )

    # Bob renders navbar notification count & recent notifications in base.html
    client.force_login(bob)
    dash_html = client.get(reverse("dashboard")).content.decode()
    assert "Unread alert 1" in dash_html
    assert "1" in dash_html

    # Bob marks n1 as read via API
    mark_resp = api_client.post(f"/api/notifications/{n1.id}/mark-read/")
    assert mark_resp.status_code == 200
    assert mark_resp.data["is_read"] is True
    n1.refresh_from_db()
    assert n1.is_read is True

    # OpenAPI schema documents notifications endpoints
    schema_resp = api_client.get("/api/schema/")
    assert schema_resp.status_code == 200
    assert b"/api/notifications/" in schema_resp.content
    assert b"/api/notifications/{id}/mark-read/" in schema_resp.content
