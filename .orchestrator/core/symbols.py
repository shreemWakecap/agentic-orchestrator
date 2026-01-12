"""Unicode symbols with ASCII fallback for Windows compatibility."""

import sys
import os


def _supports_unicode() -> bool:
    """Check if the current terminal supports Unicode."""
    # First, always check the actual stdout encoding - this is the most reliable
    try:
        encoding = getattr(sys.stdout, 'encoding', None) or ''
        stdout_is_utf8 = encoding.lower() in ('utf-8', 'utf8')
    except Exception:
        stdout_is_utf8 = False

    # On Windows, be very conservative - require actual UTF-8 encoding
    if sys.platform == 'win32':
        # If stdout is already UTF-8, we're good
        if stdout_is_utf8:
            return True

        # Check for explicit UTF-8 encoding in environment
        if os.environ.get("PYTHONIOENCODING", "").lower().startswith("utf"):
            return True

        # For all other cases on Windows, default to ASCII for safety
        # Even if we detect Windows Terminal, VSCode, etc., the actual
        # encoding might still be cp1252 which can't handle Unicode
        return False

    # Unix-like systems: check encoding
    if stdout_is_utf8:
        return True

    try:
        encoding = getattr(sys.stdout, 'encoding', None) or ''
        if encoding.lower().startswith('utf'):
            return True
    except Exception:
        pass

    # Default to True on Unix (most modern Unix systems support Unicode)
    return True


# Determine Unicode support once at import time
UNICODE_SUPPORTED = _supports_unicode()


class Symbols:
    """Terminal symbols with automatic ASCII fallback."""

    # Check mark
    CHECK = "✓" if UNICODE_SUPPORTED else "[OK]"

    # Cross mark
    CROSS = "✗" if UNICODE_SUPPORTED else "[X]"

    # Warning
    WARNING = "⚠" if UNICODE_SUPPORTED else "[!]"

    # Arrow right
    ARROW_RIGHT = "→" if UNICODE_SUPPORTED else "->"

    # Arrow left
    ARROW_LEFT = "←" if UNICODE_SUPPORTED else "<-"

    # Question mark (for uncertain status)
    QUESTION = "?" if UNICODE_SUPPORTED else "?"

    # Bullet point
    BULLET = "•" if UNICODE_SUPPORTED else "*"

    # Ellipsis
    ELLIPSIS = "…" if UNICODE_SUPPORTED else "..."


# Convenience exports
CHECK = Symbols.CHECK
CROSS = Symbols.CROSS
WARNING = Symbols.WARNING
ARROW_RIGHT = Symbols.ARROW_RIGHT
ARROW_LEFT = Symbols.ARROW_LEFT
QUESTION = Symbols.QUESTION
BULLET = Symbols.BULLET
ELLIPSIS = Symbols.ELLIPSIS
