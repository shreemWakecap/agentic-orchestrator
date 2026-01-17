"""
Run Repository.

Handles active run tracking and events.
"""
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..connection import Database


class RunRepository:
    """Repository for active run tracking."""

    def __init__(self, db: "Database"):
        self.db = db

    def create(self, run_id: str, workflow: str, description: str = None,
               plan_id: str = None, plan_path: str = None) -> int:
        """Create a new run."""
        now = datetime.now().isoformat()
        with self.db.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO active_runs (run_id, workflow, status, started_at, plan_id,
                                        plan_path, description, progress)
                VALUES (?, ?, 'pending', ?, ?, ?, ?, 0)
            """, (run_id, workflow, now, plan_id, plan_path, description))
            return cursor.lastrowid

    def get(self, run_id: str) -> Optional[dict]:
        """Get run by ID."""
        row = self.db.fetchone(
            "SELECT * FROM active_runs WHERE run_id = ?", (run_id,)
        )
        if row:
            row['data'] = self.db.from_json(row.get('data_json'), {})
        return row

    def update(self, run_id: str, **kwargs):
        """Update run fields."""
        if 'data' in kwargs:
            kwargs['data_json'] = self.db.to_json(kwargs.pop('data'))

        set_clause = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [run_id]

        with self.db.transaction() as conn:
            conn.execute(
                f"UPDATE active_runs SET {set_clause} WHERE run_id = ?",
                values
            )

    def add_event(self, run_id: str, event_type: str, data: dict = None):
        """Add event to run."""
        now = datetime.now().isoformat()
        with self.db.transaction() as conn:
            conn.execute("""
                INSERT INTO run_events (run_id, event_type, timestamp, data_json)
                VALUES (?, ?, ?, ?)
            """, (run_id, event_type, now, self.db.to_json(data)))

    def get_events(self, run_id: str, since_id: int = 0) -> list[dict]:
        """Get events for a run since a given ID."""
        rows = self.db.fetchall("""
            SELECT * FROM run_events WHERE run_id = ? AND id > ?
            ORDER BY timestamp
        """, (run_id, since_id))
        for row in rows:
            row['data'] = self.db.from_json(row.get('data_json'), {})
        return rows

    def list_active(self, status: str = None) -> list[dict]:
        """List active runs with optional status filter."""
        if status:
            rows = self.db.fetchall(
                "SELECT * FROM active_runs WHERE status = ? ORDER BY started_at DESC",
                (status,)
            )
        else:
            rows = self.db.fetchall(
                "SELECT * FROM active_runs ORDER BY started_at DESC"
            )
        for row in rows:
            row['data'] = self.db.from_json(row.get('data_json'), {})
        return rows

    def delete(self, run_id: str):
        """Delete a run and its events."""
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM active_runs WHERE run_id = ?", (run_id,))
