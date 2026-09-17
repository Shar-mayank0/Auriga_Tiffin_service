"""
Full API endpoint test suite for Auriga Tiffin Service.
Covers auth, customers, plans, subscriptions, pauses, billing, clock, outbox, import, audit.
"""
from datetime import date, timedelta
import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from audit.models import AuditLog
from billing.models import BillingRecord
from customers.models import Customer
from notifications.models import OutboxEntry, SystemClock
from plans.models import Plan
from subscriptions.models import Subscription, SubscriptionOwnershipPeriod


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def plan(db):
    return Plan.objects.create(name="Test Plan", monthly_price="1000.00", effective_from=date(2026, 1, 1))


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(username="staff", password="staffpass", is_staff=True)


@pytest.fixture
def regular_user(db):
    user = User.objects.create_user(username="customer1", password="pass123")
    Customer.objects.create(user=user, name="Alice", phone="9111111111")
    return user


@pytest.fixture
def regular_user2(db):
    user = User.objects.create_user(username="customer2", password="pass123")
    Customer.objects.create(user=user, name="Bob", phone="9222222222")
    return user


@pytest.fixture
def auth_client(regular_user):
    # Each fixture gets its own client instance to avoid shared-auth contamination
    client = APIClient()
    client.force_authenticate(user=regular_user)
    return client


@pytest.fixture
def staff_client(staff_user):
    client = APIClient()
    client.force_authenticate(user=staff_user)
    return client


@pytest.fixture
def active_subscription(db, regular_user, plan):
    customer = regular_user.customer_profile
    sub = Subscription.objects.create(plan=plan, start_date=date(2026, 9, 1), status=Subscription.Status.ACTIVE)
    SubscriptionOwnershipPeriod.objects.create(subscription=sub, customer=customer, from_date=date(2026, 9, 1), to_date=None)
    return sub


@pytest.fixture
def system_clock(db):
    # Clear any clock created by data migration before creating a fresh test one
    SystemClock.objects.all().delete()
    return SystemClock.objects.create(current_date=date(2026, 9, 1))


# ─── Auth ────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_register(api_client, plan):
    resp = api_client.post("/api/auth/register/", {
        "username": "newuser",
        "email": "new@example.com",
        "password": "securepass",
        "password2": "securepass",
        "phone": "9000000000",
    })
    assert resp.status_code == 201
    assert "access" in resp.data
    assert User.objects.filter(username="newuser").exists()


@pytest.mark.django_db
def test_register_password_mismatch(api_client):
    resp = api_client.post("/api/auth/register/", {
        "username": "newuser2",
        "email": "new2@example.com",
        "password": "pass1",
        "password2": "pass2",
    })
    assert resp.status_code == 400


@pytest.mark.django_db
def test_login(api_client, regular_user):
    resp = api_client.post("/api/auth/login/", {"username": "customer1", "password": "pass123"})
    assert resp.status_code == 200
    assert "access" in resp.data


@pytest.mark.django_db
def test_login_wrong_password(api_client, regular_user):
    resp = api_client.post("/api/auth/login/", {"username": "customer1", "password": "wrongpass"})
    assert resp.status_code == 401


@pytest.mark.django_db
def test_logout(auth_client, regular_user):
    # Get a real refresh token
    client = APIClient()
    resp = client.post("/api/auth/login/", {"username": "customer1", "password": "pass123"})
    refresh = resp.data["refresh"]
    auth_client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")
    out = auth_client.post("/api/auth/logout/", {"refresh": refresh})
    assert out.status_code == 200


# ─── Plans ────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_plans_list_authenticated(auth_client, plan):
    resp = auth_client.get("/api/plans/")
    assert resp.status_code == 200
    # At least the fixture plan exists (seed plans may also appear)
    plan_names = [p["name"] for p in resp.data]
    assert "Test Plan" in plan_names


@pytest.mark.django_db
def test_plans_list_unauthenticated(api_client, plan):
    resp = api_client.get("/api/plans/")
    assert resp.status_code == 401


# ─── Customers ────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_customer_me(auth_client, regular_user):
    resp = auth_client.get("/api/customers/me/")
    assert resp.status_code == 200
    assert resp.data["name"] == "Alice"


@pytest.mark.django_db
def test_customer_me_update(auth_client, regular_user):
    resp = auth_client.patch("/api/customers/me/", {"name": "Alice Updated", "address": "New Address"})
    assert resp.status_code == 200
    assert resp.data["name"] == "Alice Updated"


