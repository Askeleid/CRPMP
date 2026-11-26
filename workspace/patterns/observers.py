from abc import ABC, abstractmethod

from django.conf import settings
from django.core import mail

from workspace.models import GroupMembership, Notification


class ResearchObserver(ABC):
    """Abstract observer interface for reacting to workspace domain events."""

    @abstractmethod
    def update(self, event_type: str, group, actor, message: str) -> None:
        """Handle a published workspace event."""


class InAppObserver(ResearchObserver):
    """Persist in-app Notification entries for group members excluding the actor."""

    def update(self, event_type: str, group, actor, message: str) -> None:
        if group is None:
            return
        memberships = GroupMembership.objects.filter(group=group).select_related("user")
        if actor is not None:
            memberships = memberships.exclude(user=actor)
        notifications = [
            Notification(recipient=m.user, group=group, message=message[:255])
            for m in memberships
        ]
        if notifications:
            Notification.objects.bulk_create(notifications)


class EmailObserver(ResearchObserver):
    """Send email notifications to group members with emails, excluding the actor."""

    def update(self, event_type: str, group, actor, message: str) -> None:
        if group is None:
            return
        memberships = (
            GroupMembership.objects.filter(group=group)
            .exclude(user__email="")
            .select_related("user")
        )
        if actor is not None:
            memberships = memberships.exclude(user=actor)
        recipient_emails = [
            m.user.email.strip()
            for m in memberships
            if m.user.email and m.user.email.strip()
        ]
        if not recipient_emails:
            return

        subject = f"[{group.name}] {event_type.replace('_', ' ').title()}"
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com")
        mail.send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_emails,
            fail_silently=True,
        )


class EventPublisher:
    """Subject/publisher maintaining attached ResearchObservers."""

    def __init__(self) -> None:
        self._observers: list[ResearchObserver] = []

    def attach(self, observer: ResearchObserver) -> None:
        """Attach an observer if not already subscribed."""
        if observer not in self._observers:
            self._observers.append(observer)

    def detach(self, observer: ResearchObserver) -> None:
        """Detach an observer if currently subscribed."""
        if observer in self._observers:
            self._observers.remove(observer)

    def notify(self, event_type: str, group, actor, message: str) -> None:
        """Notify all attached observers of an event."""
        for observer in list(self._observers):
            observer.update(event_type, group, actor, message)


def get_default_publisher() -> EventPublisher:
    """Return an EventPublisher pre-configured with in-app and email observers."""
    publisher = EventPublisher()
    publisher.attach(InAppObserver())
    publisher.attach(EmailObserver())
    return publisher
