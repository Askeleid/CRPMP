from django.db import transaction
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from workspace.models import ExperimentLog, Paper, ResearchGroup, ResearchTask
from workspace.services import assign_tags_to_paper


class HealthCheckSerializer(serializers.Serializer):
    """Serializer representing the API health-check response."""

    status = serializers.CharField(help_text="Service health status indicator.")


class ResearchGroupSerializer(serializers.ModelSerializer):
    """Serializer for ResearchGroup records."""

    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = ResearchGroup
        fields = ["id", "name", "description", "created_by", "created_at"]
        read_only_fields = ["id", "created_by", "created_at"]


@extend_schema_field({"type": "array", "items": {"type": "string"}})
class TagListField(serializers.ListField):
    """List field exposing normalized tag strings for Paper M2M tags."""

    child = serializers.CharField(max_length=100)

    def to_representation(self, value):
        if hasattr(value, "all"):
            return [tag.name for tag in value.all()]
        return list(value)


class PaperSerializer(serializers.ModelSerializer):
    """Serializer for Paper records with tag list handling."""

    added_by = serializers.ReadOnlyField(source="added_by.username")
    tags = TagListField(required=False, default=list)

    class Meta:
        model = Paper
        fields = [
            "id",
            "group",
            "added_by",
            "title",
            "authors",
            "year",
            "doi",
            "arxiv_id",
            "url",
            "pdf_file",
            "abstract",
            "tags",
            "created_at",
        ]
        read_only_fields = ["id", "added_by", "created_at"]

    def create(self, validated_data):
        tag_names = validated_data.pop("tags", [])
        with transaction.atomic():
            paper = super().create(validated_data)
            assign_tags_to_paper(paper, tag_names)
        return paper

    def update(self, instance, validated_data):
        tag_names = validated_data.pop("tags", None)
        with transaction.atomic():
            paper = super().update(instance, validated_data)
            if tag_names is not None:
                assign_tags_to_paper(paper, tag_names)
        return paper


class ResearchTaskSerializer(serializers.ModelSerializer):
    """Serializer for ResearchTask records."""

    class Meta:
        model = ResearchTask
        fields = [
            "id",
            "group",
            "paper",
            "title",
            "description",
            "assigned_to",
            "status",
            "due_date",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        group = attrs.get("group") or getattr(self.instance, "group", None)
        paper = attrs.get("paper")
        if paper is not None and group is not None and paper.group_id != group.id:
            raise serializers.ValidationError(
                {"paper": "Paper must belong to the same research group as the task."}
            )
        return attrs


class ExperimentLogSerializer(serializers.ModelSerializer):
    """Serializer for ExperimentLog entries linked to a Paper."""

    author = serializers.ReadOnlyField(source="author.username")

    class Meta:
        model = ExperimentLog
        fields = [
            "id",
            "paper",
            "author",
            "title",
            "hypothesis",
            "parameters",
            "result_summary",
            "logged_at",
        ]
        read_only_fields = ["id", "author", "logged_at"]
