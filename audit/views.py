
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.shortcuts import render

from accounts.models import User
from .models import AuditEvent
from .services import verify_audit_chain


@login_required
def audit_log(request):
    # Temporary debugging information
    user_role = getattr(request.user, "role", None)

    print(
        "AUDIT DEBUG:",
        "authenticated =", request.user.is_authenticated,
        "username =", request.user.username,
        "role =", repr(user_role),
        "expected =", repr(User.Role.ADMIN),
        "matches =", user_role == User.Role.ADMIN,
    )

    # Only administrators can view the audit log
    if user_role != User.Role.ADMIN:
        return HttpResponseForbidden(
            "You do not have permission to view the audit log."
        )

    # Retrieve audit events
    events = AuditEvent.objects.select_related(
        "actor",
        "document",
    ).order_by("-pk")

    # Filter by action
    action = request.GET.get("action", "").strip()

    if action and action in AuditEvent.Action.values:
        events = events.filter(action=action)

    # Filter by outcome
    status = request.GET.get("status", "").strip()

    if status == "success":
        events = events.filter(success=True)
    elif status == "failed":
        events = events.filter(success=False)

    # Verify the audit hash chain
    is_valid, errors = verify_audit_chain()

    # Display 20 events per page
    paginator = Paginator(events, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "page_obj": page_obj,
        "actions": AuditEvent.Action.choices,
        "selected_action": action,
        "selected_status": status,
        "chain_valid": is_valid,
        "chain_errors": errors,
    }

    return render(
        request,
        "audit/audit_log.html",
        context,
    )
