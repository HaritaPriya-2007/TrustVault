from django.contrib import admin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = (
        "timestamp",
        "actor",
        "action",
        "document",
        "success",
    )
    list_filter = ("action", "success", "timestamp")
    search_fields = ("actor__username", "document__title")
    readonly_fields = (
        "actor",
        "document",
        "action",
        "success",
        "timestamp",
        "ip_address",
        "details",
        "previous_hash",
        "event_hash",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False