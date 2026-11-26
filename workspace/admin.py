from django.contrib import admin

from workspace.models import GroupMembership, Paper, ResearchGroup, Tag


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
