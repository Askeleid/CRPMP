from django.urls import include, path
from rest_framework.routers import DefaultRouter

from workspace.api_views import (
    ExperimentLogViewSet,
    HealthCheckView,
    PaperViewSet,
    ResearchGroupViewSet,
    ResearchTaskViewSet,
)

router = DefaultRouter()
router.register("groups", ResearchGroupViewSet, basename="api-groups")
router.register("papers", PaperViewSet, basename="api-papers")
router.register("tasks", ResearchTaskViewSet, basename="api-tasks")
router.register(
    "experiment-logs", ExperimentLogViewSet, basename="api-experiment-logs"
)

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health-check"),
    path("", include(router.urls)),
]
