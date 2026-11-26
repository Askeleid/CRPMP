from django.conf import settings
from django.db import models


class ResearchGroup(models.Model):
    """Collaborative research group workspace owned and joined by users."""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_groups",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name


class GroupMembership(models.Model):
    """Membership linking a user to a research group with a specific role."""

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        MEMBER = "MEMBER", "Member"

    group = models.ForeignKey(
        ResearchGroup,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="group_memberships",
    )
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.MEMBER,
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["group", "user"],
                name="unique_group_membership",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} - {self.group} ({self.role})"


class Tag(models.Model):
    """Lowercase tag label for categorizing research papers."""

    name = models.CharField(max_length=100, unique=True)

    def save(self, *args, **kwargs):
        self.name = self.name.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class Paper(models.Model):
    """Research paper stored within a research group."""

    group = models.ForeignKey(
        ResearchGroup,
        on_delete=models.CASCADE,
        related_name="papers",
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="added_papers",
    )
    title = models.CharField(max_length=500)
    authors = models.CharField(max_length=1000)
    year = models.IntegerField()
    doi = models.CharField(max_length=255, blank=True)
    arxiv_id = models.CharField(max_length=100, blank=True)
    url = models.URLField(blank=True)
    pdf_file = models.FileField(upload_to="papers/", blank=True, null=True)
    abstract = models.TextField(blank=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name="papers")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.title


class ResearchTask(models.Model):
    """Actionable research task scoped to a research group and optional paper."""

    class Status(models.TextChoices):
        TODO = "TODO", "To Do"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        DONE = "DONE", "Done"

    group = models.ForeignKey(
        ResearchGroup,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    paper = models.ForeignKey(
        Paper,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasks",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tasks",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.TODO,
    )
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.title


class ExperimentLog(models.Model):
    """Experiment log or reproduction note attached to a research paper."""

    paper = models.ForeignKey(
        Paper,
        on_delete=models.CASCADE,
        related_name="experiment_logs",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="experiment_logs",
    )
    title = models.CharField(max_length=255)
    hypothesis = models.TextField()
    parameters = models.TextField(blank=True)
    result_summary = models.TextField()
    logged_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.title
