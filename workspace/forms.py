from django import forms
from django.contrib.auth import get_user_model

from workspace.models import ExperimentLog, Paper, ResearchGroup, ResearchTask
from workspace.services import is_group_member

User = get_user_model()


class ResearchGroupForm(forms.ModelForm):
    """Form for creating a new research group."""

    class Meta:
        model = ResearchGroup
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g., NLP Research Lab"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Brief description of the group's research focus",
                }
            ),
        }


class AddMemberForm(forms.Form):
    """Form allowing a group admin to add an existing user by username."""

    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Enter username"}
        ),
    )


class PaperForm(forms.ModelForm):
    """Form for adding a research paper with comma-separated tags."""

    url = forms.URLField(
        required=False,
        assume_scheme="https",
        widget=forms.URLInput(attrs={"class": "form-control"}),
    )
    tags = forms.CharField(
        required=False,
        help_text="Comma-separated tags (e.g., nlp, transformers, llm)",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "nlp, transformers, llm",
            }
        ),
    )

    class Meta:
        model = Paper
        fields = [
            "title",
            "authors",
            "year",
            "doi",
            "arxiv_id",
            "url",
            "pdf_file",
            "abstract",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "authors": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Author One, Author Two",
                }
            ),
            "year": forms.NumberInput(attrs={"class": "form-control"}),
            "doi": forms.TextInput(attrs={"class": "form-control"}),
            "arxiv_id": forms.TextInput(attrs={"class": "form-control"}),
            "url": forms.URLInput(attrs={"class": "form-control"}),
            "pdf_file": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "abstract": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class ResearchTaskForm(forms.ModelForm):
    """Form for creating a research task within a research group."""

    class Meta:
        model = ResearchTask
        fields = ["title", "description", "paper", "assigned_to", "due_date"]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Task title"}
            ),
            "description": forms.Textarea(
                attrs={"class": "form-control", "rows": 2, "placeholder": "Details"}
            ),
            "paper": forms.Select(attrs={"class": "form-select"}),
            "assigned_to": forms.Select(attrs={"class": "form-select"}),
            "due_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
        }

    def __init__(self, *args, group: ResearchGroup | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        instance_group = (
            self.instance.group
            if getattr(self.instance, "group_id", None) is not None
            else None
        )
        self.group = group or instance_group
        if self.group is not None:
            self.fields["paper"].queryset = self.group.papers.order_by("title")
            self.fields["assigned_to"].queryset = (
                User.objects.filter(group_memberships__group=self.group)
                .distinct()
                .order_by("username")
            )
        else:
            self.fields["paper"].queryset = Paper.objects.none()
            self.fields["assigned_to"].queryset = User.objects.none()
        self.fields["paper"].required = False
        self.fields["assigned_to"].required = False

    def clean_assigned_to(self):
        assigned_to = self.cleaned_data.get("assigned_to")
        if assigned_to is not None and (
            self.group is None or not is_group_member(self.group, assigned_to)
        ):
            raise forms.ValidationError(
                "Assignee must be a member of this research group."
            )
        return assigned_to


class ExperimentLogForm(forms.ModelForm):
    """Form for recording an experiment log or reproduction note on a paper."""

    class Meta:
        model = ExperimentLog
        fields = ["title", "hypothesis", "parameters", "result_summary"]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Experiment title"}
            ),
            "hypothesis": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "What are you testing?",
                }
            ),
            "parameters": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "Hyperparameters, hardware, dataset split...",
                }
            ),
            "result_summary": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Key metrics and observations",
                }
            ),
        }
