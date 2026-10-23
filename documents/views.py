import hashlib
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from audit.models import AuditEvent
from audit.services import record_access_denied, write_ledger_event

from .catalog import documents_in_reach, filter_shelf, known_categories, shelf_rows
from .forms import DocumentShareForm, DocumentUploadForm, ShelfSearchForm
from .models import Document, DocumentGrant
from .permissions import get_authorized_document

User = get_user_model()


def _client_ip(request):
    return request.META.get("REMOTE_ADDR")


def require_document_or_record_refusal(request, document_id, operation):
    capability = "read" if operation in {"download", "inspect"} else operation
    try:
        return get_authorized_document(
            request.user,
            document_id,
            action=capability,
        )
    except (Http404, PermissionDenied):
        record_access_denied(
            actor=request.user,
            operation=operation,
            document_id=document_id,
            ip_address=_client_ip(request),
        )
        raise


def record_role_refusal(request, operation):
    record_access_denied(
        actor=request.user,
        operation=operation,
        ip_address=_client_ip(request),
    )


def _sha256_of_upload(uploaded_file):
    digest = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        digest.update(chunk)
    uploaded_file.seek(0)
    return digest.hexdigest()


@login_required
@require_GET
def dashboard(request):
    reachable = documents_in_reach(request.user)
    return render(
        request,
        "documents/dashboard.html",
        {
            "reachable_count": reachable.count(),
            "owned_count": reachable.filter(owner=request.user).count(),
            "received_count": reachable.exclude(owner=request.user).count(),
            "is_admin": request.user.role == User.Role.ADMIN,
        },
    )


@login_required
@require_GET
def my_documents(request):
    search = ShelfSearchForm(request.GET or None)
    queryset = documents_in_reach(request.user)
    params = request.GET if search.is_valid() else {}
    queryset = filter_shelf(queryset, params)

    return render(
        request,
        "documents/my_documents.html",
        {
            "search": search,
            "rows": shelf_rows(request.user, queryset),
            "categories": known_categories(request.user),
            "is_admin": request.user.role == User.Role.ADMIN,
            "can_upload": request.user.role in {User.Role.OWNER, User.Role.ADMIN},
        },
    )


@login_required
@require_GET
def inspect_document(request, document_id):
    document = require_document_or_record_refusal(
        request, document_id, operation="inspect"
    )
    owned = document.owner_id == request.user.pk
    grant = None
    if not owned:
        grant = DocumentGrant.objects.filter(
            document=document,
            user=request.user,
            revoked_at__isnull=True,
        ).first()

    return render(
        request,
        "documents/inspect.html",
        {
            "document": document,
            "owned": owned,
            "can_edit": owned
            or (
                grant is not None
                and grant.access_level == DocumentGrant.AccessLevel.EDIT
            ),
            "is_admin": request.user.role == User.Role.ADMIN,
        },
    )


