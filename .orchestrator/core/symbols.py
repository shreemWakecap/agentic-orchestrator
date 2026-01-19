"""Unicode symbols with ASCII fallback for Windows compatibility."""

import sys
import os


def _supports_unicode() -> bool:
    """Check if the current terminal supports Unicode."""
    # On Windows, ALWAYS default to ASCII unless we're absolutely certain UTF-8 works
    # Rich library's LegacyWindowsTerm bypasses normal stdout encoding checks
    if sys.platform == 'win32':
        # Check if we're running with UTF-8 mode enabled
        if os.environ.get("PYTHONUTF8") == "1":
            return True
        if os.environ.get("PYTHONIOENCODING", "").lower().startswith("utf"):
            return True
        # Check console code page (65001 = UTF-8)
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            if kernel32.GetConsoleOutputCP() == 65001:
                return True
        except Exception:
            pass
        # Default to ASCII on Windows - safer
        return False

    # Unix-like systems: check encoding
    try:
        encoding = getattr(sys.stdout, 'encoding', None) or ''
        if encoding.lower() in ('utf-8', 'utf8') or encoding.lower().startswith('utf'):
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

    # Sparkles
    SPARKLES = "✨" if UNICODE_SUPPORTED else "*"


# Convenience exports
CHECK = Symbols.CHECK
CROSS = Symbols.CROSS
WARNING = Symbols.WARNING
ARROW_RIGHT = Symbols.ARROW_RIGHT
ARROW_LEFT = Symbols.ARROW_LEFT
QUESTION = Symbols.QUESTION
BULLET = Symbols.BULLET
ELLIPSIS = Symbols.ELLIPSIS
SPARKLES = Symbols.SPARKLES
