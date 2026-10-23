
import uuid

from django.conf import settings
from django.db import models

from .storage import vault_document_storage


def vault_blob_name(instance, filename):
    """Store files using random names instead of original filenames."""
    return uuid.uuid4().hex


def private_upload_path(instance, filename):
    """
    Keep older Django migrations compatible with the original upload path.
    """
    return vault_blob_name(instance, filename)


class Document(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=100, db_index=True)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_documents",
    )
    file = models.FileField(
        storage=vault_document_storage,
        upload_to=vault_blob_name,
    )
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["title"]),
            models.Index(fields=["original_filename"]),
        ]

    def __str__(self):
        return self.title


class DocumentGrant(models.Model):
    class AccessLevel(models.TextChoices):
        READ = "READ", "Read"
        EDIT = "EDIT", "Edit"

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="grants",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="document_grants",
    )
    access_level = models.CharField(
        max_length=4,
        choices=AccessLevel.choices,
        default=AccessLevel.READ,
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="grants_made",
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["document", "user"],
                name="unique_document_user_grant",
            )
        ]
        ordering = ["-granted_at"]

    @property
    def is_live(self):
        return self.revoked_at is None

    def __str__(self):
        return (
            f"{self.document.title} → "
            f"{self.user.username} ({self.access_level})"
        )
