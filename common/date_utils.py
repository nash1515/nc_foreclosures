"""Date utility functions for scraper operations."""

from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from typing import List, Tuple


def generate_date_chunks(
    start_date: date,
    end_date: date,
    chunk_size: str
) -> List[Tuple[date, date]]:
    """
    Generate date ranges based on chunk size.

    Args:
        start_date: Start date
        end_date: End date
        chunk_size: 'daily', 'weekly', 'monthly', 'quarterly', 'yearly'

    Returns:
        List of (chunk_start, chunk_end) tuples

    Example:
        >>> generate_date_chunks(date(2024, 1, 1), date(2024, 3, 31), 'monthly')
        [(date(2024, 1, 1), date(2024, 1, 31)),
         (date(2024, 2, 1), date(2024, 2, 29)),
         (date(2024, 3, 1), date(2024, 3, 31))]
    """
    chunks = []
    current = start_date

    while current <= end_date:
        if chunk_size == 'daily':
            chunk_end = current
        elif chunk_size == 'weekly':
            chunk_end = current + timedelta(days=6)
        elif chunk_size == 'monthly':
            # End of current month
            next_month = current + relativedelta(months=1)
            chunk_end = next_month.replace(day=1) - timedelta(days=1)
        elif chunk_size == 'quarterly':
            # End of current quarter
            quarter_month = ((current.month - 1) // 3 + 1) * 3
            chunk_end = date(current.year, quarter_month, 1) + relativedelta(months=1) - timedelta(days=1)
        elif chunk_size == 'yearly':
            chunk_end = date(current.year, 12, 31)
        else:
            raise ValueError(f"Invalid chunk_size: {chunk_size}. Must be daily, weekly, monthly, quarterly, or yearly")

        # Don't exceed end_date
        chunk_end = min(chunk_end, end_date)

        chunks.append((current, chunk_end))

        # Move to next chunk
        if chunk_size == 'daily':
            current = current + timedelta(days=1)
        elif chunk_size == 'weekly':
            current = current + timedelta(days=7)
        elif chunk_size == 'monthly':
            current = current + relativedelta(months=1)
            current = current.replace(day=1)
        elif chunk_size == 'quarterly':
            current = current + relativedelta(months=3)
            current = date(current.year, ((current.month - 1) // 3) * 3 + 1, 1)
        elif chunk_size == 'yearly':
            current = date(current.year + 1, 1, 1)

    return chunks


def parse_date(date_str: str) -> date:
    """Parse YYYY-MM-DD string to date object."""
    from datetime import datetime
    return datetime.strptime(date_str, '%Y-%m-%d').date()
