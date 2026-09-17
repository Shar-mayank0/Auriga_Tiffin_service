from django.contrib import admin
from customers.models import Customer
from services.customer_service import get_customer_status


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["name", "phone", "address", "current_status", "created_at"]
    search_fields = ["name", "phone"]
    list_filter = []
    readonly_fields = ["created_at"]

    @admin.display(description="Status")
    def current_status(self, obj):
        ctx = get_customer_status(obj)
        return ctx.get("status", "INACTIVE")
