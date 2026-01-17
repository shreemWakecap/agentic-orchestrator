"""
Plan Repository.

Handles all plan-related database operations.
"""
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..connection import Database


class PlanRepository:
    """Repository for plan operations."""

    def __init__(self, db: "Database"):
        self.db = db

    def create(self, plan_id: str, goal: str, request: str, raw_content: str,
               context: list[str] = None, verify: list[str] = None) -> int:
        """Create a new plan. Returns the row ID."""
        now = datetime.now().isoformat()
        with self.db.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO plans (plan_id, goal, request, raw_content, context_json,
                                   verify_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                plan_id, goal, request, raw_content,
                self.db.to_json(context or []),
                self.db.to_json(verify or []),
                now, now
            ))
            return cursor.lastrowid

    def get_by_id(self, plan_id: str) -> Optional[dict]:
        """Get plan by plan_id."""
        row = self.db.fetchone("SELECT * FROM plans WHERE plan_id = ?", (plan_id,))
        if row:
            row['context'] = self.db.from_json(row.get('context_json'), [])
            row['verify'] = self.db.from_json(row.get('verify_json'), [])
        return row

    def list_by_status(self, status: str) -> list[dict]:
        """List plans by status."""
        rows = self.db.fetchall(
            "SELECT * FROM plans WHERE status = ? ORDER BY created_at DESC",
            (status,)
        )
        for row in rows:
            row['context'] = self.db.from_json(row.get('context_json'), [])
            row['verify'] = self.db.from_json(row.get('verify_json'), [])
        return rows

    def list_all(self) -> list[dict]:
        """List all plans ordered by creation."""
        rows = self.db.fetchall("SELECT * FROM plans ORDER BY created_at DESC")
        for row in rows:
            row['context'] = self.db.from_json(row.get('context_json'), [])
            row['verify'] = self.db.from_json(row.get('verify_json'), [])
        return rows

    def update_status(self, plan_id: str, status: str):
        """Update plan status."""
        now = datetime.now().isoformat()
        with self.db.transaction() as conn:
            if status == 'completed':
                conn.execute("""
                    UPDATE plans SET status = ?, updated_at = ?, completed_at = ?
                    WHERE plan_id = ?
                """, (status, now, now, plan_id))
            else:
                conn.execute("""
                    UPDATE plans SET status = ?, updated_at = ? WHERE plan_id = ?
                """, (status, now, plan_id))

    def delete(self, plan_id: str):
        """Delete a plan (cascades to steps, phases, build state)."""
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM plans WHERE plan_id = ?", (plan_id,))

    def add_phase(self, plan_id: str, phase_id: str, name: str,
                  phase_number: int, can_parallelize: bool = False):
        """Add a phase to a plan."""
        with self.db.transaction() as conn:
            conn.execute("""
                INSERT INTO plan_phases (plan_id, phase_id, name, phase_number, can_parallelize)
                VALUES (?, ?, ?, ?, ?)
            """, (plan_id, phase_id, name, phase_number, int(can_parallelize)))

    def add_step(self, plan_id: str, phase_id: str, step_id: str, action: str,
                 description: str, step_order: int, target: str = None,
                 done: str = None, inputs: list[str] = None, needs: list[str] = None):
        """Add a step to a plan."""
        with self.db.transaction() as conn:
            conn.execute("""
                INSERT INTO plan_steps (plan_id, phase_id, step_id, action, target,
                                       description, done, inputs_json, needs_json, step_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                plan_id, phase_id, step_id, action, target, description, done,
                self.db.to_json(inputs or []),
                self.db.to_json(needs or []),
                step_order
            ))

    def get_steps(self, plan_id: str) -> list[dict]:
        """Get all steps for a plan."""
        rows = self.db.fetchall(
            "SELECT * FROM plan_steps WHERE plan_id = ? ORDER BY step_order",
            (plan_id,)
        )
        for row in rows:
            row['inputs'] = self.db.from_json(row.get('inputs_json'), [])
            row['needs'] = self.db.from_json(row.get('needs_json'), [])
        return rows

    def get_phases(self, plan_id: str) -> list[dict]:
        """Get all phases for a plan."""
        return self.db.fetchall(
            "SELECT * FROM plan_phases WHERE plan_id = ? ORDER BY phase_number",
            (plan_id,)
        )

    def get_next_plan_number(self) -> int:
        """Get the next plan number for ID generation."""
        row = self.db.fetchone("SELECT MAX(id) as max_id FROM plans")
        if row and row['max_id']:
            return row['max_id'] + 1
        return 1

    def exists(self, plan_id: str) -> bool:
        """Check if a plan exists."""
        row = self.db.fetchone(
            "SELECT 1 FROM plans WHERE plan_id = ?", (plan_id,)
        )
        return row is not None
