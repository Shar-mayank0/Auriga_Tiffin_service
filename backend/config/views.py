from datetime import date as date_type
from django.contrib.auth.models import User
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from audit.models import AuditLog
from billing.models import BillingRecord
from config.permissions import IsStaff
from config.serializers import (
    AuditLogSerializer,
    BillingRecordSerializer,
    CreatePauseSerializer,
    CustomerSerializer,
    CustomerUpdateSerializer,
    ImportResultSerializer,
    OutboxEntrySerializer,
    PlanSerializer,
    RegisterSerializer,
    SubscribeSerializer,
    SubscriptionSerializer,
    SystemClockSerializer,
    TransferSerializer,
)
from customers.models import Customer
from notifications.models import OutboxEntry, SystemClock
from plans.models import Plan
from services.billing_engine import generate_bill
from services.import_service import run_import
from services.notification_service import dispatch
from services.pause_service import create_pause, resume_pause
from services.transfer_service import get_owner_on_date, transfer
from subscriptions.models import PausePeriod, Subscription, SubscriptionOwnershipPeriod


# ─── Auth ─────────────────────────────────────────────────────────────────────

class RegisterView(APIView):
    """POST /api/auth/register/ — public endpoint to create a new user + customer profile."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        # Create Customer profile automatically
        Customer.objects.create(
            user=user,
            name=user.get_full_name() or user.username,
            phone=request.data.get("phone", ""),
        )
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "message": "Registration successful.",
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


class LogoutView(APIView):
    """POST /api/auth/logout/ — blacklist the refresh token."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response({"detail": "Refresh token required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            return Response({"detail": "Invalid or already blacklisted token."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"message": "Logout successful."}, status=status.HTTP_200_OK)


# ─── Plans ────────────────────────────────────────────────────────────────────

class PlanListView(generics.ListAPIView):
    """GET /api/plans/ — list all active plans."""
    serializer_class = PlanSerializer
    permission_classes = [IsAuthenticated]
    queryset = Plan.objects.filter(is_active=True)


# ─── Customers ────────────────────────────────────────────────────────────────

