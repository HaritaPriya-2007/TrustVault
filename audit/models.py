
from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    class Action(models.TextChoices):
        UPLOAD = "UPLOAD", "Upload"
        DOWNLOAD = "DOWNLOAD", "Download"
        EDIT = "EDIT", "Edit"
        DELETE = "DELETE", "Delete"
        GRANT = "GRANT", "Grant access"
        REVOKE = "REVOKE", "Revoke access"
        ACCESS_DENIED = "ACCESS_DENIED", "Access denied"
        LOGIN = "LOGIN", "Login"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )

    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )

    action = models.CharField(max_length=20, choices=Action.choices)
    success = models.BooleanField(default=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)

    previous_hash = models.CharField(max_length=64, blank=True)
    event_hash = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-timestamp"]

    def save(self, *args, **kwargs):
        from .services import calculate_event_hash

        if not self._state.adding:
            return super().save(*args, **kwargs)

        database = kwargs.get("using") or self._state.db or "default"

        previous_event = (
            type(self).objects.using(database).order_by("-pk").first()
        )

        self.previous_hash = (
            previous_event.event_hash if previous_event else ""
        )
        self.event_hash = ""

        super().save(*args, **kwargs)

        self.event_hash = calculate_event_hash(self)

        type(self).objects.using(self._state.db).filter(
            pk=self.pk
        ).update(event_hash=self.event_hash)

    def __str__(self):
        return f"{self.action} at {self.timestamp}"
