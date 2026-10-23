from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404

from .models import Document, DocumentGrant


SUPPORTED_CAPABILITIES = frozenset({"read", "edit", "delete", "share"})


def owner_or_live_grant(user):
    return Q(owner_id=user.pk) | Q(
        grants__user_id=user.pk,
        grants__revoked_at__isnull=True,
    )


def get_authorized_document(user, document_id, action="read"):
    """
    Return a document only when the signed-in person may perform `action`.

    The lookup itself is limited to owned records and live grants, so a
    stranger asking for someone else's id receives the same 404 as a
    made-up id. Administrators do not inherit document custody.
    """
    if not user or not user.is_authenticated:
        raise PermissionDenied("Sign in is required.")

    if action not in SUPPORTED_CAPABILITIES:
        raise ValueError("Unsupported document action.")

    document = get_object_or_404(
        Document.objects.filter(owner_or_live_grant(user)).distinct(),
        pk=document_id,
    )

    if document.owner_id == user.pk:
        return document

    if action in {"delete", "share"}:
        raise PermissionDenied("Only the document owner can do that.")

    grant = DocumentGrant.objects.filter(
        document_id=document.pk,
        user_id=user.pk,
        revoked_at__isnull=True,
    ).first()

    if grant is None:
        raise PermissionDenied("No live custody grant.")

    if action == "edit" and grant.access_level != DocumentGrant.AccessLevel.EDIT:
        raise PermissionDenied("An edit grant is required.")

    return document
