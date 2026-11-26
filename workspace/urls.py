from django.contrib.auth import views as auth_views
from django.urls import path

from workspace.views import dashboard_view, group_detail_view, register_view

urlpatterns = [
    path("", dashboard_view, name="dashboard"),
    path("register/", register_view, name="register"),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("groups/<int:pk>/", group_detail_view, name="group-detail"),
]
