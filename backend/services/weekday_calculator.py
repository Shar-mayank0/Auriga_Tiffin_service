import calendar
from datetime import date, timedelta
from typing import Any, Iterable, List, Optional


def get_weekdays_in_month(year: int, month: int) -> List[date]:
    """
    Returns all Monday-to-Friday dates within a specified year and month.
    """
    _, num_days = calendar.monthrange(year, month)
    return [
        date(year, month, day)
        for day in range(1, num_days + 1)
        if date(year, month, day).weekday() < 5
    ]


def get_weekdays_in_range(start_date: date, end_date: date) -> List[date]:
    """
    Returns all Monday-to-Friday dates in [start_date, end_date] inclusive.
    If start_date > end_date, returns an empty list.
    """
    if start_date > end_date:
        return []

    weekdays: List[date] = []
    curr = start_date
    one_day = timedelta(days=1)
    while curr <= end_date:
        if curr.weekday() < 5:
            weekdays.append(curr)
        curr += one_day
    return weekdays


def _is_date_paused(d: date, pause_periods: Iterable[Any]) -> bool:
    """
    Checks if a given date falls within any of the provided pause periods.
    Handles both objects with .start_date/.end_date and dicts.
    If end_date is None, the pause is considered open-ended from start_date onwards.
    """
    for period in pause_periods:
        if hasattr(period, "start_date"):
            p_start = period.start_date
            p_end = getattr(period, "end_date", None)
        elif isinstance(period, dict):
            p_start = period.get("start_date")
            p_end = period.get("end_date")
        else:
            continue

        if p_start and p_start <= d:
            if p_end is None or d <= p_end:
                return True
    return False


def _normalize_pause_periods(pause_periods: Optional[Iterable[Any]]) -> List[Any]:
    if pause_periods is None:
        return []
    if hasattr(pause_periods, "all") and callable(pause_periods.all):
        return list(pause_periods.all())
    return list(pause_periods)


def get_paused_weekdays(
    pause_periods: Optional[Iterable[Any]],
    start_date: date,
    end_date: date,
) -> List[date]:
    """
    Returns all weekdays between start_date and end_date (inclusive) that fall
    within one or more pause periods.
    """
    normalized_pauses = _normalize_pause_periods(pause_periods)
    weekdays = get_weekdays_in_range(start_date, end_date)
    return [d for d in weekdays if _is_date_paused(d, normalized_pauses)]


def get_billable_weekdays(
    start_date: date,
    end_date: date,
    subscription_start_date: Optional[date] = None,
    subscription_end_date: Optional[date] = None,
    pause_periods: Optional[Iterable[Any]] = None,
) -> List[date]:
    """
    Pure function that calculates deliverable / billable weekdays for a date range.
    
    Rules:
    - Monday through Friday only
    - Excludes dates strictly before subscription_start_date (if provided)
    - Excludes dates strictly after subscription_end_date (if provided)
    - Excludes dates falling within any active or open-ended pause period
    - Never uses system clock / datetime.today()
    """
    normalized_pauses = _normalize_pause_periods(pause_periods)
    weekdays = get_weekdays_in_range(start_date, end_date)

    billable: List[date] = []
    for d in weekdays:
        if subscription_start_date and d < subscription_start_date:
            continue
        if subscription_end_date and d > subscription_end_date:
            continue
        if _is_date_paused(d, normalized_pauses):
            continue
        billable.append(d)

    return billable


def get_delivered_weekdays(
    subscription: Any,
    start_date: date,
    end_date: date,
) -> int:
    """
    Calculates the count of billable/delivered weekdays for a subscription
    within [start_date, end_date].
    
    Accepts either a Subscription model instance or a mock object
    with start_date, end_date, and pause_periods.
    """
    sub_start = getattr(subscription, "start_date", None)
    sub_end = getattr(subscription, "end_date", None)
    pause_periods = getattr(subscription, "pause_periods", None)

    billable = get_billable_weekdays(
        start_date=start_date,
        end_date=end_date,
        subscription_start_date=sub_start,
        subscription_end_date=sub_end,
        pause_periods=pause_periods,
    )
    return len(billable)
