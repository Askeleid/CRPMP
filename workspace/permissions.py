from rest_framework.permissions import BasePermission

from workspace.models import GroupMembership, Paper, ResearchGroup


class IsGroupMember(BasePermission):
    """Allow object-level access only to members of the associated ResearchGroup."""

    message = "You must be a member of this research group."

    def has_object_permission(self, request, view, obj) -> bool:
        if isinstance(obj, ResearchGroup):
            group = obj
        elif isinstance(obj, Paper):
            group = obj.group
        else:
            return False

        return GroupMembership.objects.filter(
            group=group, user=request.user
        ).exists()