class CustomerMeView(APIView):
    """GET/PATCH /api/customers/me/ — view or update own profile."""
    permission_classes = [IsAuthenticated]

    def get_customer(self, request):
        try:
            return request.user.customer_profile
        except Customer.DoesNotExist:
            return None

    def get(self, request):
        customer = self.get_customer(request)
        if not customer:
            return Response({"detail": "Customer profile not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(CustomerSerializer(customer).data)

    def patch(self, request):
        customer = self.get_customer(request)
        if not customer:
            return Response({"detail": "Customer profile not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = CustomerUpdateSerializer(customer, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(CustomerSerializer(customer).data)


class CustomerStatusView(APIView):
    """GET /api/customers/me/status/ — returns subscription status, active pause, plan."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from services.customer_service import get_customer_status
        try:
            customer = request.user.customer_profile
        except Customer.DoesNotExist:
            return Response({"detail": "Customer profile not found."}, status=status.HTTP_404_NOT_FOUND)

        ctx = get_customer_status(customer)
        plan_data = PlanSerializer(ctx["plan"]).data if ctx.get("plan") else None
        pause_data = None
        if ctx.get("active_pause"):
            from config.serializers import PausePeriodSerializer
            pause_data = CreatePauseSerializer(ctx["active_pause"]).data

        return Response({
            "status": ctx["status"],
            "plan": plan_data,
            "active_pause": pause_data,
        })


class CustomerListView(generics.ListAPIView):
    """GET /api/customers/ — staff only, list all customers."""
    serializer_class = CustomerSerializer
    permission_classes = [IsStaff]
    queryset = Customer.objects.select_related("user").all()


# ─── Subscriptions ────────────────────────────────────────────────────────────

class MySubscriptionView(APIView):
    """GET /api/subscriptions/mine/ — current customer's active subscription."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            customer = request.user.customer_profile
        except Customer.DoesNotExist:
            return Response({"detail": "No customer profile."}, status=404)

        op = (
            SubscriptionOwnershipPeriod.objects.filter(customer=customer, to_date__isnull=True)
            .select_related("subscription", "subscription__plan")
            .first()
        )
        if not op:
            return Response({"detail": "No active subscription found."}, status=404)
        return Response(SubscriptionSerializer(op.subscription).data)


class SubscribeView(APIView):
    """POST /api/subscriptions/ — subscribe to a plan."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SubscribeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            customer = request.user.customer_profile
        except Customer.DoesNotExist:
            return Response({"detail": "No customer profile found."}, status=400)

        # Check if already has an active subscription
        existing = SubscriptionOwnershipPeriod.objects.filter(
            customer=customer, to_date__isnull=True
        ).exclude(subscription__status=Subscription.Status.CANCELLED).first()
        if existing:
            return Response({"detail": "Already has an active subscription."}, status=400)

        plan = serializer.validated_data["plan_id"]
        start_date = serializer.validated_data["start_date"]

        sub = Subscription.objects.create(
            plan=plan,
            start_date=start_date,
            status=Subscription.Status.ACTIVE,
        )
        SubscriptionOwnershipPeriod.objects.create(
            subscription=sub, customer=customer, from_date=start_date, to_date=None
        )
        AuditLog.objects.create(
            event_type=AuditLog.EventType.SUBSCRIBED,
            entity_type="Subscription",
            entity_id=sub.id,
            operator=request.user if request.user.is_staff else None,
            notes=f"{customer.name} subscribed to {plan.name} from {start_date}",
        )
        return Response(SubscriptionSerializer(sub).data, status=201)


class SubscriptionTransferView(APIView):
    """POST /api/subscriptions/{id}/transfer/ — staff only, transfer to new customer."""
    permission_classes = [IsStaff]

    def post(self, request, pk):
        try:
            sub = Subscription.objects.get(pk=pk)
        except Subscription.DoesNotExist:
            return Response({"detail": "Subscription not found."}, status=404)

        serializer = TransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_customer = serializer.validated_data["new_customer_id"]
        transfer_date = serializer.validated_data["transfer_date"]

        try:
            new_period = transfer(sub, new_customer, transfer_date, operator=request.user)
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)

        return Response({"message": "Transfer successful.", "new_ownership_from": new_period.from_date})


# ─── Pauses ───────────────────────────────────────────────────────────────────

class PauseListCreateView(APIView):
    """
    GET /api/pauses/   — list own pause periods
    POST /api/pauses/  — create a new pause
    """
    permission_classes = [IsAuthenticated]

    def _get_sub(self, request):
        try:
            customer = request.user.customer_profile
        except Customer.DoesNotExist:
            return None
        op = SubscriptionOwnershipPeriod.objects.filter(customer=customer, to_date__isnull=True).first()
        return op.subscription if op else None

    def get(self, request):
        sub = self._get_sub(request)
        if not sub:
            return Response({"detail": "No active subscription."}, status=404)
        pauses = sub.pause_periods.all()
        return Response(CreatePauseSerializer(pauses, many=True).data)

    def post(self, request):
        # Staff can target any subscription via ?sub_id=
        if request.user.is_staff and "sub_id" in request.query_params:
            try:
                sub = Subscription.objects.get(pk=request.query_params["sub_id"])
            except Subscription.DoesNotExist:
                return Response({"detail": "Subscription not found."}, status=404)
        else:
            sub = self._get_sub(request)
            if not sub:
                return Response({"detail": "No active subscription."}, status=404)

        serializer = CreatePauseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            pause = create_pause(
                sub,
                start_date=serializer.validated_data["start_date"],
                end_date=serializer.validated_data.get("end_date"),
                operator=request.user,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)

        return Response(CreatePauseSerializer(pause).data, status=201)


class PauseResumeView(APIView):
    """PATCH /api/pauses/{id}/resume/ — resume a specific pause."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            pause = PausePeriod.objects.select_related("subscription").get(pk=pk)
        except PausePeriod.DoesNotExist:
            return Response({"detail": "Pause period not found."}, status=404)

        sub = pause.subscription
        if not request.user.is_staff:
            try:
                customer = request.user.customer_profile
            except Customer.DoesNotExist:
                return Response(status=403)
            op = SubscriptionOwnershipPeriod.objects.filter(
                customer=customer, subscription=sub, to_date__isnull=True
            ).exists()
            if not op:
                return Response(status=403)

        resume_date = request.data.get("resume_date")
        parsed_date = None
        if resume_date:
            from datetime import datetime
            try:
                parsed_date = datetime.strptime(resume_date, "%Y-%m-%d").date()
            except ValueError:
                return Response({"detail": "Invalid resume_date format. Use YYYY-MM-DD."}, status=400)

        try:
            resume_pause(sub, resume_date=parsed_date, pause_id=pause.id, operator=request.user)
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)

        return Response({"message": "Pause resumed successfully."})


# ─── Billing ─────────────────────────────────────────────────────────────────

class MyBillingView(generics.ListAPIView):
    """GET /api/billing/ — customer sees own bills."""
    serializer_class = BillingRecordSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        try:
            customer = self.request.user.customer_profile
        except Customer.DoesNotExist:
            return BillingRecord.objects.none()
        return BillingRecord.objects.filter(customer=customer).order_by("-billing_month")


class GenerateBillView(APIView):
    """POST /api/billing/generate/ — staff only, generate bill for a subscription+month."""
    permission_classes = [IsStaff]

    def post(self, request):
        sub_id = request.data.get("subscription_id")
        billing_month = request.data.get("billing_month")  # expects YYYY-MM-DD (first of month)
        if not sub_id or not billing_month:
            return Response({"detail": "subscription_id and billing_month are required."}, status=400)
        try:
            sub = Subscription.objects.get(pk=sub_id)
        except Subscription.DoesNotExist:
            return Response({"detail": "Subscription not found."}, status=404)
        try:
            from datetime import datetime
            month_date = datetime.strptime(billing_month, "%Y-%m-%d").date()
        except ValueError:
            return Response({"detail": "billing_month must be YYYY-MM-DD."}, status=400)

        records = generate_bill(sub, month_date, operator=request.user)
        return Response(BillingRecordSerializer(records, many=True).data, status=200)


# ─── Clock & Outbox (T1) ─────────────────────────────────────────────────────

class ClockView(APIView):
    """
    GET /api/clock/  — return current system date
    POST /api/clock/ — advance SystemClock by 1 day, dispatch notifications
    Staff-only for POST; authenticated for GET.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        clock = SystemClock.objects.first()
        if not clock:
            return Response({"detail": "SystemClock not initialized."}, status=503)
        return Response(SystemClockSerializer(clock).data)

    def post(self, request):
        if not request.user.is_staff:
            return Response(status=403)

        clock = SystemClock.objects.first()
        if not clock:
            return Response({"detail": "SystemClock not initialized."}, status=503)

        # Advance by 1 day (or to a specified date)
        target_date = request.data.get("date")
        if target_date:
            from datetime import datetime
            try:
                new_date = datetime.strptime(target_date, "%Y-%m-%d").date()
            except ValueError:
                return Response({"detail": "date must be YYYY-MM-DD."}, status=400)
            if new_date <= clock.current_date:
                return Response({"detail": "New date must be after current system date (idempotency)."}, status=400)
        else:
            from datetime import timedelta
            new_date = clock.current_date + timedelta(days=1)

        clock.current_date = new_date
        clock.save()

        dispatched = dispatch(new_date, operator=request.user)
        return Response({
            "current_date": str(new_date),
            "notifications_dispatched": len(dispatched),
        })


class OutboxListView(generics.ListAPIView):
    """GET /api/outbox/ — staff list of all outbox entries (grader endpoint)."""
    serializer_class = OutboxEntrySerializer
    permission_classes = [IsStaff]

    def get_queryset(self):
        qs = OutboxEntry.objects.select_related("customer").order_by("-delivery_date")
        date_filter = self.request.query_params.get("date")
        if date_filter:
            qs = qs.filter(delivery_date=date_filter)
        return qs


# ─── Import (T4) ─────────────────────────────────────────────────────────────

class ImportCustomersView(APIView):
    """POST /api/import/customers/ — staff only, bulk import customers from raw JSON rows."""
    permission_classes = [IsStaff]

    def post(self, request):
        raw_data = request.data
        if not isinstance(raw_data, list):
            return Response({"detail": "Expected a JSON array of rows."}, status=400)

        result = run_import(raw_data, operator=request.user)
        return Response(result, status=207)  # 207 Multi-Status — partial success possible


# ─── Audit ───────────────────────────────────────────────────────────────────

class AuditLogListView(generics.ListAPIView):
    """GET /api/audit/ — staff only, list of all audit log entries."""
    serializer_class = AuditLogSerializer
    permission_classes = [IsStaff]

    def get_queryset(self):
        qs = AuditLog.objects.select_related("operator").order_by("-timestamp")
        entity_type = self.request.query_params.get("entity_type")
        entity_id = self.request.query_params.get("entity_id")
        if entity_type:
            qs = qs.filter(entity_type=entity_type)
        if entity_id:
            qs = qs.filter(entity_id=entity_id)
        return qs
