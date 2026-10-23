import hashlib
import json


def calculate_event_hash(event):
    payload = {
        "id": str(event.pk) if event.pk is not None else None,
        "actor_id": str(event.actor_id) if event.actor_id is not None else None,
        "document_id": (
            str(event.document_id) if event.document_id is not None else None
        ),
        "action": event.action,
        "success": event.success,
        "timestamp": event.timestamp.isoformat() if event.timestamp else None,
        "ip_address": event.ip_address,
        "details": event.details,
        "previous_hash": event.previous_hash,
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def verify_audit_chain(events=None):
    from .models import AuditEvent

    if events is None:
        events = AuditEvent.objects.order_by("pk")

    expected_previous = ""
    errors = []

    for event in events:
        if event.previous_hash != expected_previous:
            errors.append(f"Event {event.pk}: previous hash does not match.")

        expected_hash = calculate_event_hash(event)
        if event.event_hash != expected_hash:
            errors.append(f"Event {event.pk}: event hash does not match.")

        expected_previous = event.event_hash

    return len(errors) == 0, errors


def write_ledger_event(
    *,
    actor,
    action,
    success=True,
    document=None,
    ip_address=None,
    details=None,
):
    from .models import AuditEvent

    return AuditEvent.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        document=document,
        action=action,
        success=success,
        ip_address=ip_address,
        details=details or {},
    )


def record_access_denied(
    *,
    actor,
    operation,
    document_id=None,
    ip_address=None,
):
    from .models import AuditEvent

    return write_ledger_event(
        actor=actor,
        document=None,
        action=AuditEvent.Action.ACCESS_DENIED,
        success=False,
        ip_address=ip_address,
        details={
            "operation": str(operation)[:100],
            "requested_document_id": (
                str(document_id)[:100] if document_id is not None else None
            ),
        },
    )
