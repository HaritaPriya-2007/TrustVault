from pathlib import Path

from django import forms
from django.contrib.auth import get_user_model

from .models import Document, DocumentGrant

User = get_user_model()

MAX_VAULT_FILE_BYTES = 10 * 1024 * 1024
ALLOWED_SUFFIXES = {".pdf", ".txt", ".docx", ".xlsx", ".png", ".jpg", ".jpeg"}

TEXT_WIDGET = forms.TextInput(attrs={"autocomplete": "off"})
AREA_WIDGET = forms.Textarea(attrs={"rows": 4})


class DocumentUploadForm(forms.ModelForm):
    file = forms.FileField(
        help_text="PDF, TXT, DOCX, XLSX, PNG, JPG, JPEG. 10 MB maximum.",
    )

    class Meta:
        model = Document
        fields = ["title", "category", "description", "file"]
        widgets = {
            "title": TEXT_WIDGET,
            "category": TEXT_WIDGET,
            "description": AREA_WIDGET,
        }

    def clean_title(self):
        title = (self.cleaned_data.get("title") or "").strip()
        if not title:
            raise forms.ValidationError("A title is required.")
        return title

    def clean_category(self):
        category = (self.cleaned_data.get("category") or "").strip()
        if not category:
            raise forms.ValidationError("A category is required.")
        return category

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        suffix = Path(uploaded.name).suffix.lower()

        if suffix not in ALLOWED_SUFFIXES:
            raise forms.ValidationError(
                "That file type is not accepted into the vault."
            )
        if uploaded.size == 0:
            raise forms.ValidationError("Empty files are not accepted.")
        if uploaded.size > MAX_VAULT_FILE_BYTES:
            raise forms.ValidationError("Files larger than 10 MB are rejected.")
        return uploaded


class DocumentShareForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=TEXT_WIDGET,
        help_text="The registered username of the person who should receive access.",
    )
    access_level = forms.ChoiceField(
        choices=DocumentGrant.AccessLevel.choices,
        initial=DocumentGrant.AccessLevel.READ,
    )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if not User.objects.filter(username__iexact=username, is_active=True).exists():
            raise forms.ValidationError("No active account uses that username.")
        return username


class ShelfSearchForm(forms.Form):
    q = forms.CharField(required=False, label="Name", widget=TEXT_WIDGET)
    owner = forms.CharField(required=False, widget=TEXT_WIDGET)
    category = forms.CharField(required=False, widget=TEXT_WIDGET)
    after = forms.DateField(required=False, label="From date", widget=forms.DateInput(attrs={"type": "date"}))
    before = forms.DateField(required=False, label="To date", widget=forms.DateInput(attrs={"type": "date"}))
