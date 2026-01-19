"""
Structured output helpers for CLI commands.

This module provides functions for emitting JSONL events that the portal
can parse and stream to users. All CLI commands should use these helpers
for consistent, parseable output.

Usage:
    from cli.output import set_output_format, emit_start, emit_complete, info

    set_output_format("jsonl")  # or "text" for human-readable
    emit_start("init")
    info("Processing items...")
    emit_complete(0)
"""
import json
import sys
import os
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Callable
from enum import Enum
from contextlib import contextmanager


class LogLevel(str, Enum):
    """Log level for log events."""
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class OutputFormat(str, Enum):
    """Output format modes."""
    JSONL = "jsonl"   # Structured JSON lines for portal
    TEXT = "text"     # Human-readable for development
    QUIET = "quiet"   # Minimal output


# Global output format (set by CLI argument parsing)
_output_format: OutputFormat = OutputFormat.TEXT


def set_output_format(fmt: str) -> None:
    """
    Set the global output format.

    Args:
        fmt: Format string ("jsonl", "text", or "quiet")
    """
    global _output_format
    _output_format = OutputFormat(fmt.lower())


def get_output_format() -> OutputFormat:
    """Get current output format."""
    return _output_format


def _timestamp() -> str:
    """Generate ISO timestamp with Z suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _emit_json(event: Dict[str, Any]) -> None:
    """Emit a JSON event to stdout."""
    # Add timestamp if not present
    if "ts" not in event:
        event["ts"] = _timestamp()

    # Ensure single line, compact JSON
    line = json.dumps(event, ensure_ascii=False, separators=(',', ':'))
    print(line, flush=True)


def _emit_text(message: str, level: LogLevel = LogLevel.INFO) -> None:
    """Emit a text message to stdout/stderr."""
    if level == LogLevel.ERROR:
        print(message, file=sys.stderr, flush=True)
    else:
        print(message, flush=True)


# =============================================================================
# Core Event Emitters
# =============================================================================

def emit_start(phase: str = "init", **extra) -> None:
    """
    Emit job start event.

    Args:
        phase: Initial phase name
        **extra: Additional fields to include
    """
    if _output_format == OutputFormat.JSONL:
        event = {"type": "start", "phase": phase}
        event.update(extra)
        _emit_json(event)
    elif _output_format == OutputFormat.TEXT:
        _emit_text(f"Starting: {phase}")


def emit_progress(
    phase: str,
    percent: int,
    message: Optional[str] = None,
) -> None:
    """
    Emit progress update.

    Args:
        phase: Current phase name (e.g., "analyzing", "generating")
        percent: Progress percentage (0-100)
        message: Optional human-readable message
    """
    percent = max(0, min(100, percent))

    if _output_format == OutputFormat.JSONL:
        event = {"type": "progress", "phase": phase, "percent": percent}
        if message:
            event["message"] = message
        _emit_json(event)
    elif _output_format == OutputFormat.TEXT:
        bar = "=" * (percent // 5) + " " * (20 - percent // 5)
        msg = f" - {message}" if message else ""
        _emit_text(f"[{bar}] {percent}% {phase}{msg}")


def emit_log(
    message: str,
    level: LogLevel = LogLevel.INFO,
    **extra,
) -> None:
    """
    Emit log message.

    Args:
        message: Log message
        level: Log level (debug, info, warn, error)
        **extra: Additional fields to include
    """
    if _output_format == OutputFormat.JSONL:
        event = {"type": "log", "level": level.value, "message": message}
        event.update(extra)
        _emit_json(event)
    elif _output_format == OutputFormat.TEXT:
        prefix = {"debug": "DEBUG", "info": "INFO", "warn": "WARN", "error": "ERROR"}
        _emit_text(f"[{prefix.get(level.value, 'INFO')}] {message}", level)


def emit_checkpoint(
    phase: str,
    percent: int,
    state: Dict[str, Any],
    checkpoint_id: Optional[str] = None,
    message: Optional[str] = None,
) -> str:
    """
    Emit checkpoint for job recovery.

    Args:
        phase: Current phase name
        percent: Progress percentage
        state: Serializable state data for resume
        checkpoint_id: Optional custom ID (auto-generated if not provided)
        message: Optional message

    Returns:
        The checkpoint ID
    """
    if checkpoint_id is None:
        # Generate unique ID based on content
        content = f"{phase}:{percent}:{datetime.now(timezone.utc).timestamp()}"
        checkpoint_id = f"chk_{hashlib.md5(content.encode()).hexdigest()[:12]}"

    if _output_format == OutputFormat.JSONL:
        event = {
            "type": "checkpoint",
            "id": checkpoint_id,
            "phase": phase,
            "percent": percent,
            "state": state,
        }
        if message:
            event["message"] = message
        _emit_json(event)
    elif _output_format == OutputFormat.TEXT:
        msg = f" - {message}" if message else ""
        _emit_text(f"[CHECKPOINT] {checkpoint_id} at {percent}%{msg}")

    return checkpoint_id


def emit_error(
    message: str,
    details: Optional[str] = None,
    fatal: bool = False,
) -> None:
    """
    Emit error event.

    Args:
        message: Error message
        details: Optional detailed error info (traceback, etc.)
        fatal: If True, indicates job will fail
    """
    if _output_format == OutputFormat.JSONL:
        event = {"type": "error", "message": message}
        if details:
            event["details"] = details
        if fatal:
            event["fatal"] = True
        _emit_json(event)
    elif _output_format == OutputFormat.TEXT:
        _emit_text(f"[ERROR] {message}", LogLevel.ERROR)
        if details:
            _emit_text(details, LogLevel.ERROR)


def emit_complete(
    exit_code: int = 0,
    result: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Emit job completion event.

    Args:
        exit_code: Process exit code (0 = success)
        result: Optional result data
    """
    if _output_format == OutputFormat.JSONL:
        event = {"type": "complete", "exit_code": exit_code}
        if result:
            event["result"] = result
        _emit_json(event)
    elif _output_format == OutputFormat.TEXT:
        status = "SUCCESS" if exit_code == 0 else "FAILED"
        _emit_text(f"[{status}] Exit code: {exit_code}")


