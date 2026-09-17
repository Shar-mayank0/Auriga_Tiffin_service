from rest_framework import serializers
from django.contrib.auth.models import User
from customers.models import Customer
from plans.models import Plan
from subscriptions.models import Subscription, SubscriptionOwnershipPeriod, PausePeriod
from billing.models import BillingRecord
from notifications.models import SystemClock, OutboxEntry
from audit.models import AuditLog


# ─── Auth ────────────────────────────────────────────────────────────────────

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    password2 = serializers.CharField(write_only=True, label="Confirm password")

    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name", "password", "password2"]

    def validate(self, data):
        if data["password"] != data["password2"]:
            raise serializers.ValidationError({"password2": "Passwords do not match."})
        return data

    def create(self, validated_data):
        validated_data.pop("password2")
        return User.objects.create_user(**validated_data)


# ─── Plans ────────────────────────────────────────────────────────────────────

class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ["id", "name", "monthly_price", "effective_from", "is_active"]


# ─── Customers ───────────────────────────────────────────────────────────────

class CustomerSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Customer
        fields = ["id", "username", "email", "name", "phone", "address", "created_at"]
        read_only_fields = ["id", "created_at"]


class CustomerUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["name", "address"]


# ─── Subscriptions ────────────────────────────────────────────────────────────

class OwnershipPeriodSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)

    class Meta:
        model = SubscriptionOwnershipPeriod
        fields = ["id", "customer", "customer_name", "from_date", "to_date"]


class PausePeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PausePeriod
        fields = ["id", "start_date", "end_date", "created_at", "resumed_at"]
        read_only_fields = ["id", "created_at", "resumed_at"]


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    pause_periods = PausePeriodSerializer(many=True, read_only=True)
    ownership_periods = OwnershipPeriodSerializer(many=True, read_only=True)

    class Meta:
        model = Subscription
        fields = [
            "id", "plan", "start_date", "end_date", "status",
            "created_at", "pause_periods", "ownership_periods",
        ]


class SubscribeSerializer(serializers.Serializer):
    plan_id = serializers.PrimaryKeyRelatedField(queryset=Plan.objects.filter(is_active=True))
    start_date = serializers.DateField()


class TransferSerializer(serializers.Serializer):
    new_customer_id = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    transfer_date = serializers.DateField()


# ─── Pauses ───────────────────────────────────────────────────────────────────

class CreatePauseSerializer(serializers.Serializer):
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False, allow_null=True)

    def validate(self, data):
        end = data.get("end_date")
        if end and end < data["start_date"]:
            raise serializers.ValidationError("end_date cannot be before start_date.")
        return data


# ─── Billing ─────────────────────────────────────────────────────────────────

class BillingRecordSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source="subscription.plan.name", read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True)

    class Meta:
        model = BillingRecord
        fields = [
            "id", "subscription", "customer", "customer_name", "plan_name",
            "billing_month", "ownership_from", "ownership_to",
            "total_weekdays_in_segment", "paused_weekdays", "delivered_weekdays",
            "daily_rate", "amount_due", "generated_at",
        ]


# ─── Notifications / Clock ────────────────────────────────────────────────────

class SystemClockSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemClock
        fields = ["id", "current_date"]


class OutboxEntrySerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_phone = serializers.CharField(source="customer.phone", read_only=True)

    class Meta:
        model = OutboxEntry
        fields = ["id", "customer", "customer_name", "customer_phone", "delivery_date", "message", "created_at"]


# ─── Audit ────────────────────────────────────────────────────────────────────

class AuditLogSerializer(serializers.ModelSerializer):
    operator_username = serializers.CharField(source="operator.username", read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = ["id", "event_type", "entity_type", "entity_id", "notes", "timestamp", "operator_username"]


# ─── Import ───────────────────────────────────────────────────────────────────

class ImportRowSerializer(serializers.Serializer):
    name = serializers.CharField()
    phone = serializers.CharField()
    address = serializers.CharField(required=False, default="")
    start_date = serializers.CharField()
    plan_id = serializers.IntegerField(required=False, allow_null=True)


class ImportResultSerializer(serializers.Serializer):
    imported = serializers.IntegerField()
    deduped = serializers.IntegerField()
    rejected = serializers.ListField(child=serializers.DictField())
