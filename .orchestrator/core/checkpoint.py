"""
Planning checkpoint and recovery.

Saves state after each planning phase to allow resuming interrupted plans.
"""
import hashlib
import json
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class PlanningCheckpoint:
    """State checkpoint during planning workflow."""

    request: str
    request_hash: str
    phase: str  # "scout", "architect", "planner", "validator", "completed"
    complexity: str = "simple"

    # Results from completed phases
    scout_result: Optional[str] = None
    architect_result: Optional[str] = None
    planner_result: Optional[str] = None
    validator_result: Optional[str] = None

    # Metadata
    created_at: str = ""
    updated_at: str = ""
    attempt_count: int = 1

    def __post_init__(self):
        now = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now
        self.updated_at = now


class CheckpointManager:
    """Manage planning checkpoints for recovery."""

    def __init__(self, specs_dir: Path):
        self.checkpoint_dir = specs_dir / "checkpoints"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def _get_checkpoint_path(self, request_hash: str) -> Path:
        """Get the checkpoint file path for a request hash."""
        return self.checkpoint_dir / f"{request_hash}.checkpoint.json"

    @staticmethod
    def compute_request_hash(request: str) -> str:
        """Compute a hash for the request string."""
        return hashlib.sha256(request.encode()).hexdigest()[:16]

    def save(self, checkpoint: PlanningCheckpoint) -> None:
        """
        Save checkpoint to disk.

        Args:
            checkpoint: The checkpoint to save
        """
        checkpoint.updated_at = datetime.now().isoformat()
        path = self._get_checkpoint_path(checkpoint.request_hash)

        try:
            path.write_text(
                json.dumps(asdict(checkpoint), indent=2),
                encoding="utf-8"
            )
        except Exception:
            pass  # Checkpoint save failure is not critical

    def load(self, request: str) -> Optional[PlanningCheckpoint]:
        """
        Load checkpoint for a request if it exists.

        Args:
            request: The original request string

        Returns:
            PlanningCheckpoint if exists and valid, None otherwise
        """
        request_hash = self.compute_request_hash(request)
        path = self._get_checkpoint_path(request_hash)

        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return PlanningCheckpoint(**data)
        except Exception:
            # Invalid checkpoint, remove it
            try:
                path.unlink()
            except Exception:
                pass
            return None

    def clear(self, request: str) -> None:
        """
        Remove checkpoint for a request (after successful completion).

        Args:
            request: The original request string
        """
        request_hash = self.compute_request_hash(request)
        path = self._get_checkpoint_path(request_hash)

        if path.exists():
            try:
                path.unlink()
            except Exception:
                pass

    def clear_by_hash(self, request_hash: str) -> None:
        """Remove checkpoint by hash."""
        path = self._get_checkpoint_path(request_hash)
        if path.exists():
            try:
                path.unlink()
            except Exception:
                pass

    def list_pending(self) -> list[dict]:
        """
        List all pending checkpoints (interrupted plans).

        Returns:
            List of checkpoint summaries
        """
        pending = []
        try:
            for f in self.checkpoint_dir.glob("*.checkpoint.json"):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    pending.append({
                        "request_hash": data.get("request_hash", f.stem),
                        "request": data.get("request", "")[:50],
                        "phase": data.get("phase", "unknown"),
                        "created_at": data.get("created_at", ""),
                        "attempt_count": data.get("attempt_count", 1),
                    })
                except Exception:
                    pass
        except Exception:
            pass

        return pending

    def clear_all(self) -> int:
        """
        Clear all checkpoints.

        Returns:
            Number of checkpoints cleared
        """
        count = 0
        try:
            for f in self.checkpoint_dir.glob("*.checkpoint.json"):
                try:
                    f.unlink()
                    count += 1
                except Exception:
                    pass
        except Exception:
            pass
        return count

    def get_resumable(self, request: str) -> Optional[tuple[str, PlanningCheckpoint]]:
        """
        Check if a request can be resumed from checkpoint.

        Args:
            request: The request to check

        Returns:
            Tuple of (resume_phase, checkpoint) if resumable, None otherwise
        """
        checkpoint = self.load(request)
        if not checkpoint:
            return None

        # Determine what phase to resume from
        phase = checkpoint.phase
        if phase == "completed":
            return None  # Already done

        # Map phase to next phase
        phase_order = ["scout", "architect", "planner", "validator", "completed"]
        if phase in phase_order:
            return (phase, checkpoint)

        return None
