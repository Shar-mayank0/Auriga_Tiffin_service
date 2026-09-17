from datetime import date
import pytest
from audit.models import AuditLog
from django.contrib.auth.models import User
from customers.models import Customer
from plans.models import Plan
from subscriptions.models import Subscription, PausePeriod
from services.pause_service import create_pause, resume_pause


@pytest.fixture
def sample_subscription(db):
    user = User.objects.create_user(username="rahul", email="rahul@example.com", password="password")
    plan = Plan.objects.create(name="Standard", monthly_price="120.00", effective_from=date(2026, 1, 1))
    customer = Customer.objects.create(user=user, name="Rahul Sharma", phone="9876543210", address="123 Main St")
    sub = Subscription.objects.create(plan=plan, start_date=date(2026, 9, 1), status=Subscription.Status.ACTIVE)
    return sub


@pytest.mark.django_db
def test_create_single_day_pause(sample_subscription):
    pause_date = date(2026, 9, 15)
    pause = create_pause(sample_subscription, start_date=pause_date, end_date=pause_date)
    
    assert pause.start_date == pause_date
    assert pause.end_date == pause_date
    sample_subscription.refresh_from_db()
    assert sample_subscription.status == Subscription.Status.PAUSED

    # Verify audit log
    audit = AuditLog.objects.filter(entity_type="Subscription", entity_id=sample_subscription.id).first()
    assert audit is not None
    assert audit.event_type == AuditLog.EventType.PAUSED


@pytest.mark.django_db
def test_create_range_pause(sample_subscription):
    start = date(2026, 9, 10)
    end = date(2026, 9, 20)
    pause = create_pause(sample_subscription, start_date=start, end_date=end)

    assert pause.start_date == start
    assert pause.end_date == end
    sample_subscription.refresh_from_db()
    assert sample_subscription.status == Subscription.Status.PAUSED


@pytest.mark.django_db
def test_create_open_ended_pause(sample_subscription):
    start = date(2026, 9, 15)
    pause = create_pause(sample_subscription, start_date=start, end_date=None)

    assert pause.start_date == start
    assert pause.end_date is None
    sample_subscription.refresh_from_db()
    assert sample_subscription.status == Subscription.Status.PAUSED


@pytest.mark.django_db
def test_create_pause_invalid_date_range(sample_subscription):
    with pytest.raises(ValueError, match="End date cannot be earlier than start date"):
        create_pause(sample_subscription, start_date=date(2026, 9, 20), end_date=date(2026, 9, 10))


@pytest.mark.django_db
def test_create_overlapping_pause_rejected(sample_subscription):
    create_pause(sample_subscription, start_date=date(2026, 9, 10), end_date=date(2026, 9, 15))

    # Overlaps inside
    with pytest.raises(ValueError, match="overlaps with an existing pause"):
        create_pause(sample_subscription, start_date=date(2026, 9, 12), end_date=date(2026, 9, 18))

    # Overlaps start
    with pytest.raises(ValueError, match="overlaps with an existing pause"):
        create_pause(sample_subscription, start_date=date(2026, 9, 8), end_date=date(2026, 9, 11))


@pytest.mark.django_db
def test_resume_pause_flow(sample_subscription):
    pause = create_pause(sample_subscription, start_date=date(2026, 9, 10), end_date=None)
    assert sample_subscription.status == Subscription.Status.PAUSED

    resume_d = date(2026, 9, 16)
    resumed = resume_pause(sample_subscription, resume_date=resume_d)

    assert resumed.id == pause.id
    assert resumed.end_date == resume_d
    assert resumed.resumed_at is not None

    sample_subscription.refresh_from_db()
    assert sample_subscription.status == Subscription.Status.ACTIVE

    # Verify audit log for resume
    audit = AuditLog.objects.filter(
        entity_type="Subscription",
        entity_id=sample_subscription.id,
        event_type=AuditLog.EventType.RESUMED,
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_resume_without_active_pause_rejected(sample_subscription):
    with pytest.raises(ValueError, match="No active pause period found"):
        resume_pause(sample_subscription, resume_date=date(2026, 9, 15))
