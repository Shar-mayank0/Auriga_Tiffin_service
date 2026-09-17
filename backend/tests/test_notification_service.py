from datetime import date
import pytest
from audit.models import AuditLog
from customers.models import Customer
from django.contrib.auth.models import User
from notifications.models import OutboxEntry
from plans.models import Plan
from services.notification_service import dispatch, get_eligible_customers
from services.pause_service import create_pause
from subscriptions.models import Subscription, SubscriptionOwnershipPeriod


@pytest.fixture
def notification_setup(db):
    u1 = User.objects.create_user(username="u1", password="pw")
    u2 = User.objects.create_user(username="u2", password="pw")
    cust1 = Customer.objects.create(user=u1, name="Alice", phone="1111111111")
    cust2 = Customer.objects.create(user=u2, name="Bob", phone="2222222222")

    plan = Plan.objects.create(name="Daily", monthly_price="1500.00", effective_from=date(2026, 1, 1))

    sub1 = Subscription.objects.create(plan=plan, start_date=date(2026, 9, 1), status=Subscription.Status.ACTIVE)
    SubscriptionOwnershipPeriod.objects.create(subscription=sub1, customer=cust1, from_date=date(2026, 9, 1), to_date=None)

    sub2 = Subscription.objects.create(plan=plan, start_date=date(2026, 9, 1), status=Subscription.Status.ACTIVE)
    SubscriptionOwnershipPeriod.objects.create(subscription=sub2, customer=cust2, from_date=date(2026, 9, 1), to_date=None)

    return {"cust1": cust1, "cust2": cust2, "sub1": sub1, "sub2": sub2}


@pytest.mark.django_db
def test_eligible_customer_gets_entry(notification_setup):
    target = date(2026, 9, 15)  # Tuesday
    entries = dispatch(target)
    assert len(entries) == 2

    phones = {e.customer.phone for e in entries}
    assert "1111111111" in phones
    assert "2222222222" in phones

    for entry in entries:
        assert entry.delivery_date == target
        assert "tiffin" in entry.message.lower()

    # Check AuditLog
    assert AuditLog.objects.filter(event_type=AuditLog.EventType.NOTIFIED).count() == 2


@pytest.mark.django_db
def test_paused_customer_excluded(notification_setup):
    sub2 = notification_setup["sub2"]
    create_pause(sub2, start_date=date(2026, 9, 14), end_date=date(2026, 9, 16))

    target = date(2026, 9, 15)  # Tuesday, sub2 is paused
    eligible = list(get_eligible_customers(target))
    assert len(eligible) == 1
    assert eligible[0] == notification_setup["cust1"]

    entries = dispatch(target)
    assert len(entries) == 1
    assert entries[0].customer == notification_setup["cust1"]


@pytest.mark.django_db
def test_weekend_produces_no_entries(notification_setup):
    weekend_target = date(2026, 9, 13)  # Sunday
    eligible = list(get_eligible_customers(weekend_target))
    assert len(eligible) == 0

    entries = dispatch(weekend_target)
    assert len(entries) == 0
    assert OutboxEntry.objects.count() == 0


@pytest.mark.django_db
def test_double_dispatch_same_date_does_not_duplicate(notification_setup):
    target = date(2026, 9, 15)
    first_run = dispatch(target)
    assert len(first_run) == 2
    assert OutboxEntry.objects.count() == 2

    # Second dispatch on the same date should be idempotent
    second_run = dispatch(target)
    assert len(second_run) == 0
    assert OutboxEntry.objects.count() == 2
