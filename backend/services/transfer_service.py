from datetime import date, timedelta
from typing import Any, Optional
from django.db import transaction
from django.db.models import Q
from audit.models import AuditLog
from customers.models import Customer
from subscriptions.models import Subscription, SubscriptionOwnershipPeriod


def transfer(
    subscription: Subscription,
    new_customer: Customer,
    transfer_date: date,
    operator: Optional[Any] = None,
) -> SubscriptionOwnershipPeriod:
    """
    Transfers subscription ownership to a new customer starting on transfer_date.
    
    Rules:
    - Rejects if subscription is cancelled.
    - Rejects if transfer_date is earlier than subscription start date.
    - Rejects if new_customer already has another conflicting active subscription on transfer_date.
    - Closes current ownership period (to_date = transfer_date - 1 day).
    - Opens new ownership period starting from transfer_date with to_date=None.
    - Atomic transaction + AuditLog entry.
    """
    if subscription.status == Subscription.Status.CANCELLED:
        raise ValueError("Cannot transfer a cancelled subscription.")

    if transfer_date < subscription.start_date:
        raise ValueError("Transfer date cannot be earlier than subscription start date.")

    # Check if new customer already has a conflicting active subscription on transfer_date
    conflicting_sub = (
        SubscriptionOwnershipPeriod.objects.filter(
            customer=new_customer,
            from_date__lte=transfer_date,
        )
        .filter(Q(to_date__isnull=True) | Q(to_date__gte=transfer_date))
        .exclude(subscription=subscription)
        .exclude(subscription__status=Subscription.Status.CANCELLED)
        .exists()
    )
    if conflicting_sub:
        raise ValueError(
            f"Customer {new_customer.name} already has an active subscription on {transfer_date}."
        )

    # Locate the active ownership period for this subscription
    current_period = (
        subscription.ownership_periods.filter(from_date__lte=transfer_date)
        .filter(Q(to_date__isnull=True) | Q(to_date__gte=transfer_date))
        .first()
    )

    if not current_period:
        current_period = subscription.ownership_periods.filter(to_date__isnull=True).first()

    if not current_period:
        raise ValueError("No active ownership period found for this subscription.")

    if current_period.customer == new_customer:
        raise ValueError("Cannot transfer subscription to the same customer.")

    if transfer_date <= current_period.from_date:
        raise ValueError("Transfer date must be strictly after current ownership start date.")

    with transaction.atomic():
        current_period.to_date = transfer_date - timedelta(days=1)
        current_period.save(update_fields=["to_date"])

        new_period = SubscriptionOwnershipPeriod.objects.create(
            subscription=subscription,
            customer=new_customer,
            from_date=transfer_date,
            to_date=None,
        )

        AuditLog.objects.create(
            event_type=AuditLog.EventType.TRANSFERRED,
            entity_type="Subscription",
            entity_id=subscription.id,
            operator=operator,
            notes=(
                f"Transferred subscription #{subscription.id} from {current_period.customer} "
                f"to {new_customer} on {transfer_date}"
            ),
        )

    return new_period


def get_owner_on_date(subscription: Subscription, target_date: date) -> Optional[Customer]:
    """
    Returns the customer who owns the subscription on the given date.
    """
    period = (
        subscription.ownership_periods.filter(from_date__lte=target_date)
        .filter(Q(to_date__isnull=True) | Q(to_date__gte=target_date))
        .order_by("-from_date")
        .first()
    )
    return period.customer if period else None
