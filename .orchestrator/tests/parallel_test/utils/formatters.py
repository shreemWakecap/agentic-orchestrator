"""Utility functions for formatting values."""

from datetime import datetime


def format_currency(amount: float) -> str:
    """
    Format a numeric amount as a currency string.

    Args:
        amount: The numeric amount to format

    Returns:
        Formatted currency string (e.g., "$19.99")
    """
    return f"${amount:.2f}"


def format_date(date: datetime) -> str:
    """
    Format a datetime to ISO format string.

    Args:
        date: The datetime object to format

    Returns:
        ISO format date string (e.g., "2024-01-15T10:30:00")
    """
    return date.isoformat()
