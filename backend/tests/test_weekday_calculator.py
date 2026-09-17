from datetime import date
from types import SimpleNamespace
import pytest
from services.weekday_calculator import (
    get_weekdays_in_month,
    get_weekdays_in_range,
    get_paused_weekdays,
    get_billable_weekdays,
    get_delivered_weekdays,
)


def test_get_weekdays_in_month():
    # September 2026: starts on Tuesday Sep 1, ends on Wednesday Sep 30.
    # Total days: 30. Saturdays: Sep 5, 12, 19, 26 (4). Sundays: Sep 6, 13, 20, 27 (4).
    # Billable weekdays: 30 - 8 = 22 weekdays.
    weekdays = get_weekdays_in_month(2026, 9)
    assert len(weekdays) == 22
    assert weekdays[0] == date(2026, 9, 1)
    assert weekdays[-1] == date(2026, 9, 30)
    for d in weekdays:
        assert d.weekday() < 5


def test_get_weekdays_in_range():
    # Mon Sep 7, 2026 to Sun Sep 13, 2026
    start = date(2026, 9, 7)
    end = date(2026, 9, 13)
    weekdays = get_weekdays_in_range(start, end)
    assert len(weekdays) == 5
    assert weekdays == [
        date(2026, 9, 7),
        date(2026, 9, 8),
        date(2026, 9, 9),
        date(2026, 9, 10),
        date(2026, 9, 11),
    ]

    # Inverted range returns empty list
    assert get_weekdays_in_range(end, start) == []


def test_full_month_no_pauses():
    # Full month of Sep 2026, subscription started earlier, no pauses
    start = date(2026, 9, 1)
    end = date(2026, 9, 30)
    sub_start = date(2026, 8, 1)
    
    billable = get_billable_weekdays(
        start_date=start,
        end_date=end,
        subscription_start_date=sub_start,
        pause_periods=[],
    )
    assert len(billable) == 22

    # Delivered count via mock subscription object
    sub = SimpleNamespace(start_date=sub_start, end_date=None, pause_periods=[])
    assert get_delivered_weekdays(sub, start, end) == 22


def test_mid_month_pause():
    # Sep 2026: pause from Wed Sep 9 to Fri Sep 11 (3 weekdays)
    start = date(2026, 9, 1)
    end = date(2026, 9, 30)
    sub_start = date(2026, 9, 1)
    pause = SimpleNamespace(start_date=date(2026, 9, 9), end_date=date(2026, 9, 11))

    billable = get_billable_weekdays(
        start_date=start,
        end_date=end,
        subscription_start_date=sub_start,
        pause_periods=[pause],
    )
    assert len(billable) == 22 - 3  # 19 days

    paused = get_paused_weekdays([pause], start, end)
    assert len(paused) == 3
    assert paused == [date(2026, 9, 9), date(2026, 9, 10), date(2026, 9, 11)]

    sub = SimpleNamespace(start_date=sub_start, end_date=None, pause_periods=[pause])
    assert get_delivered_weekdays(sub, start, end) == 19


def test_open_ended_pause():
    # Pause starts on Mon Sep 21, 2026, end_date is None (open-ended)
    # Remaining weekdays in Sep:
    # Sep 21 (Mon), Sep 22 (Tue), Sep 23 (Wed), Sep 24 (Thu), Sep 25 (Fri) -> 5 days
    # Sep 28 (Mon), Sep 29 (Tue), Sep 30 (Wed) -> 3 days
    # Total paused weekdays = 8 days
    start = date(2026, 9, 1)
    end = date(2026, 9, 30)
    sub_start = date(2026, 9, 1)
    pause = SimpleNamespace(start_date=date(2026, 9, 21), end_date=None)

    billable = get_billable_weekdays(
        start_date=start,
        end_date=end,
        subscription_start_date=sub_start,
        pause_periods=[pause],
    )
    assert len(billable) == 22 - 8  # 14 days

    paused = get_paused_weekdays([pause], start, end)
    assert len(paused) == 8

    sub = SimpleNamespace(start_date=sub_start, end_date=None, pause_periods=[pause])
    assert get_delivered_weekdays(sub, start, end) == 14


def test_subscription_starting_mid_month():
    # Subscription starts on Mon Sep 14, 2026. Month is Sep 1 to Sep 30.
    # Total weekdays in month = 22.
    # Weekdays before Sep 14:
    # Sep 1..4 (Tue..Fri = 4 days)
    # Sep 7..11 (Mon..Fri = 5 days)
    # Total before start = 9 days.
    # Active weekdays = 22 - 9 = 13 days.
    start = date(2026, 9, 1)
    end = date(2026, 9, 30)
    sub_start = date(2026, 9, 14)

    billable = get_billable_weekdays(
        start_date=start,
        end_date=end,
        subscription_start_date=sub_start,
        pause_periods=[],
    )
    assert len(billable) == 13
    assert billable[0] == date(2026, 9, 14)

    sub = SimpleNamespace(start_date=sub_start, end_date=None, pause_periods=[])
    assert get_delivered_weekdays(sub, start, end) == 13


def test_pause_spanning_only_weekend():
    # Sep 12, 2026 (Sat) to Sep 13, 2026 (Sun)
    start = date(2026, 9, 1)
    end = date(2026, 9, 30)
    sub_start = date(2026, 9, 1)
    weekend_pause = SimpleNamespace(start_date=date(2026, 9, 12), end_date=date(2026, 9, 13))

    paused = get_paused_weekdays([weekend_pause], start, end)
    assert len(paused) == 0

    billable = get_billable_weekdays(
        start_date=start,
        end_date=end,
        subscription_start_date=sub_start,
        pause_periods=[weekend_pause],
    )
    # No effect on billable weekdays
    assert len(billable) == 22

    sub = SimpleNamespace(start_date=sub_start, end_date=None, pause_periods=[weekend_pause])
    assert get_delivered_weekdays(sub, start, end) == 22


def test_subscription_cancelled_mid_month():
    # Subscription cancelled/ended on Friday Sep 18, 2026
    start = date(2026, 9, 1)
    end = date(2026, 9, 30)
    sub_start = date(2026, 9, 1)
    sub_end = date(2026, 9, 18)

    billable = get_billable_weekdays(
        start_date=start,
        end_date=end,
        subscription_start_date=sub_start,
        subscription_end_date=sub_end,
    )
    # Days from Sep 1 to Sep 18:
    # Sep 1..4 (4) + Sep 7..11 (5) + Sep 14..18 (5) = 14 weekdays
    assert len(billable) == 14
    assert billable[-1] == date(2026, 9, 18)

    sub = SimpleNamespace(start_date=sub_start, end_date=sub_end, pause_periods=[])
    assert get_delivered_weekdays(sub, start, end) == 14
