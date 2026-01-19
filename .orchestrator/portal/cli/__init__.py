"""
CLI package - Utilities for CLI command implementation.
"""
from .checkpointing import (
    CheckpointManager,
    BatchCheckpointer,
    load_checkpoint_state,
    get_resume_checkpoint_id,
)

from .output import (
    # Enums
    LogLevel,
    OutputFormat,
    # Configuration
    set_output_format,
    get_output_format,
    # Core event emitters
    emit_start,
    emit_progress,
    emit_log,
    emit_checkpoint,
    emit_error,
    emit_complete,
    emit_raw,
    # Convenience helpers
    info,
    warn,
    error,
    debug,
    # Classes
    ProgressTracker,
    ResumeContext,
    JobContext,
    # Context managers
    phase,
)

__all__ = [
    # From checkpointing
    "CheckpointManager",
    "BatchCheckpointer",
    "load_checkpoint_state",
    "get_resume_checkpoint_id",
    # From output - Enums
    "LogLevel",
    "OutputFormat",
    # From output - Configuration
    "set_output_format",
    "get_output_format",
    # From output - Core event emitters
    "emit_start",
    "emit_progress",
    "emit_log",
    "emit_checkpoint",
    "emit_error",
    "emit_complete",
    "emit_raw",
    # From output - Convenience helpers
    "info",
    "warn",
    "error",
    "debug",
    # From output - Classes
    "ProgressTracker",
    "ResumeContext",
    "JobContext",
    # From output - Context managers
    "phase",
]
