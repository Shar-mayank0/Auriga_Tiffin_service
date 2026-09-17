from django.contrib import admin
from billing.models import BillingRecord


@admin.register(BillingRecord)
class BillingRecordAdmin(admin.ModelAdmin):
    list_display = [
        "id", "customer", "subscription", "billing_month",
        "delivered_weekdays", "paused_weekdays", "amount_due", "generated_at",
    ]
    list_filter = ["billing_month"]
    search_fields = ["customer__name", "customer__phone", "subscription__id"]
    readonly_fields = [
        "subscription", "customer", "billing_month", "ownership_from", "ownership_to",
        "total_weekdays_in_segment", "paused_weekdays", "delivered_weekdays",
        "daily_rate", "amount_due", "generated_at",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
