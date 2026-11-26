from django.contrib import admin

from workspace.models import (
    ExperimentLog,
    GroupMembership,
    Paper,
    ResearchGroup,
    ResearchTask,
    Tag,
)


@admin.register(ResearchGroup)
class ResearchGroupAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_by", "created_at")
    search_fields = ("name", "description")


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ("id", "group", "user", "role", "joined_at")
    list_filter = ("role",)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(Paper)
class PaperAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "group", "year", "added_by", "created_at")
    list_filter = ("year", "group")
    search_fields = ("title", "authors", "doi", "arxiv_id")


@admin.register(ResearchTask)
class ResearchTaskAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "group", "paper", "assigned_to", "status", "due_date")
    list_filter = ("status", "group")
    search_fields = ("title", "description")


@admin.register(ExperimentLog)
class ExperimentLogAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "paper", "author", "logged_at")
    list_filter = ("paper",)
    search_fields = ("title", "hypothesis", "result_summary")
