from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.shortcuts import render

from accounts.models import User
from audit.services import record_access_denied, verify_audit_chain

from .models import AuditEvent


@login_required
def audit_log(request):
    if request.user.role != User.Role.ADMIN:
        record_access_denied(
            actor=request.user,
            operation="audit_log",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return HttpResponseForbidden(
            "Only an administrator may open the activity ledger."
        )

    events = AuditEvent.objects.select_related("actor", "document").order_by("-pk")

    action = request.GET.get("action", "").strip()
    if action and action in AuditEvent.Action.values:
        events = events.filter(action=action)

    status = request.GET.get("status", "").strip()
    if status == "success":
        events = events.filter(success=True)
    elif status == "failed":
        events = events.filter(success=False)

    chain_valid, chain_errors = verify_audit_chain()
    page_obj = Paginator(events, 20).get_page(request.GET.get("page"))

    return render(
        request,
        "audit/audit_log.html",
        {
            "page_obj": page_obj,
            "actions": AuditEvent.Action.choices,
            "selected_action": action,
            "selected_status": status,
            "chain_valid": chain_valid,
            "chain_errors": chain_errors,
            "is_admin": True,
        },
    )
