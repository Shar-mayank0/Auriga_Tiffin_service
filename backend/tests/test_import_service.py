from datetime import date
import pytest
from audit.models import AuditLog
from customers.models import Customer
from plans.models import Plan
from services.import_service import deduplicate, normalize_date, run_import, validate_row
from subscriptions.models import Subscription, SubscriptionOwnershipPeriod


@pytest.fixture
def import_plan(db):
    return Plan.objects.create(name="Lunch Plan", monthly_price="1500.00", effective_from=date(2026, 1, 1))


def test_normalize_date():
    assert normalize_date("2026-09-15") == date(2026, 9, 15)
    assert normalize_date("15/09/2026") == date(2026, 9, 15)
    assert normalize_date("Sep 15 2026") == date(2026, 9, 15)
    assert normalize_date("15-Sep-26") == date(2026, 9, 15)
    assert normalize_date("15-Sep-2026") == date(2026, 9, 15)
    assert normalize_date("invalid-date") is None
    assert normalize_date("") is None
    assert normalize_date(None) is None


@pytest.mark.django_db
def test_validate_row(import_plan):
    valid_row = {"name": "Alice", "phone": "9999999999", "start_date": "2026-09-01", "plan_id": import_plan.id}
    is_valid, reasons = validate_row(valid_row)
    assert is_valid
    assert len(reasons) == 0

    invalid_row = {"name": "", "phone": "", "start_date": "bad_date", "plan_id": 999}
    is_valid, reasons = validate_row(invalid_row)
    assert not is_valid
    assert any("Name" in r for r in reasons)
    assert any("Phone" in r for r in reasons)
    assert any("start_date" in r for r in reasons)
    assert any("Plan" in r for r in reasons)


def test_deduplicate():
    rows = [
        {"name": "Alice", "phone": "1234567890"},
        {"name": "Alice Duplicate", "phone": "1234567890"},
        {"name": "Bob", "phone": "9876543210"},
        {"name": "Bob Duplicate", "phone": "9876543210"},
    ]
    unique_rows, deduped_rows = deduplicate(rows)
    assert len(unique_rows) == 2
    assert len(deduped_rows) == 2
    assert {r["name"] for r in unique_rows} == {"Alice", "Bob"}


@pytest.mark.django_db
def test_clean_rows_import_correctly(import_plan):
    data = [
        {"name": "Rohan", "phone": "9111111111", "address": "Flat 1", "start_date": "2026-09-01", "plan_id": import_plan.id},
        {"name": "Sita", "phone": "9222222222", "address": "Flat 2", "start_date": "15/09/2026", "plan_id": import_plan.id},
    ]
    result = run_import(data)
    assert result["imported"] == 2
    assert result["deduped"] == 0
    assert len(result["rejected"]) == 0

    assert Customer.objects.filter(phone="9111111111").exists()
    assert Customer.objects.filter(phone="9222222222").exists()

    # Subscriptions and ownership periods created
    cust = Customer.objects.get(phone="9111111111")
    op = SubscriptionOwnershipPeriod.objects.filter(customer=cust).first()
    assert op is not None
    assert op.subscription.plan == import_plan
    assert op.from_date == date(2026, 9, 1)

    # Audit log check
    assert AuditLog.objects.filter(event_type=AuditLog.EventType.IMPORTED).count() == 2


@pytest.mark.django_db
def test_duplicate_phones_deduped(import_plan):
    data = [
        {"name": "Rohan", "phone": "9111111111", "start_date": "2026-09-01", "plan_id": import_plan.id},
        {"name": "Rohan Copy", "phone": "9111111111", "start_date": "2026-09-01", "plan_id": import_plan.id},
    ]
    result = run_import(data)
    assert result["imported"] == 1
    assert result["deduped"] == 1
    assert len(result["rejected"]) == 0
    assert Customer.objects.filter(phone="9111111111").count() == 1


@pytest.mark.django_db
def test_one_bad_row_does_not_block_others(import_plan):
    data = [
        {"name": "Good Row 1", "phone": "9333333333", "start_date": "2026-09-01", "plan_id": import_plan.id},
        {"name": "", "phone": "invalid", "start_date": "not-a-date", "plan_id": 99999},  # Bad
        {"name": "Good Row 2", "phone": "9444444444", "start_date": "2026-09-05", "plan_id": import_plan.id},
    ]
    result = run_import(data)
    assert result["imported"] == 2
    assert result["deduped"] == 0
    assert len(result["rejected"]) == 1
    assert result["rejected"][0]["row"]["phone"] == "invalid"

    assert Customer.objects.filter(phone="9333333333").exists()
    assert Customer.objects.filter(phone="9444444444").exists()
