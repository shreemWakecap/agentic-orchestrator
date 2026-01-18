"""
Build State Repository.

Handles build state and step state database operations.
"""
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..connection import Database


class BuildStateRepository:
    """Repository for build state operations."""

    def __init__(self, db: "Database"):
        self.db = db

    def create(self, plan_id: str, total_steps: int = 0) -> int:
        """Create build state for a plan."""
        now = datetime.now().isoformat()
        with self.db.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO build_states (plan_id, status, started_at, updated_at, total_steps,
                                         completed_steps_json, failed_steps_json, skipped_steps_json,
                                         files_created_json, files_modified_json)
                VALUES (?, 'pending', ?, ?, ?, '[]', '[]', '[]', '[]', '[]')
            """, (plan_id, now, now, total_steps))
            return cursor.lastrowid

    def get(self, plan_id: str) -> Optional[dict]:
        """Get build state for a plan."""
        row = self.db.fetchone(
            "SELECT * FROM build_states WHERE plan_id = ?", (plan_id,)
        )
        if row:
            row['completed_steps'] = self.db.from_json(row.get('completed_steps_json'), [])
            row['failed_steps'] = self.db.from_json(row.get('failed_steps_json'), [])
            row['skipped_steps'] = self.db.from_json(row.get('skipped_steps_json'), [])
            row['files_created'] = self.db.from_json(row.get('files_created_json'), [])
            row['files_modified'] = self.db.from_json(row.get('files_modified_json'), [])
        return row

    def update(self, plan_id: str, **kwargs):
        """Update build state fields."""
        if not kwargs:
            return

        kwargs['updated_at'] = datetime.now().isoformat()

        # Convert list fields to JSON
        for field in ['completed_steps', 'failed_steps', 'skipped_steps',
                      'files_created', 'files_modified']:
            if field in kwargs:
                kwargs[f"{field}_json"] = self.db.to_json(kwargs.pop(field))

        set_clause = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [plan_id]

        with self.db.transaction() as conn:
            conn.execute(
                f"UPDATE build_states SET {set_clause} WHERE plan_id = ?",
                values
            )

    def set_step_state(self, plan_id: str, step_id: str, status: str,
                       started_at: str = None, completed_at: str = None,
                       retry_count: int = 0, error: str = None,
                       files_affected: list[str] = None, summary: str = None):
        """Create or update step state."""
        with self.db.transaction() as conn:
            conn.execute("""
                INSERT INTO step_states (plan_id, step_id, status, started_at, completed_at,
                                        retry_count, error, files_affected_json, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(plan_id, step_id) DO UPDATE SET
                    status = excluded.status,
                    started_at = COALESCE(excluded.started_at, step_states.started_at),
                    completed_at = excluded.completed_at,
                    retry_count = excluded.retry_count,
                    error = excluded.error,
                    files_affected_json = excluded.files_affected_json,
                    summary = excluded.summary
            """, (
                plan_id, step_id, status, started_at, completed_at,
                retry_count, error,
                self.db.to_json(files_affected or []),
                summary
            ))

    def get_step_states(self, plan_id: str) -> list[dict]:
        """Get all step states for a plan."""
        rows = self.db.fetchall(
            "SELECT * FROM step_states WHERE plan_id = ?", (plan_id,)
        )
        for row in rows:
            row['files_affected'] = self.db.from_json(row.get('files_affected_json'), [])
        return rows

    def get_step_state(self, plan_id: str, step_id: str) -> Optional[dict]:
        """Get step state for a specific step."""
        row = self.db.fetchone(
            "SELECT * FROM step_states WHERE plan_id = ? AND step_id = ?",
            (plan_id, step_id)
        )
        if row:
            row['files_affected'] = self.db.from_json(row.get('files_affected_json'), [])
        return row

    def exists(self, plan_id: str) -> bool:
        """Check if build state exists for a plan."""
        row = self.db.fetchone(
            "SELECT 1 FROM build_states WHERE plan_id = ?", (plan_id,)
        )
        return row is not None

    def clear(self, plan_id: str) -> bool:
        """Clear all build state and step states for a plan.

        This removes:
        - The build state record
        - All associated step state records

        Returns True if any records were deleted.
        """
        with self.db.transaction() as conn:
            # Delete step states first (child records)
            conn.execute(
                "DELETE FROM step_states WHERE plan_id = ?", (plan_id,)
            )
            # Delete build state
            cursor = conn.execute(
                "DELETE FROM build_states WHERE plan_id = ?", (plan_id,)
            )
            return cursor.rowcount > 0

    def cancel(self, plan_id: str) -> bool:
        """Cancel a build by setting status to 'cancelled'.

        Allows graceful stopping of stuck or unwanted builds.

        Returns True if the build was cancelled, False if not found.
        """
        now = datetime.now().isoformat()
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "UPDATE build_states SET status = 'cancelled', updated_at = ? WHERE plan_id = ?",
                (now, plan_id)
            )
            return cursor.rowcount > 0

    def pause(self, plan_id: str) -> bool:
        """Pause a build by setting status to 'paused'.

        Allows graceful pausing of builds that can be resumed later.

        Returns True if the build was paused, False if not found.
        """
        now = datetime.now().isoformat()
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "UPDATE build_states SET status = 'paused', updated_at = ? WHERE plan_id = ?",
                (now, plan_id)
            )
            return cursor.rowcount > 0

    def update_status(self, plan_id: str, status: str) -> bool:
        """Update build state status.

        This method is called by PlanStatusService to cascade status changes
        from the Plan (aggregate root) to build_states.

        Args:
            plan_id: The plan identifier
            status: New status value

        Returns:
            True if update succeeded, False if build state not found
        """
        self.update(plan_id, status=status)
        return True

    # =====================================================
    # GOAL CONTEXT PERSISTENCE
    # =====================================================

    def save_goal_context(self, plan_id: str, goal_context: dict) -> None:
        """Save or update goal verification state.

        Args:
            plan_id: The plan identifier
            goal_context: Dictionary with goal, original_request, verification_attempts,
                         missing_items, completion_percentage, goal_achieved,
                         context_notes, verify_commands
        """
        now = datetime.now().isoformat()
        with self.db.transaction() as conn:
            conn.execute("""
                INSERT INTO goal_verification_state
                (plan_id, goal, original_request, verification_attempt,
                 missing_items_json, completion_percentage, goal_achieved,
                 context_notes_json, verify_commands_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(plan_id) DO UPDATE SET
                    goal = excluded.goal,
                    original_request = excluded.original_request,
                    verification_attempt = excluded.verification_attempt,
                    missing_items_json = excluded.missing_items_json,
                    completion_percentage = excluded.completion_percentage,
                    goal_achieved = excluded.goal_achieved,
                    context_notes_json = excluded.context_notes_json,
                    verify_commands_json = excluded.verify_commands_json,
                    updated_at = excluded.updated_at
            """, (
                plan_id,
                goal_context.get('goal', ''),
                goal_context.get('original_request', ''),
                goal_context.get('verification_attempts', 0),
                self.db.to_json(goal_context.get('missing_items', [])),
                goal_context.get('completion_percentage', 0),
                1 if goal_context.get('goal_achieved', False) else 0,
                self.db.to_json(goal_context.get('context_notes', [])),
                self.db.to_json(goal_context.get('verify_commands', [])),
                now, now
            ))

    def get_goal_context(self, plan_id: str) -> Optional[dict]:
        """Load goal verification state.

        Args:
            plan_id: The plan identifier

        Returns:
            Dictionary with goal context or None if not found
        """
        row = self.db.fetchone(
            "SELECT * FROM goal_verification_state WHERE plan_id = ?", (plan_id,)
        )
        if row:
            return {
                'goal': row.get('goal', ''),
                'original_request': row.get('original_request', ''),
                'verification_attempts': row.get('verification_attempt', 0),
                'missing_items': self.db.from_json(row.get('missing_items_json'), []),
                'completion_percentage': row.get('completion_percentage', 0),
                'goal_achieved': bool(row.get('goal_achieved', 0)),
                'context_notes': self.db.from_json(row.get('context_notes_json'), []),
                'verify_commands': self.db.from_json(row.get('verify_commands_json'), []),
            }
        return None

    def clear_goal_context(self, plan_id: str) -> bool:
        """Clear goal verification state for a plan.

        Args:
            plan_id: The plan identifier

        Returns:
            True if deleted, False if not found
        """
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM goal_verification_state WHERE plan_id = ?", (plan_id,)
            )
            return cursor.rowcount > 0

    # =====================================================
    # RETRY HISTORY TRACKING
    # =====================================================

    def add_step_retry_history(
        self, plan_id: str, step_id: str, error: str, duration_ms: int
    ) -> None:
        """Append to step retry history.

        Args:
            plan_id: The plan identifier
            step_id: The step identifier
            error: Error message from the failed attempt
            duration_ms: Duration of the failed attempt in milliseconds
        """
        now = datetime.now().isoformat()

        # Get existing history
        step_state = self.get_step_state(plan_id, step_id)
        history = []
        if step_state:
            history = self.db.from_json(step_state.get('retry_history_json'), [])

        # Append new entry
        history.append({
            'timestamp': now,
            'error': error,
            'duration_ms': duration_ms
        })

        with self.db.transaction() as conn:
            conn.execute("""
                UPDATE step_states
                SET retry_history_json = ?
                WHERE plan_id = ? AND step_id = ?
            """, (self.db.to_json(history), plan_id, step_id))

    def get_step_retry_history(self, plan_id: str, step_id: str) -> list[dict]:
        """Get retry history for a step.

        Args:
            plan_id: The plan identifier
            step_id: The step identifier

        Returns:
            List of retry history entries
        """
        step_state = self.get_step_state(plan_id, step_id)
        if step_state:
            return self.db.from_json(step_state.get('retry_history_json'), [])
        return []

    # =====================================================
    # FULL OUTPUT STORAGE
    # =====================================================

    def save_step_full_output(self, plan_id: str, step_id: str, output: str) -> None:
        """Save full step output (up to 5000 chars).

        Args:
            plan_id: The plan identifier
            step_id: The step identifier
            output: Full output to save (will be truncated to 5000 chars)
        """
        truncated = output[:5000] if len(output) > 5000 else output
        with self.db.transaction() as conn:
            conn.execute("""
                UPDATE step_states
                SET full_output = ?
                WHERE plan_id = ? AND step_id = ?
            """, (truncated, plan_id, step_id))

    def get_step_full_output(self, plan_id: str, step_id: str) -> Optional[str]:
        """Get full step output.

        Args:
            plan_id: The plan identifier
            step_id: The step identifier

        Returns:
            Full output or None if not found
        """
        row = self.db.fetchone(
            "SELECT full_output FROM step_states WHERE plan_id = ? AND step_id = ?",
            (plan_id, step_id)
        )
        return row.get('full_output') if row else None

    # =====================================================
    # BATCH OPERATIONS
    # =====================================================

    def batch_update_step_states(self, plan_id: str, step_updates: list[dict]) -> None:
        """Atomically update multiple step states in one transaction.

        Args:
            plan_id: The plan identifier
            step_updates: List of dicts with step_id and fields to update
                         Each dict should have at least 'step_id' and 'status'
        """
        with self.db.transaction() as conn:
            for update in step_updates:
                step_id = update.pop('step_id')
                status = update.get('status', 'pending')
                started_at = update.get('started_at')
                completed_at = update.get('completed_at')
                retry_count = update.get('retry_count', 0)
                error = update.get('error')
                files_affected = update.get('files_affected', [])
                summary = update.get('summary')

                conn.execute("""
                    INSERT INTO step_states (plan_id, step_id, status, started_at, completed_at,
                                            retry_count, error, files_affected_json, summary)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(plan_id, step_id) DO UPDATE SET
                        status = excluded.status,
                        started_at = COALESCE(excluded.started_at, step_states.started_at),
                        completed_at = excluded.completed_at,
                        retry_count = excluded.retry_count,
                        error = excluded.error,
                        files_affected_json = excluded.files_affected_json,
                        summary = excluded.summary
                """, (
                    plan_id, step_id, status, started_at, completed_at,
                    retry_count, error,
                    self.db.to_json(files_affected),
                    summary
                ))

    # =====================================================
    # EXECUTION MODE TRACKING
    # =====================================================

    def update_execution_mode(
        self, plan_id: str, mode: str, wave_index: int = 0
    ) -> None:
        """Update execution mode and wave index.

        Args:
            plan_id: The plan identifier
            mode: 'sequential', 'parallel', or 'coordinated'
            wave_index: Current wave index for parallel execution
        """
        self.update(plan_id, execution_mode=mode, current_wave_index=wave_index)
