from datetime import date
from typing import Any, List, Optional
from django.db import transaction
from django.db.models import Q
from audit.models import AuditLog
from customers.models import Customer
from notifications.models import OutboxEntry
from subscriptions.models import PausePeriod, Subscription, SubscriptionOwnershipPeriod


def get_eligible_customers(delivery_date: date):
    """
    Returns customers eligible for delivery on the given date:
    - Must be a weekday (Mon-Fri)
    - Has an active subscription spanning the date
    - Subscription is not currently paused on that date
    - Customer is the active owner of that subscription on that date
    """
    if delivery_date.weekday() >= 5:
        return Customer.objects.none()

    active_subs = (
        Subscription.objects.filter(start_date__lte=delivery_date)
        .filter(Q(end_date__isnull=True) | Q(end_date__gte=delivery_date))
        .exclude(status=Subscription.Status.CANCELLED)
    )

    paused_sub_ids = (
        PausePeriod.objects.filter(start_date__lte=delivery_date)
        .filter(Q(end_date__isnull=True) | Q(end_date__gte=delivery_date))
        .values_list("subscription_id", flat=True)
    )

    deliverable_subs = active_subs.exclude(id__in=paused_sub_ids)

    eligible_customer_ids = (
        SubscriptionOwnershipPeriod.objects.filter(
            subscription__in=deliverable_subs,
            from_date__lte=delivery_date,
        )
        .filter(Q(to_date__isnull=True) | Q(to_date__gte=delivery_date))
        .values_list("customer_id", flat=True)
        .distinct()
    )

    return Customer.objects.filter(id__in=eligible_customer_ids)


def dispatch(delivery_date: date, operator: Optional[Any] = None) -> List[OutboxEntry]:
    """
    Dispatches delivery notifications to OutboxEntry for all eligible customers.
    Idempotent: skips customers who already have an OutboxEntry for delivery_date.
    """
    if delivery_date.weekday() >= 5:
        return []

    eligible_customers = get_eligible_customers(delivery_date)
    dispatched_entries: List[OutboxEntry] = []

    with transaction.atomic():
        for customer in eligible_customers:
            if OutboxEntry.objects.filter(
                customer=customer, delivery_date=delivery_date
            ).exists():
                continue

            entry = OutboxEntry.objects.create(
                customer=customer,
                delivery_date=delivery_date,
                message=f"Hello {customer.name}, your tiffin delivery is scheduled for today ({delivery_date:%A, %B %d, %Y})!",
            )
            dispatched_entries.append(entry)

            AuditLog.objects.create(
                event_type=AuditLog.EventType.NOTIFIED,
                entity_type="Customer",
                entity_id=customer.id,
                operator=operator,
                notes=f"Dispatched delivery notification for {delivery_date}",
            )

    return dispatched_entries
