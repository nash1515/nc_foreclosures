"""Business day calculations for NC upset bid deadlines.

NC General Statute 45-21.27 specifies a 10-day upset bid period.
If the 10th day falls on a weekend or court holiday, the deadline
extends to the next business day.

NC Court Holidays (observed):
- New Year's Day (Jan 1)
- Martin Luther King Jr. Day (3rd Monday in January)
- Good Friday (Friday before Easter)
- Memorial Day (Last Monday in May)
- Independence Day (July 4)
- Labor Day (1st Monday in September)
- Veterans Day (Nov 11)
- Thanksgiving Day (4th Thursday in November)
- Day after Thanksgiving (4th Friday in November)
- Christmas Eve (Dec 24)
- Christmas Day (Dec 25)
- Day after Christmas (Dec 26)
"""

from datetime import date, timedelta
from typing import Optional
import calendar


def get_easter_date(year: int) -> date:
    """Calculate Easter Sunday using the Anonymous Gregorian algorithm."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def get_good_friday(year: int) -> date:
    """Get Good Friday (2 days before Easter Sunday)."""
    easter = get_easter_date(year)
    return easter - timedelta(days=2)


def get_nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date:
    """Get the nth occurrence of a weekday in a month.

    Args:
        year: Year
        month: Month (1-12)
        weekday: Day of week (0=Monday, 6=Sunday)
        n: Which occurrence (1=first, 2=second, etc., -1=last)
    """
    if n > 0:
        # Find first occurrence
        first_day = date(year, month, 1)
        days_until = (weekday - first_day.weekday()) % 7
        first_occurrence = first_day + timedelta(days=days_until)
        return first_occurrence + timedelta(weeks=n-1)
    else:
        # Find last occurrence
        last_day = date(year, month, calendar.monthrange(year, month)[1])
        days_since = (last_day.weekday() - weekday) % 7
        return last_day - timedelta(days=days_since)


def get_nc_court_holidays(year: int) -> set:
    """Get all NC court holidays for a given year."""
    holidays = set()

    # Fixed holidays
    holidays.add(date(year, 1, 1))    # New Year's Day
    holidays.add(date(year, 7, 4))    # Independence Day
    holidays.add(date(year, 11, 11))  # Veterans Day
    holidays.add(date(year, 12, 24))  # Christmas Eve
    holidays.add(date(year, 12, 25))  # Christmas Day
    holidays.add(date(year, 12, 26))  # Day after Christmas

    # Floating holidays
    holidays.add(get_nth_weekday_of_month(year, 1, 0, 3))   # MLK Day (3rd Monday Jan)
    holidays.add(get_good_friday(year))                      # Good Friday
    holidays.add(get_nth_weekday_of_month(year, 5, 0, -1))  # Memorial Day (last Monday May)
    holidays.add(get_nth_weekday_of_month(year, 9, 0, 1))   # Labor Day (1st Monday Sep)

    # Thanksgiving (4th Thursday) and day after
    thanksgiving = get_nth_weekday_of_month(year, 11, 3, 4)
    holidays.add(thanksgiving)
    holidays.add(thanksgiving + timedelta(days=1))

    # Handle holidays that fall on weekends (observed on nearest weekday)
    adjusted_holidays = set()
    for holiday in holidays:
        if holiday.weekday() == 5:  # Saturday -> Friday
            adjusted_holidays.add(holiday - timedelta(days=1))
        elif holiday.weekday() == 6:  # Sunday -> Monday
            adjusted_holidays.add(holiday + timedelta(days=1))
        else:
            adjusted_holidays.add(holiday)

    return adjusted_holidays


def is_business_day(d: date) -> bool:
    """Check if a date is a business day (not weekend or NC court holiday)."""
    # Weekend check
    if d.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False

    # Holiday check
    holidays = get_nc_court_holidays(d.year)
    if d in holidays:
        return False

    return True


def next_business_day(d: date) -> date:
    """Get the next business day on or after the given date."""
    while not is_business_day(d):
        d += timedelta(days=1)
    return d


def calculate_upset_bid_deadline(event_date: date) -> date:
    """Calculate the upset bid deadline from an event date.

    NC law: 10 calendar days from the event, extended to next business day
    if the 10th day falls on a weekend or court holiday.

    Args:
        event_date: Date of the upset bid event or sale report

    Returns:
        The deadline date (adjusted for weekends/holidays)
    """
    raw_deadline = event_date + timedelta(days=10)
    return next_business_day(raw_deadline)


def get_days_remaining(deadline: date, from_date: Optional[date] = None) -> int:
    """Get the number of days remaining until a deadline.

    Args:
        deadline: The deadline date
        from_date: The date to calculate from (defaults to today)

    Returns:
        Number of days remaining (negative if past deadline)
    """
    if from_date is None:
        from_date = date.today()
    return (deadline - from_date).days
