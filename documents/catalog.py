from datetime import datetime, time

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date

from .models import Document, DocumentGrant


def documents_in_reach(user):
    """Documents the signed-in person actually holds: owned or live grant."""
    return (
        Document.objects.filter(
            Q(owner_id=user.pk)
            | Q(
                grants__user_id=user.pk,
                grants__revoked_at__isnull=True,
            )
        )
        .select_related("owner")
        .distinct()
    )


def filter_shelf(queryset, params):
    """
    Narrow a document queryset by title/filename, owner, category, and dates.

    Empty filters leave the queryset unchanged.
    """
    needle = (params.get("q") or "").strip()
    category = (params.get("category") or "").strip()
    owner = (params.get("owner") or "").strip()
    after = (params.get("after") or "").strip()
    before = (params.get("before") or "").strip()

    if needle:
        queryset = queryset.filter(
            Q(title__icontains=needle)
            | Q(original_filename__icontains=needle)
            | Q(description__icontains=needle)
        )

    if category:
        queryset = queryset.filter(category__icontains=category)

    if owner:
        queryset = queryset.filter(
            Q(owner__username__icontains=owner)
            | Q(owner__first_name__icontains=owner)
            | Q(owner__last_name__icontains=owner)
        )

    after_date = parse_date(after) if after else None
    before_date = parse_date(before) if before else None
    tz = timezone.get_current_timezone()

    if after_date:
        start = timezone.make_aware(datetime.combine(after_date, time.min), tz)
        queryset = queryset.filter(created_at__gte=start)

    if before_date:
        end = timezone.make_aware(datetime.combine(before_date, time.max), tz)
        queryset = queryset.filter(created_at__lte=end)

    return queryset.order_by("-created_at")


def shelf_rows(user, queryset):
    """Attach action flags for the signed-in person without leaking extra grants."""
    rows = []
    live_grants = {
        grant.document_id: grant
        for grant in DocumentGrant.objects.filter(
            user_id=user.pk,
            revoked_at__isnull=True,
            document_id__in=queryset.values_list("pk", flat=True),
        )
    }

    for document in queryset:
        owned = document.owner_id == user.pk
        grant = None if owned else live_grants.get(document.pk)
        rows.append(
            {
                "document": document,
                "owned": owned,
                "can_read": owned or grant is not None,
                "can_edit": owned
                or (
                    grant is not None
                    and grant.access_level == DocumentGrant.AccessLevel.EDIT
                ),
                "can_share": owned,
                "can_retire": owned,
            }
        )
    return rows


def known_categories(user):
    return (
        documents_in_reach(user)
        .exclude(category="")
        .values_list("category", flat=True)
        .distinct()
        .order_by("category")
    )
