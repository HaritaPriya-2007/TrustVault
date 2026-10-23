
import hashlib
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from audit.models import AuditEvent
from audit.services import record_access_denied

from .forms import DocumentShareForm, DocumentUploadForm
from .models import Document, DocumentGrant
from .permissions import get_authorized_document


User = get_user_model()


def get_authorized_document_or_log_denial(
    request,
    document_id,
    operation,
):
    """Authorize a document action and audit denied attempts."""
    permission_action = (
        "read" if operation == "download" else operation
    )

    try:
        return get_authorized_document(
            request.user,
            document_id,
            action=permission_action,
        )
    except (Http404, PermissionDenied):
        record_access_denied(
            actor=request.user,
            operation=operation,
            document_id=document_id,
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        raise


def log_role_denial(request, operation):
    """Record a role-based denial without linking to a private document."""
    record_access_denied(
        actor=request.user,
        operation=operation,
        ip_address=request.META.get("REMOTE_ADDR"),
    )


@login_required
@require_GET
def download_document(request, document_id):
    document = get_authorized_document_or_log_denial(
        request,
        document_id,
        operation="download",
    )

    if not document.file or not document.file.storage.exists(
        document.file.name
    ):
        raise Http404("Document file not found.")

    AuditEvent.objects.create(
        actor=request.user,
        document=document,
        action=AuditEvent.Action.DOWNLOAD,
        success=True,
        ip_address=request.META.get("REMOTE_ADDR"),
        details={"operation": "download"},
    )

    return FileResponse(
        document.file.open("rb"),
        as_attachment=True,
        filename=document.original_filename,
        content_type="application/octet-stream",
    )


@login_required
@require_http_methods(["GET", "POST"])
def upload_document(request):
    if request.user.role not in {
        User.Role.OWNER,
        User.Role.ADMIN,
    }:
        log_role_denial(request, "upload")
        return render(
            request,
            "documents/upload.html",
            {
                "form": DocumentUploadForm(),
                "error": (
                    "Your account does not have permission "
                    "to upload documents."
                ),
            },
            status=403,
        )

    if request.method == "POST":
        form = DocumentUploadForm(request.POST, request.FILES)

        if form.is_valid():
            uploaded_file = form.cleaned_data["file"]

            digest = hashlib.sha256()
            for chunk in uploaded_file.chunks():
                digest.update(chunk)

            document = form.save(commit=False)
            document.owner = request.user
            document.original_filename = Path(
                uploaded_file.name
            ).name[:255]
            document.content_type = "application/octet-stream"
            document.size_bytes = uploaded_file.size
            document.sha256 = digest.hexdigest()

            with transaction.atomic():
                document.save()

                AuditEvent.objects.create(
                    actor=request.user,
                    document=document,
                    action=AuditEvent.Action.UPLOAD,
                    success=True,
                    ip_address=request.META.get("REMOTE_ADDR"),
                    details={
                        "operation": "upload",
                        "size_bytes": document.size_bytes,
                        "sha256": document.sha256,
                    },
                )

            return render(
                request,
                "documents/upload_success.html",
                {"document": document},
            )
    else:
        form = DocumentUploadForm()

    return render(
        request,
        "documents/upload.html",
        {"form": form},
    )


@login_required
@require_http_methods(["GET", "POST"])
def edit_document(request, document_id):
    document = get_authorized_document_or_log_denial(
        request,
        document_id,
        operation="edit",
    )

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        category = request.POST.get("category", "").strip()
        description = request.POST.get("description", "").strip()

        if not title or not category:
            return render(
                request,
                "documents/edit.html",
                {
                    "document": document,
                    "error": "Title and category are required.",
                },
                status=400,
            )

        if len(title) > 255 or len(category) > 100:
            return render(
                request,
                "documents/edit.html",
                {
                    "document": document,
                    "error": (
                        "Title must be at most 255 characters "
                        "and category at most 100 characters."
                    ),
                },
                status=400,
            )

        with transaction.atomic():
            document.title = title
            document.category = category
            document.description = description
            document.save(
                update_fields=[
                    "title",
                    "category",
                    "description",
                    "updated_at",
                ]
            )

            AuditEvent.objects.create(
                actor=request.user,
                document=document,
                action=AuditEvent.Action.EDIT,
                success=True,
                ip_address=request.META.get("REMOTE_ADDR"),
                details={"operation": "edit"},
            )

        return redirect(
            "download_document",
            document_id=document.pk,
        )

    return render(
        request,
        "documents/edit.html",
        {"document": document},
    )


@login_required
@require_GET
def my_documents(request):
    documents = (
        Document.objects.filter(
            Q(owner=request.user)
            | Q(
                grants__user=request.user,
                grants__revoked_at__isnull=True,
            )
        )
        .distinct()
        .order_by("-created_at")
    )

    document_items = []

    for document in documents:
        is_owner = document.owner_id == request.user.pk
        grant = None

        if not is_owner:
            grant = DocumentGrant.objects.filter(
                document=document,
                user=request.user,
                revoked_at__isnull=True,
            ).first()

        document_items.append(
            {
                "document": document,
                "can_edit": (
                    is_owner
                    or (
                        grant is not None
                        and grant.access_level
                        == DocumentGrant.AccessLevel.EDIT
                    )
                ),
                "can_download": is_owner or grant is not None,
            }
        )

    return render(
        request,
        "documents/my_documents.html",
        {"document_items": document_items},
    )


@login_required
@require_GET
def dashboard(request):
    accessible_documents = Document.objects.filter(
        Q(owner=request.user)
        | Q(
            grants__user=request.user,
            grants__revoked_at__isnull=True,
        )
    ).distinct()

    return render(
        request,
        "documents/dashboard.html",
        {
            "total_documents": accessible_documents.count(),
            "owned_documents": accessible_documents.filter(
                owner=request.user
            ).count(),
            "shared_documents": accessible_documents.exclude(
                owner=request.user
            ).count(),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def share_document(request, document_id):
    document = get_authorized_document_or_log_denial(
        request,
        document_id,
        operation="share",
    )

    active_grants = document.grants.filter(
        revoked_at__isnull=True
    ).select_related("user", "granted_by")

    if request.method == "POST":
        form = DocumentShareForm(request.POST)

        if form.is_valid():
            username = form.cleaned_data["username"]
            access_level = form.cleaned_data["access_level"]

            recipient = User.objects.filter(
                username__iexact=username
            ).first()

            if recipient is None:
                form.add_error(
                    "username",
                    "No registered user exists with that username.",
                )
            elif recipient.pk == document.owner_id:
                form.add_error(
                    "username",
                    "You cannot share a document with its owner.",
                )
            elif not recipient.is_active:
                form.add_error(
                    "username",
                    "You cannot share with an inactive account.",
                )
            else:
                with transaction.atomic():
                    grant = (
                        DocumentGrant.objects.select_for_update()
                        .filter(
                            document=document,
                            user=recipient,
                        )
                        .first()
                    )

                    if grant is None:
                        DocumentGrant.objects.create(
                            document=document,
                            user=recipient,
                            granted_by=request.user,
                            access_level=access_level,
                        )
                    else:
                        grant.access_level = access_level
                        grant.granted_by = request.user
                        grant.granted_at = timezone.now()
                        grant.revoked_at = None
                        grant.save(
                            update_fields=[
                                "access_level",
                                "granted_by",
                                "granted_at",
                                "revoked_at",
                            ]
                        )

                    AuditEvent.objects.create(
                        actor=request.user,
                        document=document,
                        action=AuditEvent.Action.GRANT,
                        success=True,
                        ip_address=request.META.get("REMOTE_ADDR"),
                        details={
                            "recipient": recipient.username,
                            "access_level": access_level,
                        },
                    )

                return redirect(
                    "share_document",
                    document_id=document.pk,
                )
    else:
        form = DocumentShareForm()

    return render(
        request,
        "documents/share.html",
        {
            "document": document,
            "form": form,
            "active_grants": active_grants,
            "revoked_grants": document.grants.filter(
                revoked_at__isnull=False
            ).select_related("user", "granted_by"),
        },
    )


@login_required
@require_http_methods(["POST"])
def revoke_document_access(request, document_id, grant_id):
    document = get_authorized_document_or_log_denial(
        request,
        document_id,
        operation="share",
    )

    try:
        with transaction.atomic():
            grant = get_object_or_404(
                DocumentGrant.objects.select_for_update(),
                pk=grant_id,
                document=document,
            )

            if grant.revoked_at is None:
                grant.revoked_at = timezone.now()
                grant.save(update_fields=["revoked_at"])

                AuditEvent.objects.create(
                    actor=request.user,
                    document=document,
                    action=AuditEvent.Action.REVOKE,
                    success=True,
                    ip_address=request.META.get("REMOTE_ADDR"),
                    details={
                        "recipient": grant.user.username,
                        "access_level": grant.access_level,
                    },
                )
    except Http404:
        record_access_denied(
            actor=request.user,
            operation="revoke",
            document_id=document_id,
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        raise

    return redirect(
        "share_document",
        document_id=document.pk,
    )
