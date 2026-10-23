
import hashlib
import json


def calculate_event_hash(event):
    """Calculate a deterministic SHA-256 hash for an audit event."""
    payload = {
        "id": str(event.pk) if event.pk is not None else None,
        "actor_id": (
            str(event.actor_id)
            if event.actor_id is not None
            else None
        ),
        "document_id": (
            str(event.document_id)
            if event.document_id is not None
            else None
        ),
        "action": event.action,
        "success": event.success,
        "timestamp": (
            event.timestamp.isoformat()
            if event.timestamp
            else None
        ),
        "ip_address": event.ip_address,
        "details": event.details,
        "previous_hash": event.previous_hash,
    }

    canonical_data = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

    return hashlib.sha256(canonical_data).hexdigest()


def verify_audit_chain(events=None):
    """
    Verify event hashes and links in chronological insertion order.

    Returns:
        tuple: (is_valid, errors)
    """
    from .models import AuditEvent

    if events is None:
        events = AuditEvent.objects.order_by("pk")

    expected_previous_hash = ""
    errors = []

    for event in events:
        if event.previous_hash != expected_previous_hash:
            errors.append(
                f"Event {event.pk}: previous hash does not match."
            )

        expected_hash = calculate_event_hash(event)

        if event.event_hash != expected_hash:
            errors.append(
                f"Event {event.pk}: event hash does not match."
            )

        expected_previous_hash = event.event_hash

    return len(errors) == 0, errors


def record_access_denied(
    *,
    actor,
    operation,
    document_id=None,
    ip_address=None,
):
    """
    Record a denied operation without linking the event
    to the private document itself.
    """
    from .models import AuditEvent

    authenticated_actor = (
        actor
        if getattr(actor, "is_authenticated", False)
        else None
    )

    return AuditEvent.objects.create(
        actor=authenticated_actor,
        document=None,
        action=AuditEvent.Action.ACCESS_DENIED,
        success=False,
        ip_address=ip_address,
        details={
            "operation": str(operation)[:100],
            "requested_document_id": (
                str(document_id)[:100]
                if document_id is not None
                else None
            ),
        },
    )
