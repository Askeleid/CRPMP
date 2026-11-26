from django.urls import include, path
from rest_framework.routers import DefaultRouter

from workspace.api_views import HealthCheckView, PaperViewSet, ResearchGroupViewSet

router = DefaultRouter()
router.register("groups", ResearchGroupViewSet, basename="api-groups")
router.register("papers", PaperViewSet, basename="api-papers")

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health-check"),
    path("", include(router.urls)),
]
