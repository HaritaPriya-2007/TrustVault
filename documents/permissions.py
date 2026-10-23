
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from .models import Document, DocumentGrant


def get_authorized_document(user, document_id, action="read"):
    """
    Return a document only if the authenticated user
    is authorized for the requested action.

    Supported actions: read, edit, delete, share.
    Administrators do not automatically get document access.
    """

    if not user or not user.is_authenticated:
        raise PermissionDenied("Authentication required.")

    if action not in {"read", "edit", "delete", "share"}:
        raise ValueError("Unsupported document action.")

    # Scope the lookup to the owner or a currently active grant.
    # An unauthorized user gets the same 404 as an unknown ID.
    document = get_object_or_404(
        Document.objects.filter(
            models_Q_owner_or_active_grant(user)
        ).distinct(),
        pk=document_id,
    )

    if document.owner_id == user.pk:
        return document

    if action in {"delete", "share"}:
        raise PermissionDenied("Only the owner can perform this action.")

    grant = DocumentGrant.objects.filter(
        document_id=document.pk,
        user_id=user.pk,
        revoked_at__isnull=True,
    ).first()

    if grant is None:
        raise PermissionDenied("No active document grant.")

    if action == "edit" and grant.access_level != DocumentGrant.AccessLevel.EDIT:
        raise PermissionDenied("Edit permission required.")

    return document


def models_Q_owner_or_active_grant(user):
    from django.db.models import Q

    return Q(owner_id=user.pk) | Q(
        grants__user_id=user.pk,
        grants__revoked_at__isnull=True,
    )