@login_required
@require_GET
def download_document(request, document_id):
    document = require_document_or_record_refusal(
        request, document_id, operation="download"
    )

    if not document.file or not document.file.storage.exists(document.file.name):
        raise Http404("The stored file is missing.")

    write_ledger_event(
        actor=request.user,
        document=document,
        action=AuditEvent.Action.DOWNLOAD,
        ip_address=_client_ip(request),
        details={"operation": "download", "filename": document.original_filename},
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
    if request.user.role not in {User.Role.OWNER, User.Role.ADMIN}:
        record_role_refusal(request, "upload")
        return render(
            request,
            "documents/upload.html",
            {
                "form": DocumentUploadForm(),
                "error": "This account is not allowed to place files in the vault.",
                "is_admin": request.user.role == User.Role.ADMIN,
            },
            status=403,
        )

    form = DocumentUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        uploaded = form.cleaned_data["file"]
        document = form.save(commit=False)
        document.owner = request.user
        document.original_filename = Path(uploaded.name).name[:255]
        document.content_type = "application/octet-stream"
        document.size_bytes = uploaded.size
        document.sha256 = _sha256_of_upload(uploaded)

        with transaction.atomic():
            document.save()
            write_ledger_event(
                actor=request.user,
                document=document,
                action=AuditEvent.Action.UPLOAD,
                ip_address=_client_ip(request),
                details={
                    "operation": "upload",
                    "size_bytes": document.size_bytes,
                    "sha256": document.sha256,
                },
            )

        return render(
            request,
            "documents/upload_success.html",
            {"document": document, "is_admin": request.user.role == User.Role.ADMIN},
        )

    return render(
        request,
        "documents/upload.html",
        {
            "form": form,
            "is_admin": request.user.role == User.Role.ADMIN,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def edit_document(request, document_id):
    document = require_document_or_record_refusal(
        request, document_id, operation="edit"
    )
    error = ""

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        category = request.POST.get("category", "").strip()
        description = request.POST.get("description", "").strip()

        if not title or not category:
            error = "Title and category are required."
        elif len(title) > 255 or len(category) > 100:
            error = "Title must be at most 255 characters and category at most 100."
        else:
            with transaction.atomic():
                document.title = title
                document.category = category
                document.description = description
                document.save(
                    update_fields=["title", "category", "description", "updated_at"]
                )
                write_ledger_event(
                    actor=request.user,
                    document=document,
                    action=AuditEvent.Action.EDIT,
                    ip_address=_client_ip(request),
                    details={"operation": "edit"},
                )
            return redirect("inspect_document", document_id=document.pk)

    return render(
        request,
        "documents/edit.html",
        {
            "document": document,
            "error": error,
            "is_admin": request.user.role == User.Role.ADMIN,
        },
        status=400 if error else 200,
    )


@login_required
@require_http_methods(["GET", "POST"])
def share_document(request, document_id):
    document = require_document_or_record_refusal(
        request, document_id, operation="share"
    )
    form = DocumentShareForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        username = form.cleaned_data["username"]
        access_level = form.cleaned_data["access_level"]
        recipient = User.objects.filter(username__iexact=username, is_active=True).first()

        if recipient is None:
            form.add_error("username", "No active account uses that username.")
        elif recipient.pk == document.owner_id:
            form.add_error("username", "The owner already holds the document.")
        else:
            with transaction.atomic():
                grant = (
                    DocumentGrant.objects.select_for_update()
                    .filter(document=document, user=recipient)
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

                write_ledger_event(
                    actor=request.user,
                    document=document,
                    action=AuditEvent.Action.GRANT,
                    ip_address=_client_ip(request),
                    details={
                        "recipient": recipient.username,
                        "access_level": access_level,
                    },
                )
            return redirect("share_document", document_id=document.pk)

    return render(
        request,
        "documents/share.html",
        {
            "document": document,
            "form": form,
            "live_grants": document.grants.filter(revoked_at__isnull=True).select_related(
                "user", "granted_by"
            ),
            "withdrawn_grants": document.grants.filter(
                revoked_at__isnull=False
            ).select_related("user", "granted_by"),
            "is_admin": request.user.role == User.Role.ADMIN,
        },
    )


@login_required
@require_http_methods(["POST"])
def revoke_document_access(request, document_id, grant_id):
    document = require_document_or_record_refusal(
        request, document_id, operation="share"
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
                write_ledger_event(
                    actor=request.user,
                    document=document,
                    action=AuditEvent.Action.REVOKE,
                    ip_address=_client_ip(request),
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
            ip_address=_client_ip(request),
        )
        raise

    return redirect("share_document", document_id=document.pk)


@login_required
@require_http_methods(["GET", "POST"])
def retire_document(request, document_id):
    document = require_document_or_record_refusal(
        request, document_id, operation="delete"
    )

    if request.method == "POST":
        snapshot = {
            "operation": "delete",
            "title": document.title,
            "document_id": str(document.pk),
            "filename": document.original_filename,
        }
        stored_name = document.file.name if document.file else ""
        storage = document.file.storage if document.file else None

        with transaction.atomic():
            write_ledger_event(
                actor=request.user,
                document=document,
                action=AuditEvent.Action.DELETE,
                ip_address=_client_ip(request),
                details=snapshot,
            )
            document.delete()

        if storage and stored_name and storage.exists(stored_name):
            storage.delete(stored_name)

        return redirect("my_documents")

    return render(
        request,
        "documents/retire.html",
        {
            "document": document,
            "is_admin": request.user.role == User.Role.ADMIN,
        },
    )
