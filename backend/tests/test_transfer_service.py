from datetime import date, timedelta
import pytest
from audit.models import AuditLog
from customers.models import Customer
from django.contrib.auth.models import User
from plans.models import Plan
from services.transfer_service import get_owner_on_date, transfer
from subscriptions.models import Subscription, SubscriptionOwnershipPeriod


@pytest.fixture
def transfer_setup(db):
    u1 = User.objects.create_user(username="u1", password="pw")
    u2 = User.objects.create_user(username="u2", password="pw")
    u3 = User.objects.create_user(username="u3", password="pw")
    cust1 = Customer.objects.create(user=u1, name="Cust 1", phone="1111111111")
    cust2 = Customer.objects.create(user=u2, name="Cust 2", phone="2222222222")
    cust3 = Customer.objects.create(user=u3, name="Cust 3", phone="3333333333")

    plan = Plan.objects.create(name="Standard", monthly_price="1000.00", effective_from=date(2026, 1, 1))
    sub = Subscription.objects.create(plan=plan, start_date=date(2026, 9, 1), status=Subscription.Status.ACTIVE)
    op1 = SubscriptionOwnershipPeriod.objects.create(
        subscription=sub, customer=cust1, from_date=date(2026, 9, 1), to_date=None
    )

    return {"cust1": cust1, "cust2": cust2, "cust3": cust3, "sub": sub, "op1": op1, "plan": plan}


@pytest.mark.django_db
def test_successful_transfer_splits_ownership_correctly(transfer_setup):
    sub = transfer_setup["sub"]
    cust1 = transfer_setup["cust1"]
    cust2 = transfer_setup["cust2"]
    transfer_d = date(2026, 9, 15)

    new_op = transfer(sub, cust2, transfer_d)

    assert new_op.customer == cust2
    assert new_op.from_date == transfer_d
    assert new_op.to_date is None

    # Check original ownership period closed
    old_op = SubscriptionOwnershipPeriod.objects.get(id=transfer_setup["op1"].id)
    assert old_op.to_date == transfer_d - timedelta(days=1)

    # Check audit log
    audit = AuditLog.objects.filter(entity_type="Subscription", entity_id=sub.id, event_type=AuditLog.EventType.TRANSFERRED).first()
    assert audit is not None


@pytest.mark.django_db
def test_transfer_to_customer_with_conflicting_active_sub_is_rejected(transfer_setup):
    sub = transfer_setup["sub"]
    cust2 = transfer_setup["cust2"]
    plan = transfer_setup["plan"]

    # Cust2 already has an active subscription
    sub2 = Subscription.objects.create(plan=plan, start_date=date(2026, 9, 1), status=Subscription.Status.ACTIVE)
    SubscriptionOwnershipPeriod.objects.create(subscription=sub2, customer=cust2, from_date=date(2026, 9, 1), to_date=None)

    with pytest.raises(ValueError, match="already has an active subscription"):
        transfer(sub, cust2, date(2026, 9, 15))


@pytest.mark.django_db
def test_get_owner_on_date_correct_before_after_transfer(transfer_setup):
    sub = transfer_setup["sub"]
    cust1 = transfer_setup["cust1"]
    cust2 = transfer_setup["cust2"]
    transfer_d = date(2026, 9, 15)

    transfer(sub, cust2, transfer_d)

    # Day before transfer -> Cust 1
    assert get_owner_on_date(sub, date(2026, 9, 14)) == cust1
    # Day of transfer -> Cust 2
    assert get_owner_on_date(sub, date(2026, 9, 15)) == cust2
    # Day after transfer -> Cust 2
    assert get_owner_on_date(sub, date(2026, 9, 20)) == cust2


@pytest.mark.django_db
def test_atomicity_failure_rolls_back_both_period_changes(transfer_setup, monkeypatch):
    sub = transfer_setup["sub"]
    cust2 = transfer_setup["cust2"]
    op1_id = transfer_setup["op1"].id

    # Simulate an error during AuditLog creation inside the transaction
    def faulty_create(*args, **kwargs):
        raise RuntimeError("Database error during audit logging")

    monkeypatch.setattr(AuditLog.objects, "create", faulty_create)

    with pytest.raises(RuntimeError):
        transfer(sub, cust2, date(2026, 9, 15))

    # Verify rollback: old period to_date is still None
    old_op = SubscriptionOwnershipPeriod.objects.get(id=op1_id)
    assert old_op.to_date is None
    # No new ownership period was created for cust2
    assert not SubscriptionOwnershipPeriod.objects.filter(customer=cust2).exists()