@pytest.mark.django_db
def test_customer_list_staff_only(regular_user, staff_user):
    # Use separate clients to avoid shared authentication state
    client_regular = APIClient()
    client_regular.force_authenticate(user=regular_user)
    resp = client_regular.get("/api/customers/")
    assert resp.status_code == 403

    client_staff = APIClient()
    client_staff.force_authenticate(user=staff_user)
    resp2 = client_staff.get("/api/customers/")
    assert resp2.status_code == 200


@pytest.mark.django_db
def test_customer_status(auth_client, active_subscription):
    resp = auth_client.get("/api/customers/me/status/")
    assert resp.status_code == 200
    assert resp.data["status"] == "ACTIVE"
    assert resp.data["plan"]["name"] == "Test Plan"


# ─── Subscriptions ────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_subscribe(auth_client, plan, regular_user):
    resp = auth_client.post("/api/subscriptions/", {
        "plan_id": plan.id,
        "start_date": "2026-09-01",
    })
    assert resp.status_code == 201
    assert resp.data["status"] == "ACTIVE"
    assert AuditLog.objects.filter(event_type=AuditLog.EventType.SUBSCRIBED).count() == 1


@pytest.mark.django_db
def test_subscribe_duplicate_blocked(auth_client, plan, active_subscription):
    resp = auth_client.post("/api/subscriptions/", {
        "plan_id": plan.id,
        "start_date": "2026-09-15",
    })
    assert resp.status_code == 400


@pytest.mark.django_db
def test_my_subscription(auth_client, active_subscription):
    resp = auth_client.get("/api/subscriptions/mine/")
    assert resp.status_code == 200
    assert resp.data["id"] == active_subscription.id


@pytest.mark.django_db
def test_transfer_staff_only(regular_user, staff_user, active_subscription, regular_user2):
    cust2 = regular_user2.customer_profile
    client_regular = APIClient()
    client_regular.force_authenticate(user=regular_user)
    resp = client_regular.post(f"/api/subscriptions/{active_subscription.id}/transfer/", {
        "new_customer_id": cust2.id,
        "transfer_date": "2026-09-15",
    })
    assert resp.status_code == 403

    client_staff = APIClient()
    client_staff.force_authenticate(user=staff_user)
    resp2 = client_staff.post(f"/api/subscriptions/{active_subscription.id}/transfer/", {
        "new_customer_id": cust2.id,
        "transfer_date": "2026-09-15",
    }, format="json")
    assert resp2.status_code == 200
    assert AuditLog.objects.filter(event_type=AuditLog.EventType.TRANSFERRED).exists()


# ─── Pauses ───────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_create_pause(auth_client, active_subscription):
    resp = auth_client.post("/api/pauses/", {
        "start_date": "2026-09-10",
        "end_date": "2026-09-15",
    })
    assert resp.status_code == 201
    active_subscription.refresh_from_db()
    assert active_subscription.status == Subscription.Status.PAUSED


@pytest.mark.django_db
def test_create_pause_invalid_dates(auth_client, active_subscription):
    resp = auth_client.post("/api/pauses/", {
        "start_date": "2026-09-20",
        "end_date": "2026-09-10",
    })
    assert resp.status_code == 400


@pytest.mark.django_db
def test_resume_pause(auth_client, active_subscription):
    # First create a pause (send as JSON to avoid multipart None encoding issue)
    auth_client.post("/api/pauses/", {"start_date": "2026-09-10"}, format="json")
    from subscriptions.models import PausePeriod
    pause = PausePeriod.objects.filter(subscription=active_subscription).first()

    resp = auth_client.patch(f"/api/pauses/{pause.id}/resume/", {"resume_date": "2026-09-14"}, format="json")
    assert resp.status_code == 200
    active_subscription.refresh_from_db()
    assert active_subscription.status == Subscription.Status.ACTIVE


@pytest.mark.django_db
def test_list_pauses(auth_client, active_subscription):
    auth_client.post("/api/pauses/", {"start_date": "2026-09-10", "end_date": "2026-09-12"})
    resp = auth_client.get("/api/pauses/")
    assert resp.status_code == 200
    assert len(resp.data) == 1


# ─── Billing ─────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_view_own_bills(auth_client, active_subscription):
    # Generate a bill via service
    from services.billing_engine import generate_bill
    generate_bill(active_subscription, date(2026, 9, 1))
    resp = auth_client.get("/api/billing/")
    assert resp.status_code == 200
    assert len(resp.data) == 1


