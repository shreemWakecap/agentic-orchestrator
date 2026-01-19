"""
Checkpoint Manager - Helper for CLI commands to manage checkpoints.

This module provides utilities for:
- Emitting checkpoint events during CLI execution
- Restoring state when resuming from a checkpoint
- Tracking progress and determining what work to skip
"""
import os
import json
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List


class CheckpointManager:
    """
    Manages checkpoint emission and restoration for CLI commands.

    Usage:
        cp = CheckpointManager("plan")

        # Check if resuming
        if cp.is_resuming:
            start_index = cp.get_resume_value("items_processed", 0)

        # During execution, emit checkpoints
        for i, item in enumerate(items):
            if cp.should_skip("items_processed", i):
                continue

            process_item(item)

            if (i + 1) % 25 == 0:
                cp.emit_checkpoint(
                    phase="processing",
                    percent=int(((i + 1) / len(items)) * 100),
                    state={"items_processed": i + 1}
                )
    """

    def __init__(self, command_name: str):
        """
        Initialize checkpoint manager.

        Args:
            command_name: Name of the CLI command (e.g., "plan", "build")
        """
        self.command_name = command_name
        self.checkpoint_count = 0
        self.resume_state: Optional[Dict[str, Any]] = None
        self.resume_checkpoint_id: Optional[str] = None

        # Check for resume state from environment
        resume_env = os.environ.get("RESUME_STATE")
        if resume_env:
            try:
                self.resume_state = json.loads(resume_env)
            except json.JSONDecodeError:
                self._emit_log("warning", f"Invalid RESUME_STATE JSON: {resume_env[:100]}")

        # Check for checkpoint ID
        self.resume_checkpoint_id = os.environ.get("RESUME_CHECKPOINT_ID")

    @property
    def is_resuming(self) -> bool:
        """Check if this is a resumed execution."""
        return self.resume_state is not None

    def get_resume_value(self, key: str, default: Any = None) -> Any:
        """
        Get a value from resume state.

        Args:
            key: Key to look up in resume state
            default: Default value if key not found

        Returns:
            Value from resume state or default
        """
        if self.resume_state:
            return self.resume_state.get(key, default)
        return default

    def should_skip(self, progress_key: str, current_value: int) -> bool:
        """
        Check if current work should be skipped (already done in previous run).

        Args:
            progress_key: Key in state that tracks progress (e.g., "items_processed")
            current_value: Current progress value

        Returns:
            True if this work was already completed in previous run
        """
        if not self.is_resuming:
            return False
        resume_value = self.get_resume_value(progress_key, 0)
        return current_value < resume_value

    def emit_checkpoint(
        self,
        phase: str,
        percent: int,
        state: Dict[str, Any],
        message: Optional[str] = None,
        checkpoint_id: Optional[str] = None,
    ) -> str:
        """
        Emit a checkpoint event to stdout.

        Args:
            phase: Current phase name (e.g., "analyzing", "generating")
            percent: Progress percentage (0-100)
            state: Serializable state dict that can restore execution
            message: Optional human-readable message
            checkpoint_id: Optional explicit checkpoint ID (auto-generated if not provided)

        Returns:
            The checkpoint ID
        """
        self.checkpoint_count += 1

        if checkpoint_id is None:
            # Generate unique checkpoint ID
            timestamp = datetime.now(timezone.utc).isoformat()
            hash_input = f"{self.command_name}:{phase}:{percent}:{timestamp}"
            hash_suffix = hashlib.md5(hash_input.encode()).hexdigest()[:8]
            checkpoint_id = f"chk_{self.command_name}_{self.checkpoint_count:03d}_{hash_suffix}"

        event = {
            "type": "checkpoint",
            "id": checkpoint_id,
            "phase": phase,
            "percent": percent,
            "state": state,
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        if message:
            event["message"] = message

        print(json.dumps(event), flush=True)
        return checkpoint_id

    def emit_event(self, event_type: str, **data) -> None:
        """
        Emit a generic JSONL event to stdout.

        Args:
            event_type: Type of event (e.g., "start", "progress", "complete")
            **data: Additional event data
        """
        event = {
            "type": event_type,
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            **data
        }
        print(json.dumps(event), flush=True)

    def _emit_log(self, level: str, message: str) -> None:
        """Emit a log event."""
        self.emit_event("log", level=level, message=message)

    def log_info(self, message: str) -> None:
        """Emit an info-level log."""
        self._emit_log("info", message)

    def log_warning(self, message: str) -> None:
        """Emit a warning-level log."""
        self._emit_log("warning", message)

    def log_error(self, message: str) -> None:
        """Emit an error-level log."""
        self._emit_log("error", message)

    def start(self, phase: str = "init") -> None:
        """
        Emit start event, handling resume case.

        Args:
            phase: Initial phase name
        """
        if self.is_resuming:
            self.log_info(
                f"Resuming from checkpoint {self.resume_checkpoint_id or 'unknown'}"
            )
            self.emit_event("start", phase=phase, resumed=True,
                           from_checkpoint=self.resume_checkpoint_id)
        else:
            self.emit_event("start", phase=phase)

    def progress(self, phase: str, percent: int, message: Optional[str] = None) -> None:
        """
        Emit progress event.

        Args:
            phase: Current phase name
            percent: Progress percentage (0-100)
            message: Optional progress message
        """
        data = {"phase": phase, "percent": percent}
        if message:
            data["message"] = message
        self.emit_event("progress", **data)

    def complete(self, exit_code: int = 0, result: Optional[Dict[str, Any]] = None) -> None:
        """
        Emit completion event.

        Args:
            exit_code: Exit code (0 for success)
            result: Optional result data
        """
        data = {"exit_code": exit_code}
        if result:
            data["result"] = result
        self.emit_event("complete", **data)

    def fail(self, error: str, exit_code: int = 1) -> None:
        """
        Emit failure event.

        Args:
            error: Error message
            exit_code: Exit code (non-zero)
        """
        self.emit_event("error", message=error, exit_code=exit_code)


class BatchCheckpointer:
    """
    Helper for checkpointing batch processing operations.

    Automatically emits checkpoints at configured intervals.

    Usage:
        checkpointer = BatchCheckpointer(
            manager=CheckpointManager("plan"),
            total_items=100,
            checkpoint_interval=25,
            phase="processing"
        )

        for i, item in enumerate(items):
            if checkpointer.should_skip(i):
                continue

            process_item(item)
            checkpointer.item_completed(i, {"last_item_id": item.id})
    """

    def __init__(
        self,
        manager: CheckpointManager,
        total_items: int,
        checkpoint_interval: int = 25,
        phase: str = "processing",
        progress_key: str = "items_processed",
    ):
        """
        Initialize batch checkpointer.

        Args:
            manager: CheckpointManager instance
            total_items: Total number of items to process
            checkpoint_interval: Emit checkpoint every N items
            phase: Phase name for checkpoints
            progress_key: Key to use for progress tracking in state
        """
        self.manager = manager
        self.total_items = total_items
        self.checkpoint_interval = checkpoint_interval
        self.phase = phase
        self.progress_key = progress_key
        self.items_completed = 0
        self.additional_state: Dict[str, Any] = {}

    def should_skip(self, index: int) -> bool:
        """Check if item at index should be skipped (already processed)."""
        return self.manager.should_skip(self.progress_key, index)

    def get_start_index(self) -> int:
        """Get the index to start processing from."""
        return self.manager.get_resume_value(self.progress_key, 0)

    def set_additional_state(self, **kwargs) -> None:
        """Set additional state to include in checkpoints."""
        self.additional_state.update(kwargs)

    def item_completed(
        self,
        index: int,
        item_state: Optional[Dict[str, Any]] = None,
        force_checkpoint: bool = False,
    ) -> Optional[str]:
        """
        Mark an item as completed, potentially emitting a checkpoint.

        Args:
            index: Index of completed item (0-based)
            item_state: Optional item-specific state to include
            force_checkpoint: Force checkpoint emission regardless of interval

        Returns:
            Checkpoint ID if checkpoint was emitted, None otherwise
        """
        self.items_completed = index + 1
        percent = int((self.items_completed / self.total_items) * 100)

        # Emit progress update
        self.manager.progress(self.phase, percent)

        # Check if checkpoint needed
        should_checkpoint = (
            force_checkpoint or
            self.items_completed % self.checkpoint_interval == 0 or
            self.items_completed == self.total_items
        )

        if should_checkpoint:
            state = {
                self.progress_key: self.items_completed,
                **self.additional_state,
            }
            if item_state:
                state.update(item_state)

            return self.manager.emit_checkpoint(
                phase=self.phase,
                percent=percent,
                state=state,
                message=f"Completed {self.items_completed}/{self.total_items} items"
            )

        return None


def load_checkpoint_state() -> Optional[Dict[str, Any]]:
    """
    Load checkpoint state from environment.

    Returns:
        Parsed state dict or None if not resuming
    """
    resume_env = os.environ.get("RESUME_STATE")
    if resume_env:
        try:
            return json.loads(resume_env)
        except json.JSONDecodeError:
            return None
    return None


def get_resume_checkpoint_id() -> Optional[str]:
    """
    Get the checkpoint ID being resumed from.

    Returns:
        Checkpoint ID string or None
    """
    return os.environ.get("RESUME_CHECKPOINT_ID")
