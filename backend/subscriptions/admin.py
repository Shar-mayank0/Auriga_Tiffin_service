from datetime import date
from django import forms
from django.contrib import admin, messages
from subscriptions.models import PausePeriod, Subscription, SubscriptionOwnershipPeriod


class PausePeriodInline(admin.TabularInline):
    model = PausePeriod
    extra = 0
    readonly_fields = ["created_at", "resumed_at"]
    fields = ["start_date", "end_date", "created_at", "resumed_at"]


class OwnershipPeriodInline(admin.TabularInline):
    model = SubscriptionOwnershipPeriod
    extra = 0
    readonly_fields = ["from_date"]
    fields = ["customer", "from_date", "to_date"]


class GenerateBillForm(forms.Form):
    billing_month = forms.DateField(
        label="Billing month (YYYY-MM-01)",
        initial=date.today().replace(day=1),
        widget=forms.DateInput(attrs={"type": "date"}),
    )


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["id", "plan", "status", "start_date", "end_date", "created_at"]
    list_filter = ["status", "plan"]
    search_fields = ["id", "plan__name"]
    readonly_fields = ["created_at"]
    inlines = [OwnershipPeriodInline, PausePeriodInline]
    actions = ["generate_bill_for_month"]

    @admin.action(description="Generate Bill for selected subscription(s)")
    def generate_bill_for_month(self, request, queryset):
        from services.billing_engine import generate_bill
        billing_month = date.today().replace(day=1)
        total_created = 0
        for sub in queryset:
            records = generate_bill(sub, billing_month, operator=request.user)
            total_created += len(records)
        self.message_user(
            request,
            f"Generated {total_created} billing record(s) for {billing_month:%B %Y}.",
            messages.SUCCESS,
        )


@admin.register(SubscriptionOwnershipPeriod)
class OwnershipPeriodAdmin(admin.ModelAdmin):
    list_display = ["subscription", "customer", "from_date", "to_date"]
    list_filter = ["from_date"]


@admin.register(PausePeriod)
class PausePeriodAdmin(admin.ModelAdmin):
    list_display = ["subscription", "start_date", "end_date", "created_at", "resumed_at"]
    list_filter = ["start_date"]
