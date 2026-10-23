
import uuid

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models


# TrustVault stores uploaded documents outside public media directories.
private_storage = FileSystemStorage(
    location=settings.PRIVATE_DOCUMENT_ROOT,
)


def private_upload_path(instance, filename):
    """Generate a random storage filename for each uploaded document."""
    return uuid.uuid4().hex


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
        storage=private_storage,
        upload_to=private_upload_path,
    )

    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

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
    def is_active(self):
        return self.revoked_at is None

    def __str__(self):
        return (
            f"{self.document.title} - {self.user.username} "
            f"({self.access_level})"
        )
