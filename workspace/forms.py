from django import forms

from workspace.models import Paper, ResearchGroup


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
