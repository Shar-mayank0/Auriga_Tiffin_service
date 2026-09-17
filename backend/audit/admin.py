from django.contrib import admin
from audit.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["event_type", "entity_type", "entity_id", "operator", "timestamp", "notes"]
    list_filter = ["event_type", "entity_type"]
    search_fields = ["entity_id", "notes", "operator__username"]
    readonly_fields = ["event_type", "entity_type", "entity_id", "notes", "timestamp", "operator"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
