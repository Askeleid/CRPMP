from django.urls import path

from workspace.views import HealthCheckView

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health-check"),
]
