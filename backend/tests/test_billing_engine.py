from datetime import date
from decimal import Decimal
import pytest
from audit.models import AuditLog
from billing.models import BillingRecord
from customers.models import Customer
from django.contrib.auth.models import User
from plans.models import Plan
from services.billing_engine import generate_bill
from services.pause_service import create_pause
from services.weekday_calculator import get_weekdays_in_month
from subscriptions.models import Subscription, SubscriptionOwnershipPeriod


@pytest.fixture
def billing_setup(db):
    user1 = User.objects.create_user(username="cust1", password="pw")
    user2 = User.objects.create_user(username="cust2", password="pw")
    cust1 = Customer.objects.create(user=user1, name="Customer 1", phone="1111111111")
    cust2 = Customer.objects.create(user=user2, name="Customer 2", phone="2222222222")
    # Sep 2026 has 22 weekdays.
    # Plan monthly price: 2200.00 -> daily rate = 100.00
    plan = Plan.objects.create(name="Office Plan", monthly_price="2200.00", effective_from=date(2026, 1, 1))
    return {"cust1": cust1, "cust2": cust2, "plan": plan}


@pytest.mark.django_db
def test_single_owner_full_month(billing_setup):
    cust = billing_setup["cust1"]
    plan = billing_setup["plan"]
    sub = Subscription.objects.create(plan=plan, start_date=date(2026, 8, 1), status=Subscription.Status.ACTIVE)
    SubscriptionOwnershipPeriod.objects.create(subscription=sub, customer=cust, from_date=date(2026, 8, 1), to_date=None)

    bills = generate_bill(sub, date(2026, 9, 1))
    assert len(bills) == 1
    bill = bills[0]

    assert bill.customer == cust
    assert bill.billing_month == date(2026, 9, 1)
    assert bill.total_weekdays_in_segment == 22
    assert bill.paused_weekdays == 0
    assert bill.delivered_weekdays == 22
    assert bill.daily_rate == Decimal("100.00")
    assert bill.amount_due == Decimal("2200.00")


@pytest.mark.django_db
def test_mid_month_transfer_split_across_two_customers(billing_setup):
    # Sep 2026:
    # Cust 1 owns from Sep 1 to Sep 11 (Mon-Fri: Sep 1..4 is 4 days; Sep 7..11 is 5 days -> 9 weekdays)
    # Cust 2 owns from Sep 12 onwards (weekdays in Sep 12..30 -> 13 weekdays)
    cust1 = billing_setup["cust1"]
    cust2 = billing_setup["cust2"]
    plan = billing_setup["plan"]
    sub = Subscription.objects.create(plan=plan, start_date=date(2026, 9, 1), status=Subscription.Status.ACTIVE)
    SubscriptionOwnershipPeriod.objects.create(subscription=sub, customer=cust1, from_date=date(2026, 9, 1), to_date=date(2026, 9, 11))
    SubscriptionOwnershipPeriod.objects.create(subscription=sub, customer=cust2, from_date=date(2026, 9, 12), to_date=None)

    bills = generate_bill(sub, date(2026, 9, 1))
    assert len(bills) == 2

    bill1 = next(b for b in bills if b.customer == cust1)
    assert bill1.delivered_weekdays == 9
    assert bill1.amount_due == Decimal("900.00")

    bill2 = next(b for b in bills if b.customer == cust2)
    assert bill2.delivered_weekdays == 13
    assert bill2.amount_due == Decimal("1300.00")

    # Sum of amount due equals total monthly price
    assert bill1.amount_due + bill2.amount_due == Decimal("2200.00")


@pytest.mark.django_db
def test_mid_month_subscription_start(billing_setup):
    # Sub starts on Monday Sep 14, 2026.
    # Weekdays from Sep 14 to Sep 30 = 13 weekdays.
    cust = billing_setup["cust1"]
    plan = billing_setup["plan"]
    sub = Subscription.objects.create(plan=plan, start_date=date(2026, 9, 14), status=Subscription.Status.ACTIVE)
    SubscriptionOwnershipPeriod.objects.create(subscription=sub, customer=cust, from_date=date(2026, 9, 1), to_date=None)

    bills = generate_bill(sub, date(2026, 9, 1))
    assert len(bills) == 1
    bill = bills[0]

    assert bill.delivered_weekdays == 13
    assert bill.total_weekdays_in_segment == 13
    assert bill.amount_due == Decimal("1300.00")


@pytest.mark.django_db
def test_mid_month_cancellation(billing_setup):
    # Sub cancelled on Sep 18, 2026 (end_date = 2026-09-18).
    # Sep 1..18 has 14 weekdays.
    cust = billing_setup["cust1"]
    plan = billing_setup["plan"]
    sub = Subscription.objects.create(
        plan=plan,
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 18),
        status=Subscription.Status.CANCELLED,
    )
    SubscriptionOwnershipPeriod.objects.create(subscription=sub, customer=cust, from_date=date(2026, 9, 1), to_date=None)

    bills = generate_bill(sub, date(2026, 9, 1))
    assert len(bills) == 1
    bill = bills[0]

    assert bill.delivered_weekdays == 14
    assert bill.amount_due == Decimal("1400.00")


@pytest.mark.django_db
def test_pause_inside_billing_month(billing_setup):
    # Pause from Wed Sep 9 to Fri Sep 11 (3 weekdays)
    cust = billing_setup["cust1"]
    plan = billing_setup["plan"]
    sub = Subscription.objects.create(plan=plan, start_date=date(2026, 9, 1), status=Subscription.Status.ACTIVE)
    SubscriptionOwnershipPeriod.objects.create(subscription=sub, customer=cust, from_date=date(2026, 9, 1), to_date=None)
    create_pause(sub, start_date=date(2026, 9, 9), end_date=date(2026, 9, 11))

    bills = generate_bill(sub, date(2026, 9, 1))
    assert len(bills) == 1
    bill = bills[0]

    assert bill.total_weekdays_in_segment == 22
    assert bill.paused_weekdays == 3
    assert bill.delivered_weekdays == 19
    assert bill.amount_due == Decimal("1900.00")


@pytest.mark.django_db
def test_rerunning_billing_is_idempotent(billing_setup):
    cust = billing_setup["cust1"]
    plan = billing_setup["plan"]
    sub = Subscription.objects.create(plan=plan, start_date=date(2026, 9, 1), status=Subscription.Status.ACTIVE)
    SubscriptionOwnershipPeriod.objects.create(subscription=sub, customer=cust, from_date=date(2026, 9, 1), to_date=None)

    bills_first = generate_bill(sub, date(2026, 9, 1))
    assert len(bills_first) == 1
    record_id = bills_first[0].id

    # Run again for the same month
    bills_second = generate_bill(sub, date(2026, 9, 1))
    assert len(bills_second) == 1
    assert bills_second[0].id == record_id
    assert BillingRecord.objects.filter(subscription=sub, billing_month=date(2026, 9, 1)).count() == 1