@pytest.mark.django_db
def test_generate_bill_staff_only(regular_user, staff_user, active_subscription):
    client_regular = APIClient()
    client_regular.force_authenticate(user=regular_user)
    resp = client_regular.post("/api/billing/generate/", {
        "subscription_id": active_subscription.id,
        "billing_month": "2026-09-01",
    })
    assert resp.status_code == 403

    client_staff = APIClient()
    client_staff.force_authenticate(user=staff_user)
    resp2 = client_staff.post("/api/billing/generate/", {
        "subscription_id": active_subscription.id,
        "billing_month": "2026-09-01",
    })
    assert resp2.status_code == 200
    assert BillingRecord.objects.count() == 1


# ─── Clock & Outbox ───────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_get_clock(auth_client, system_clock):
    resp = auth_client.get("/api/clock/")
    assert resp.status_code == 200
    # system_clock fixture clears + creates fresh record; pull from DB to confirm match
    clock_in_db = SystemClock.objects.first()
    assert resp.data["current_date"] == str(clock_in_db.current_date)


@pytest.mark.django_db
def test_advance_clock_staff_only(regular_user, staff_user, system_clock, active_subscription):
    client_regular = APIClient()
    client_regular.force_authenticate(user=regular_user)
    resp = client_regular.post("/api/clock/")
    assert resp.status_code == 403

    # Sep 1, 2026 is a Tuesday -> should dispatch notifications for active_subscription
    client_staff = APIClient()
    client_staff.force_authenticate(user=staff_user)
    resp2 = client_staff.post("/api/clock/")
    assert resp2.status_code == 200
    system_clock.refresh_from_db()
    assert system_clock.current_date == date(2026, 9, 2)  # advanced by 1 day


@pytest.mark.django_db
def test_advance_clock_dispatches_notifications(staff_client, system_clock, active_subscription):
    # Clock starts on Sep 1, advance to Sep 2 (Wednesday)
    staff_client.post("/api/clock/")  # moves to Sep 2 (Wed) -> weekday -> dispatch
    assert OutboxEntry.objects.count() >= 1


@pytest.mark.django_db
def test_outbox_list_staff_only(regular_user, staff_user, system_clock, active_subscription):
    client_regular = APIClient()
    client_regular.force_authenticate(user=regular_user)
    resp = client_regular.get("/api/outbox/")
    assert resp.status_code == 403

    client_staff = APIClient()
    client_staff.force_authenticate(user=staff_user)
    resp2 = client_staff.get("/api/outbox/")
    assert resp2.status_code == 200


# ─── Import (T4) ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_import_customers_staff_only(regular_user, staff_user, plan):
    rows = [{"name": "Import 1", "phone": "8111111111", "start_date": "2026-09-01", "plan_id": plan.id}]
    client_regular = APIClient()
    client_regular.force_authenticate(user=regular_user)
    resp = client_regular.post("/api/import/customers/", rows, format="json")
    assert resp.status_code == 403

    client_staff = APIClient()
    client_staff.force_authenticate(user=staff_user)
    resp2 = client_staff.post("/api/import/customers/", rows, format="json")
    assert resp2.status_code == 207
    assert resp2.data["imported"] == 1
    assert resp2.data["deduped"] == 0


@pytest.mark.django_db
def test_import_customers_partial_success(staff_client, plan):
    rows = [
        {"name": "Good", "phone": "8222222222", "start_date": "2026-09-01", "plan_id": plan.id},
        {"name": "", "phone": "", "start_date": "bad_date"},  # bad row
    ]
    resp = staff_client.post("/api/import/customers/", rows, format="json")
    assert resp.status_code == 207
    assert resp.data["imported"] == 1
    assert len(resp.data["rejected"]) == 1


@pytest.mark.django_db
def test_import_non_array_rejected(staff_client, plan):
    resp = staff_client.post("/api/import/customers/", {"name": "not a list"}, format="json")
    assert resp.status_code == 400


# ─── Audit ────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_audit_log_staff_only(regular_user, staff_user, active_subscription):
    client_regular = APIClient()
    client_regular.force_authenticate(user=regular_user)
    resp = client_regular.get("/api/audit/")
    assert resp.status_code == 403

    client_staff = APIClient()
    client_staff.force_authenticate(user=staff_user)
    resp2 = client_staff.get("/api/audit/")
    assert resp2.status_code == 200
