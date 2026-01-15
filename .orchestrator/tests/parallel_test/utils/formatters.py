"""Utility functions for formatting values."""

from datetime import datetime, date
from typing import Union


def format_currency(amount: Union[int, float], currency_symbol: str = "$", decimal_places: int = 2) -> str:
    """
    Format a numeric amount as a currency string.

    Args:
        amount: The numeric amount to format
        currency_symbol: The currency symbol to prepend (default: "$")
        decimal_places: Number of decimal places (default: 2)

    Returns:
        Formatted currency string (e.g., "$1,234.56")
    """
    if amount is None:
        return f"{currency_symbol}0.00"

    formatted = f"{abs(amount):,.{decimal_places}f}"

    if amount < 0:
        return f"-{currency_symbol}{formatted}"
    return f"{currency_symbol}{formatted}"


def format_date(date_value: Union[datetime, date, str], output_format: str = "%Y-%m-%d") -> str:
    """
    Format a date value to a string representation.

    Args:
        date_value: The date to format (datetime, date, or ISO format string)
        output_format: The strftime format string (default: "%Y-%m-%d")

    Returns:
        Formatted date string

    Raises:
        ValueError: If the date string cannot be parsed
    """
    if date_value is None:
        return ""

    if isinstance(date_value, str):
        # Try common ISO formats
        for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d"]:
            try:
                date_value = datetime.strptime(date_value, fmt)
                break
            except ValueError:
                continue
        else:
            raise ValueError(f"Unable to parse date string: {date_value}")

    return date_value.strftime(output_format)
