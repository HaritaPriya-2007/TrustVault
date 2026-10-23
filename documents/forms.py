
from pathlib import Path

from django import forms
from django.contrib.auth import get_user_model

from .models import Document, DocumentGrant


User = get_user_model()

MAX_DOCUMENT_SIZE = 10 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".docx",
    ".xlsx",
    ".png",
    ".jpg",
    ".jpeg",
}


class DocumentUploadForm(forms.ModelForm):
    file = forms.FileField()

    class Meta:
        model = Document
        fields = ["title", "category", "description", "file"]

    def clean_file(self):
        uploaded_file = self.cleaned_data["file"]
        extension = Path(uploaded_file.name).suffix.lower()

        if extension not in ALLOWED_EXTENSIONS:
            raise forms.ValidationError(
                "This file type is not allowed."
            )

        if uploaded_file.size == 0:
            raise forms.ValidationError(
                "Empty files cannot be uploaded."
            )

        if uploaded_file.size > MAX_DOCUMENT_SIZE:
            raise forms.ValidationError(
                "File size must not exceed 10 MB."
            )

        return uploaded_file


class DocumentShareForm(forms.Form):
    username = forms.CharField(max_length=150)

    access_level = forms.ChoiceField(
        choices=DocumentGrant.AccessLevel.choices,
        initial=DocumentGrant.AccessLevel.READ,
    )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()

        if not User.objects.filter(
            username__iexact=username
        ).exists():
            raise forms.ValidationError(
                "No registered user exists with that username."
            )

        return username
