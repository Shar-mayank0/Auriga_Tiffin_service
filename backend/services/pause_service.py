from datetime import date
from typing import Any, Optional
from django.db import transaction
from django.utils import timezone
from audit.models import AuditLog
from subscriptions.models import PausePeriod, Subscription


def create_pause(
    subscription: Subscription,
    start_date: date,
    end_date: Optional[date] = None,
    operator: Optional[Any] = None,
) -> PausePeriod:
    """
    Creates a new pause period for a subscription.
    Can be a single day, date range, or open-ended (end_date=None).
    Rejects inverted date ranges and overlapping pauses.
    Updates subscription status to PAUSED and records an AuditLog entry.
    """
    if end_date is not None and end_date < start_date:
        raise ValueError("End date cannot be earlier than start date.")

    # Check for overlapping pause periods
    # An existing pause [p.start_date, p.end_date or date.max] overlaps [start_date, end_date or date.max]
    # when p.start_date <= (end_date or max) AND start_date <= (p.end_date or max)
    target_end = end_date if end_date is not None else date.max
    existing_pauses = subscription.pause_periods.filter(resumed_at__isnull=True)
    for p in existing_pauses:
        p_end = p.end_date if p.end_date is not None else date.max
        if p.start_date <= target_end and start_date <= p_end:
            raise ValueError("Pause period overlaps with an existing pause period.")

    with transaction.atomic():
        pause = PausePeriod.objects.create(
            subscription=subscription,
            start_date=start_date,
            end_date=end_date,
        )

        subscription.status = Subscription.Status.PAUSED
        subscription.save(update_fields=["status"])

        AuditLog.objects.create(
            event_type=AuditLog.EventType.PAUSED,
            entity_type="Subscription",
            entity_id=subscription.id,
            operator=operator,
            notes=f"Created pause period from {start_date} to {end_date or 'open-ended'}",
        )

    return pause


def resume_pause(
    subscription: Subscription,
    resume_date: Optional[date] = None,
    pause_id: Optional[int] = None,
    operator: Optional[Any] = None,
) -> PausePeriod:
    """
    Closes an active pause period, sets resumed_at, and restores subscription status to ACTIVE.
    Records an AuditLog entry.
    """
    with transaction.atomic():
        if pause_id:
            pause = subscription.pause_periods.filter(id=pause_id, resumed_at__isnull=True).first()
        else:
            pause = (
                subscription.pause_periods.filter(resumed_at__isnull=True)
                .order_by("-start_date")
                .first()
            )

        if not pause:
            raise ValueError("No active pause period found for this subscription.")

        if resume_date is not None:
            if resume_date < pause.start_date:
                raise ValueError("Resume date cannot be earlier than pause start date.")
            pause.end_date = resume_date
        elif pause.end_date is None:
            from notifications.models import SystemClock
            clock = SystemClock.objects.first()
            pause.end_date = clock.current_date if clock else date.today()

        pause.resumed_at = timezone.now()
        pause.save()

        # If no other active unresumed pauses exist, restore subscription status to ACTIVE
        still_paused = subscription.pause_periods.filter(resumed_at__isnull=True).exists()
        if not still_paused:
            subscription.status = Subscription.Status.ACTIVE
            subscription.save(update_fields=["status"])

        AuditLog.objects.create(
            event_type=AuditLog.EventType.RESUMED,
            entity_type="Subscription",
            entity_id=subscription.id,
            operator=operator,
            notes=f"Resumed pause #{pause.id} effective {pause.end_date}",
        )

    return pause