def emit_raw(line: str) -> None:
    """
    Emit raw output line.

    Used for CLI output that doesn't fit event structure.

    Args:
        line: Raw output line
    """
    if _output_format == OutputFormat.JSONL:
        _emit_json({"type": "raw", "line": line})
    elif _output_format == OutputFormat.TEXT:
        _emit_text(line)


# =============================================================================
# Convenience Helpers
# =============================================================================

def info(message: str, **extra) -> None:
    """Emit info log."""
    emit_log(message, LogLevel.INFO, **extra)


def warn(message: str, **extra) -> None:
    """Emit warning log."""
    emit_log(message, LogLevel.WARN, **extra)


def error(message: str, **extra) -> None:
    """Emit error log."""
    emit_log(message, LogLevel.ERROR, **extra)


def debug(message: str, **extra) -> None:
    """Emit debug log."""
    emit_log(message, LogLevel.DEBUG, **extra)


# =============================================================================
# Progress Tracking Context
# =============================================================================

class ProgressTracker:
    """
    Helper for tracking progress through a phase with automatic checkpoints.

    Usage:
        with ProgressTracker("analyzing", total=100, checkpoint_interval=25) as tracker:
            for i, item in enumerate(items):
                process(item)
                tracker.update(i + 1, message=f"Processed {item}")
    """

    def __init__(
        self,
        phase: str,
        total: int,
        start_percent: int = 0,
        end_percent: int = 100,
        checkpoint_interval: Optional[int] = None,
        checkpoint_state_fn: Optional[Callable[[], Dict[str, Any]]] = None,
    ):
        """
        Initialize progress tracker.

        Args:
            phase: Phase name
            total: Total items to process
            start_percent: Starting percentage for this phase
            end_percent: Ending percentage for this phase
            checkpoint_interval: Emit checkpoint every N items (None = no auto-checkpoint)
            checkpoint_state_fn: Function returning state dict for checkpoints
        """
        self.phase = phase
        self.total = total
        self.start_percent = start_percent
        self.end_percent = end_percent
        self.checkpoint_interval = checkpoint_interval
        self.checkpoint_state_fn = checkpoint_state_fn
        self.current = 0
        self.checkpoints_emitted = 0

    def __enter__(self) -> "ProgressTracker":
        emit_progress(self.phase, self.start_percent, f"Starting {self.phase}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            emit_progress(self.phase, self.end_percent, f"Completed {self.phase}")
        return False

    def update(self, current: int, message: Optional[str] = None) -> None:
        """
        Update progress.

        Args:
            current: Current item number (1-based)
            message: Optional progress message
        """
        self.current = current
        percent = self._calculate_percent()
        emit_progress(self.phase, percent, message)

        # Auto-checkpoint at interval
        if self.checkpoint_interval and current % self.checkpoint_interval == 0:
            state = self.checkpoint_state_fn() if self.checkpoint_state_fn else {"current": current}
            emit_checkpoint(self.phase, percent, state)
            self.checkpoints_emitted += 1

    def _calculate_percent(self) -> int:
        """Calculate percentage within phase range."""
        if self.total == 0:
            return self.end_percent
        progress = self.current / self.total
        return int(self.start_percent + (self.end_percent - self.start_percent) * progress)

    def checkpoint(self, state: Optional[Dict[str, Any]] = None, message: Optional[str] = None) -> str:
        """
        Manually emit a checkpoint.

        Args:
            state: Optional state override (uses checkpoint_state_fn if not provided)
            message: Optional message

        Returns:
            Checkpoint ID
        """
        if state is None:
            state = self.checkpoint_state_fn() if self.checkpoint_state_fn else {"current": self.current}

        percent = self._calculate_percent()
        checkpoint_id = emit_checkpoint(self.phase, percent, state, message=message)
        self.checkpoints_emitted += 1
        return checkpoint_id


@contextmanager
def phase(name: str, start_percent: int = 0, end_percent: int = 100):
    """
    Context manager for a phase of execution.

    Usage:
        with phase("analyzing", 0, 50):
            # Do analysis work
            pass

    Args:
        name: Phase name
        start_percent: Starting percentage
        end_percent: Ending percentage
    """
    emit_progress(name, start_percent, f"Starting {name}")
    try:
        yield
        emit_progress(name, end_percent, f"Completed {name}")
    except Exception as e:
        emit_error(f"Failed during {name}: {str(e)}", fatal=True)
        raise


# =============================================================================
# Resume Support
# =============================================================================

class ResumeContext:
    """
    Manages resume state for checkpointed execution.

    Usage:
        resume = ResumeContext()
        start_index = resume.get("items_processed", 0)

        for i, item in enumerate(items):
            if resume.should_skip("items_processed", i):
                continue
            process(item)
    """

    def __init__(self):
        """Initialize resume context from environment."""
        self.state: Optional[Dict[str, Any]] = None
        self.checkpoint_id: Optional[str] = None

        # Load from environment (set by portal ProcessExecutor)
        resume_state = os.environ.get("RESUME_STATE")
        if resume_state:
            try:
                self.state = json.loads(resume_state)
                info(f"Resuming from checkpoint state")
            except json.JSONDecodeError:
                warn("Invalid RESUME_STATE, starting fresh")

        self.checkpoint_id = os.environ.get("RESUME_CHECKPOINT_ID")

    @property
    def is_resuming(self) -> bool:
        """Check if we're resuming from a checkpoint."""
        return self.state is not None

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get value from resume state.

        Args:
            key: Key to look up
            default: Default value if not found

        Returns:
            Value from state or default
        """
        if self.state:
            return self.state.get(key, default)
        return default

    def should_skip(self, key: str, current: int) -> bool:
        """
        Check if current item should be skipped (already processed).

        Args:
            key: Key tracking progress (e.g., "items_processed")
            current: Current item index (0-based)

        Returns:
            True if this item was already processed
        """
        if not self.is_resuming:
            return False
        resume_value = self.get(key, 0)
        return current < resume_value

    def get_start_index(self, key: str = "items_processed") -> int:
        """
        Get the index to start processing from.

        Args:
            key: Key tracking progress

        Returns:
            Starting index (0 if not resuming)
        """
        return self.get(key, 0)


# =============================================================================
# Job Context
# =============================================================================

class JobContext:
    """
    Combined context for job execution with output and resume support.

    Usage:
        with JobContext("plan", output_format="jsonl") as ctx:
            ctx.info("Starting work...")

            with ctx.phase("analyzing", 0, 50):
                # Do work
                pass

            ctx.complete(result={"output": "plan.md"})
    """

    def __init__(
        self,
        command_name: str,
        output_format: str = "text",
    ):
        """
        Initialize job context.

        Args:
            command_name: Name of the CLI command
            output_format: Output format (jsonl, text, quiet)
        """
        self.command_name = command_name
        set_output_format(output_format)
        self.resume = ResumeContext()

    def __enter__(self) -> "JobContext":
        if self.resume.is_resuming:
            emit_start("resuming", from_checkpoint=self.resume.checkpoint_id)
        else:
            emit_start("init")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            import traceback
            emit_error(
                str(exc_val),
                details=traceback.format_exc(),
                fatal=True
            )
            emit_complete(1)
        return False

    # Delegate to module-level functions
    def info(self, message: str, **extra) -> None:
        info(message, **extra)

    def warn(self, message: str, **extra) -> None:
        warn(message, **extra)

    def error(self, message: str, **extra) -> None:
        error(message, **extra)

    def debug(self, message: str, **extra) -> None:
        debug(message, **extra)

    def progress(self, phase_name: str, percent: int, message: Optional[str] = None) -> None:
        emit_progress(phase_name, percent, message)

    def checkpoint(
        self,
        phase_name: str,
        percent: int,
        state: Dict[str, Any],
        message: Optional[str] = None,
    ) -> str:
        return emit_checkpoint(phase_name, percent, state, message=message)

    def complete(self, exit_code: int = 0, result: Optional[Dict[str, Any]] = None) -> None:
        emit_complete(exit_code, result)

    @contextmanager
    def phase(self, name: str, start_percent: int = 0, end_percent: int = 100):
        """Create a phase context."""
        with phase(name, start_percent, end_percent):
            yield

    def tracker(
        self,
        phase_name: str,
        total: int,
        start_percent: int = 0,
        end_percent: int = 100,
        checkpoint_interval: Optional[int] = None,
        checkpoint_state_fn: Optional[Callable[[], Dict[str, Any]]] = None,
    ) -> ProgressTracker:
        """Create a progress tracker for a phase."""
        return ProgressTracker(
            phase=phase_name,
            total=total,
            start_percent=start_percent,
            end_percent=end_percent,
            checkpoint_interval=checkpoint_interval,
            checkpoint_state_fn=checkpoint_state_fn,
        )
