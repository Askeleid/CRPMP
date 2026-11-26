from rest_framework.permissions import BasePermission

from workspace.models import (
    ExperimentLog,
    GroupMembership,
    Notification,
    Paper,
    ResearchGroup,
    ResearchTask,
)


class IsGroupMember(BasePermission):
    """Allow object-level access only to members of the associated ResearchGroup."""

    message = "You must be a member of this research group."

    def has_object_permission(self, request, view, obj) -> bool:
        if isinstance(obj, ResearchGroup):
            group = obj
        elif isinstance(obj, (Paper, ResearchTask)):
            group = obj.group
        elif isinstance(obj, ExperimentLog):
            group = obj.paper.group
        else:
            return False

        return GroupMembership.objects.filter(
            group=group, user=request.user
        ).exists()


class IsNotificationRecipient(BasePermission):
    """Allow access only to the recipient of the Notification."""

    message = "You do not have permission to access this notification."

    def has_object_permission(self, request, view, obj) -> bool:
        return isinstance(obj, Notification) and obj.recipient_id == request.user.id
