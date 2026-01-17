"""
Cost Repository.

Handles cost tracking and history operations.
"""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..connection import Database


class CostRepository:
    """Repository for cost tracking operations."""

    def __init__(self, db: "Database"):
        self.db = db

    def record(self, workflow: str, run_id: str, started_at: str, completed_at: str,
               total_tokens: int, estimated_cost: float, agents: dict,
               actual_cost: float = None):
        """Record completed workflow cost."""
        with self.db.transaction() as conn:
            conn.execute("""
                INSERT INTO cost_history (workflow, run_id, started_at, completed_at,
                                         total_tokens, estimated_cost, actual_cost, agents_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (workflow, run_id, started_at, completed_at, total_tokens,
                  estimated_cost, actual_cost, self.db.to_json(agents)))

    def get_history(self, since: str = None, workflow: str = None) -> list[dict]:
        """Get cost history with optional filters."""
        sql = "SELECT * FROM cost_history WHERE 1=1"
        params = []

        if since:
            sql += " AND started_at >= ?"
            params.append(since)
        if workflow:
            sql += " AND workflow = ?"
            params.append(workflow)

        sql += " ORDER BY started_at DESC"
        rows = self.db.fetchall(sql, tuple(params))
        for row in rows:
            row['agents'] = self.db.from_json(row.get('agents_json'), {})
        return rows

    def get_total_cost(self, since: str = None) -> float:
        """Get total cost since a given date."""
        sql = "SELECT SUM(estimated_cost) as total FROM cost_history"
        params = []
        if since:
            sql += " WHERE started_at >= ?"
            params.append(since)

        row = self.db.fetchone(sql, tuple(params))
        return row['total'] if row and row['total'] else 0.0
