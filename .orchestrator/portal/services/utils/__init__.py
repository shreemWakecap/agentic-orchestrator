"""Shared service utilities.

This package contains shared utility functions and classes used across
multiple portal services to eliminate code duplication.

Modules:
    git_runner: Unified git command execution utilities.
    timestamp: Unified timestamp parsing and comparison utilities.
    thread_context: Thread-local project context management.
"""

from .git_runner import GitRunner, run_git_command
from .timestamp import parse_iso_timestamp, is_timestamp_older_than
from .thread_context import ThreadContextManager, run_with_project_context

__all__ = [
    "GitRunner",
    "run_git_command",
    "parse_iso_timestamp",
    "is_timestamp_older_than",
    "ThreadContextManager",
    "run_with_project_context",
]
