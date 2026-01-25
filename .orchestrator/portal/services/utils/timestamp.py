"""Timestamp parsing and comparison utilities.

Provides unified timestamp handling, consolidating duplicate
implementations across multiple services.
"""
from datetime import datetime, timedelta
from typing import Optional, Union


def parse_iso_timestamp(
    timestamp_str: Optional[str],
    default: Optional[datetime] = None
) -> Optional[datetime]:
    """Parse an ISO format timestamp string.

    Handles multiple ISO 8601 formats:
    - 2025-01-24T12:30:45
    - 2025-01-24T12:30:45.123456
    - 2025-01-24T12:30:45Z
    - 2025-01-24T12:30:45+00:00

    Args:
        timestamp_str: ISO format timestamp string.
        default: Default value to return if parsing fails.

    Returns:
        Parsed datetime object or default value.
    """
    if not timestamp_str:
        return default

    try:
        # Handle Z suffix for UTC
        if timestamp_str.endswith('Z'):
            timestamp_str = timestamp_str[:-1] + '+00:00'

        # Try standard fromisoformat (handles most cases)
        return datetime.fromisoformat(timestamp_str)
    except (ValueError, TypeError):
        pass

    # Try common formats as fallback
    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(timestamp_str, fmt)
        except (ValueError, TypeError):
            continue

    return default


def is_timestamp_older_than(
    timestamp: Union[str, datetime, None],
    hours: int = 0,
    minutes: int = 0,
    seconds: int = 0,
    reference: Optional[datetime] = None
) -> bool:
    """Check if a timestamp is older than a specified duration.

    Args:
        timestamp: Timestamp to check (string or datetime).
        hours: Hours threshold.
        minutes: Minutes threshold.
        seconds: Seconds threshold.
        reference: Reference time (defaults to now).

    Returns:
        True if timestamp is older than the threshold, False otherwise.
        Returns True if timestamp is None or invalid (treat as stale).
    """
    if timestamp is None:
        return True

    # Parse string timestamp
    if isinstance(timestamp, str):
        timestamp = parse_iso_timestamp(timestamp)
        if timestamp is None:
            return True

    reference = reference or datetime.now()
    threshold = timedelta(hours=hours, minutes=minutes, seconds=seconds)

    return (reference - timestamp) > threshold


def format_duration(seconds: Union[int, float]) -> str:
    """Format a duration in seconds to a human-readable string.

    Args:
        seconds: Duration in seconds.

    Returns:
        Human-readable duration string (e.g., "2h 30m 15s").
    """
    if seconds < 0:
        return "0s"

    seconds = int(seconds)

    if seconds < 60:
        return f"{seconds}s"

    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {secs}s" if secs else f"{minutes}m"

    hours, mins = divmod(minutes, 60)
    if hours < 24:
        if secs:
            return f"{hours}h {mins}m {secs}s"
        elif mins:
            return f"{hours}h {mins}m"
        return f"{hours}h"

    days, hrs = divmod(hours, 24)
    if hrs:
        return f"{days}d {hrs}h"
    return f"{days}d"


def format_timestamp(
    dt: Optional[datetime],
    format_str: str = "%Y-%m-%d %H:%M:%S"
) -> str:
    """Format a datetime object to a string.

    Args:
        dt: Datetime object to format.
        format_str: Output format string.

    Returns:
        Formatted string or empty string if dt is None.
    """
    if dt is None:
        return ""
    return dt.strftime(format_str)
