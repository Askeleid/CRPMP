from workspace.models import Notification


def notifications_context(request) -> dict:
    """Provide unread notification count and recent notifications to templates."""
    if getattr(request, "user", None) is not None and request.user.is_authenticated:
        base_qs = Notification.objects.filter(recipient=request.user).select_related(
            "group"
        )
        return {
            "unread_notifications_count": base_qs.filter(is_read=False).count(),
            "recent_notifications": list(base_qs.order_by("-created_at")[:5]),
        }
    return {
        "unread_notifications_count": 0,
        "recent_notifications": [],
    }
