import calendar
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, List, Optional
from django.db import transaction
from audit.models import AuditLog
from billing.models import BillingRecord
from services.weekday_calculator import (
    get_billable_weekdays,
    get_paused_weekdays,
    get_weekdays_in_month,
    get_weekdays_in_range,
)
from subscriptions.models import Subscription


def generate_bill(
    subscription: Subscription,
    billing_month_or_year: Any,
    month: Optional[int] = None,
    operator: Optional[Any] = None,
) -> List[BillingRecord]:
    """
    Generates deterministic, ownership-period-aware BillingRecord(s) for a subscription.
    
    Supports:
    - Multiple customers owning parts of the same subscription in one month (split billing).
    - Mid-month starts and cancellations (FR-8).
    - Excludes paused weekdays from amount due.
    - Idempotent and safe to re-run (upserts records without duplicates).
    """
    if isinstance(billing_month_or_year, int) and month is not None:
        year = billing_month_or_year
        m = month
    elif isinstance(billing_month_or_year, date):
        year = billing_month_or_year.year
        m = billing_month_or_year.month
    else:
        raise ValueError("Invalid billing month provided. Pass date or (year, month).")

    first_of_month = date(year, m, 1)
    _, num_days = calendar.monthrange(year, m)
    last_of_month = date(year, m, num_days)

    all_weekdays_in_month = get_weekdays_in_month(year, m)
    total_weekdays_in_month = len(all_weekdays_in_month)

    if total_weekdays_in_month == 0:
        return []

    plan_price = Decimal(str(subscription.plan.monthly_price))
    daily_rate = plan_price / Decimal(total_weekdays_in_month)
    daily_rate_rounded = daily_rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Fetch ownership periods overlapping the target month
    ownership_periods = subscription.ownership_periods.filter(
        from_date__lte=last_of_month
    ).order_by("from_date")

    billing_records: List[BillingRecord] = []
    pause_periods = list(subscription.pause_periods.all())

    with transaction.atomic():
        for op in ownership_periods:
            if op.to_date and op.to_date < first_of_month:
                continue

            seg_start = max(first_of_month, op.from_date)
            seg_end = min(last_of_month, op.to_date) if op.to_date else last_of_month

            # Respect subscription start and cancellation dates
            if subscription.start_date:
                seg_start = max(seg_start, subscription.start_date)
            if subscription.end_date:
                seg_end = min(seg_end, subscription.end_date)

            if seg_start > seg_end:
                continue

            total_weekdays_in_segment = len(get_weekdays_in_range(seg_start, seg_end))
            paused_weekdays = len(get_paused_weekdays(pause_periods, seg_start, seg_end))
            delivered_weekdays = len(
                get_billable_weekdays(
                    start_date=seg_start,
                    end_date=seg_end,
                    subscription_start_date=subscription.start_date,
                    subscription_end_date=subscription.end_date,
                    pause_periods=pause_periods,
                )
            )

            amount_due = (daily_rate * Decimal(delivered_weekdays)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

            record, _ = BillingRecord.objects.update_or_create(
                subscription=subscription,
                customer=op.customer,
                billing_month=first_of_month,
                defaults={
                    "ownership_from": seg_start,
                    "ownership_to": seg_end,
                    "total_weekdays_in_segment": total_weekdays_in_segment,
                    "paused_weekdays": paused_weekdays,
                    "delivered_weekdays": delivered_weekdays,
                    "daily_rate": daily_rate_rounded,
                    "amount_due": amount_due,
                },
            )
            billing_records.append(record)

            AuditLog.objects.create(
                event_type=AuditLog.EventType.BILLED,
                entity_type="Subscription",
                entity_id=subscription.id,
                operator=operator,
                notes=f"Generated bill #{record.id} for {op.customer} for {first_of_month:%Y-%m}: ₹{amount_due}",
            )

    return billing_records
