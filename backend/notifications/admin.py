from django.contrib import admin
from notifications.models import OutboxEntry, SystemClock


@admin.register(SystemClock)
class SystemClockAdmin(admin.ModelAdmin):
    list_display = ["id", "current_date"]
    readonly_fields = ["id"]

    def has_add_permission(self, request):
        # Only allow if no clock exists yet
        return not SystemClock.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OutboxEntry)
class OutboxEntryAdmin(admin.ModelAdmin):
    list_display = ["customer", "delivery_date", "message", "created_at"]
    list_filter = ["delivery_date"]
    search_fields = ["customer__name", "customer__phone"]
    readonly_fields = ["customer", "delivery_date", "message", "created_at"]
    ordering = ["-delivery_date"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
