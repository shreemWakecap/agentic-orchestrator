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
