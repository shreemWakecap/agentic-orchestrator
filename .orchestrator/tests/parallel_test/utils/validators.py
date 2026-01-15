"""Validation utility functions for parallel test module."""

import re


def validate_email(email: str) -> bool:
    """
    Validate an email address format.

    Args:
        email: The email address string to validate.

    Returns:
        True if the email format is valid, False otherwise.
    """
    if not email or not isinstance(email, str):
        return False

    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_price(price) -> bool:
    """
    Validate a price value.

    Args:
        price: The price value to validate (int, float, or string).

    Returns:
        True if the price is valid (positive number), False otherwise.
    """
    if price is None:
        return False

    if isinstance(price, bool):
        return False

    if isinstance(price, (int, float)):
        return price >= 0

    if isinstance(price, str):
        try:
            value = float(price)
            return value >= 0
        except ValueError:
            return False

    return False
