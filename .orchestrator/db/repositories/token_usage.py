"""
Token Usage Repository.

Handles token usage tracking and analytics operations.
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..connection import Database


class TokenUsageRepository:
    """Repository for token usage tracking operations."""

    def __init__(self, db: "Database"):
        self.db = db

    def record_usage(
        self,
        workflow_type: str,
        event_type: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        model: str = None,
        cost_usd: float = 0.0,
        run_id: str = None,
        plan_id: str = None,
        estimated_tokens: int = None,
        estimated_cost_usd: float = None,
        metadata: dict = None
    ):
        """Record a token usage event.

        Args:
            workflow_type: Type of workflow (scout, build, plan, etc.)
            event_type: Type of event (execution, estimation)
            input_tokens: Number of input tokens consumed
            output_tokens: Number of output tokens consumed
            model: Model identifier used
            cost_usd: Actual cost in USD
            run_id: Associated run ID (optional)
            plan_id: Associated plan ID (optional)
            estimated_tokens: Predicted token count for estimation events
            estimated_cost_usd: Predicted cost for estimation events
            metadata: Additional metadata as dict
        """
        with self.db.transaction() as conn:
            conn.execute("""
                INSERT INTO token_usage_records
                (run_id, plan_id, workflow_type, event_type, input_tokens, output_tokens,
                 model, cost_usd, estimated_tokens, estimated_cost_usd, timestamp, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id, plan_id, workflow_type, event_type,
                input_tokens, output_tokens, model, cost_usd,
                estimated_tokens, estimated_cost_usd,
                datetime.utcnow().isoformat(),
                self.db.to_json(metadata or {})
            ))

    def get_usage_by_run(self, run_id: str) -> list[dict]:
        """Get all token usage records for a specific run.

        Args:
            run_id: The run identifier

        Returns:
            List of token usage records for the run
        """
        sql = """
            SELECT * FROM token_usage_records
            WHERE run_id = ?
            ORDER BY timestamp DESC
        """
        rows = self.db.fetchall(sql, (run_id,))
        for row in rows:
            row['metadata'] = self.db.from_json(row.get('metadata_json'), {})
        return rows

    def get_usage_by_plan(self, plan_id: str) -> list[dict]:
        """Get all token usage records for a specific plan.

        Args:
            plan_id: The plan identifier

        Returns:
            List of token usage records for the plan
        """
        sql = """
            SELECT * FROM token_usage_records
            WHERE plan_id = ?
            ORDER BY timestamp DESC
        """
        rows = self.db.fetchall(sql, (plan_id,))
        for row in rows:
            row['metadata'] = self.db.from_json(row.get('metadata_json'), {})
        return rows

    def get_usage_by_date_range(
        self,
        start_date: str,
        end_date: str = None,
        workflow_type: str = None,
        event_type: str = None
    ) -> list[dict]:
        """Get token usage records within a date range.

        Args:
            start_date: Start date (ISO format)
            end_date: End date (ISO format), defaults to now
            workflow_type: Filter by workflow type (optional)
            event_type: Filter by event type (optional)

        Returns:
            List of token usage records in the date range
        """
        sql = "SELECT * FROM token_usage_records WHERE timestamp >= ?"
        params = [start_date]

        if end_date:
            sql += " AND timestamp <= ?"
            params.append(end_date)

        if workflow_type:
            sql += " AND workflow_type = ?"
            params.append(workflow_type)

        if event_type:
            sql += " AND event_type = ?"
            params.append(event_type)

        sql += " ORDER BY timestamp DESC"
        rows = self.db.fetchall(sql, tuple(params))
        for row in rows:
            row['metadata'] = self.db.from_json(row.get('metadata_json'), {})
        return rows

    def get_aggregated_stats(
        self,
        start_date: str = None,
        end_date: str = None,
        group_by: str = "workflow_type"
    ) -> dict:
        """Get aggregated token usage statistics.

        Args:
            start_date: Start date filter (optional)
            end_date: End date filter (optional)
            group_by: Field to group by (workflow_type, event_type, model)

        Returns:
            Dictionary with aggregated statistics
        """
        # Build WHERE clause
        where_clauses = []
        params = []

        if start_date:
            where_clauses.append("timestamp >= ?")
            params.append(start_date)
        if end_date:
            where_clauses.append("timestamp <= ?")
            params.append(end_date)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # Total stats
        total_sql = f"""
            SELECT
                COUNT(*) as total_records,
                SUM(input_tokens) as total_input_tokens,
                SUM(output_tokens) as total_output_tokens,
                SUM(input_tokens + output_tokens) as total_tokens,
                SUM(cost_usd) as total_cost_usd,
                AVG(input_tokens + output_tokens) as avg_tokens_per_request
            FROM token_usage_records
            WHERE {where_sql}
        """
        total_row = self.db.fetchone(total_sql, tuple(params))

        # Grouped stats
        valid_group_by = {"workflow_type", "event_type", "model"}
        if group_by not in valid_group_by:
            group_by = "workflow_type"

        grouped_sql = f"""
            SELECT
                {group_by},
                COUNT(*) as record_count,
                SUM(input_tokens) as input_tokens,
                SUM(output_tokens) as output_tokens,
                SUM(input_tokens + output_tokens) as total_tokens,
                SUM(cost_usd) as cost_usd
            FROM token_usage_records
            WHERE {where_sql}
            GROUP BY {group_by}
            ORDER BY total_tokens DESC
        """
        grouped_rows = self.db.fetchall(grouped_sql, tuple(params))

        # Daily breakdown
        daily_sql = f"""
            SELECT
                DATE(timestamp) as date,
                SUM(input_tokens) as input_tokens,
                SUM(output_tokens) as output_tokens,
                SUM(cost_usd) as cost_usd,
                COUNT(*) as request_count
            FROM token_usage_records
            WHERE {where_sql}
            GROUP BY DATE(timestamp)
            ORDER BY date DESC
            LIMIT 30
        """
        daily_rows = self.db.fetchall(daily_sql, tuple(params))

        return {
            "totals": {
                "total_records": total_row.get("total_records", 0) if total_row else 0,
                "total_input_tokens": total_row.get("total_input_tokens", 0) if total_row else 0,
                "total_output_tokens": total_row.get("total_output_tokens", 0) if total_row else 0,
                "total_tokens": total_row.get("total_tokens", 0) if total_row else 0,
                "total_cost_usd": total_row.get("total_cost_usd", 0.0) if total_row else 0.0,
                "avg_tokens_per_request": total_row.get("avg_tokens_per_request", 0) if total_row else 0
            },
            "by_group": grouped_rows,
            "daily_breakdown": daily_rows
        }

    def get_estimated_vs_actual(
        self,
        plan_id: str = None,
        start_date: str = None,
        end_date: str = None
    ) -> list[dict]:
        """Get comparison of estimated vs actual token usage.

        Args:
            plan_id: Filter by specific plan (optional)
            start_date: Start date filter (optional)
            end_date: End date filter (optional)

        Returns:
            List of comparison records with variance calculations
        """
        # Get estimation records
        where_clauses = ["event_type = 'estimation'"]
        params = []

        if plan_id:
            where_clauses.append("plan_id = ?")
            params.append(plan_id)
        if start_date:
            where_clauses.append("timestamp >= ?")
            params.append(start_date)
        if end_date:
            where_clauses.append("timestamp <= ?")
            params.append(end_date)

        where_sql = " AND ".join(where_clauses)

        # Query for plans with both estimation and execution records
        sql = f"""
            SELECT
                e.plan_id,
                e.workflow_type,
                e.estimated_tokens,
                e.estimated_cost_usd,
                e.timestamp as estimated_at,
                a.actual_tokens,
                a.actual_cost_usd,
                a.execution_count
            FROM (
                SELECT
                    plan_id,
                    workflow_type,
                    SUM(estimated_tokens) as estimated_tokens,
                    SUM(estimated_cost_usd) as estimated_cost_usd,
                    MIN(timestamp) as timestamp
                FROM token_usage_records
                WHERE {where_sql} AND plan_id IS NOT NULL
                GROUP BY plan_id, workflow_type
            ) e
            LEFT JOIN (
                SELECT
                    plan_id,
                    workflow_type,
                    SUM(input_tokens + output_tokens) as actual_tokens,
                    SUM(cost_usd) as actual_cost_usd,
                    COUNT(*) as execution_count
                FROM token_usage_records
                WHERE event_type = 'execution' AND plan_id IS NOT NULL
                GROUP BY plan_id, workflow_type
            ) a ON e.plan_id = a.plan_id AND e.workflow_type = a.workflow_type
            ORDER BY e.timestamp DESC
        """
        rows = self.db.fetchall(sql, tuple(params))

        # Calculate variances
        results = []
        for row in rows:
            estimated = row.get('estimated_tokens') or 0
            actual = row.get('actual_tokens') or 0
            estimated_cost = row.get('estimated_cost_usd') or 0.0
            actual_cost = row.get('actual_cost_usd') or 0.0

            token_variance = actual - estimated if estimated > 0 else 0
            token_variance_pct = ((actual - estimated) / estimated * 100) if estimated > 0 else 0
            cost_variance = actual_cost - estimated_cost if estimated_cost > 0 else 0
            cost_variance_pct = ((actual_cost - estimated_cost) / estimated_cost * 100) if estimated_cost > 0 else 0

            results.append({
                "plan_id": row.get('plan_id'),
                "workflow_type": row.get('workflow_type'),
                "estimated_tokens": estimated,
                "actual_tokens": actual,
                "token_variance": token_variance,
                "token_variance_pct": round(token_variance_pct, 2),
                "estimated_cost_usd": estimated_cost,
                "actual_cost_usd": actual_cost,
                "cost_variance": round(cost_variance, 4),
                "cost_variance_pct": round(cost_variance_pct, 2),
                "execution_count": row.get('execution_count', 0),
                "estimated_at": row.get('estimated_at')
            })

        return results

    def get_error_rates(
        self,
        start_date: str = None,
        end_date: str = None,
        group_by: str = "workflow_type"
    ) -> dict:
        """Get error rate calculations based on token usage patterns.

        Args:
            start_date: Start date filter (optional)
            end_date: End date filter (optional)
            group_by: Field to group by (workflow_type, model)

        Returns:
            Dictionary with error rate statistics
        """
        # Build WHERE clause
        where_clauses = []
        params = []

        if start_date:
            where_clauses.append("t.timestamp >= ?")
            params.append(start_date)
        if end_date:
            where_clauses.append("t.timestamp <= ?")
            params.append(end_date)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # Validate group_by
        valid_group_by = {"workflow_type", "model"}
        if group_by not in valid_group_by:
            group_by = "workflow_type"

        # Get total runs and failed runs by linking to active_runs
        error_sql = f"""
            SELECT
                t.{group_by},
                COUNT(DISTINCT t.run_id) as total_runs,
                COUNT(DISTINCT CASE WHEN r.status = 'failed' THEN t.run_id END) as failed_runs,
                SUM(t.input_tokens + t.output_tokens) as total_tokens,
                SUM(CASE WHEN r.status = 'failed' THEN t.input_tokens + t.output_tokens ELSE 0 END) as failed_tokens
            FROM token_usage_records t
            LEFT JOIN active_runs r ON t.run_id = r.run_id
            WHERE {where_sql} AND t.run_id IS NOT NULL
            GROUP BY t.{group_by}
        """
        grouped_rows = self.db.fetchall(error_sql, tuple(params))

        # Calculate error rates
        results = []
        total_runs = 0
        total_failed = 0

        for row in grouped_rows:
            runs = row.get('total_runs', 0) or 0
            failed = row.get('failed_runs', 0) or 0
            tokens = row.get('total_tokens', 0) or 0
            failed_tokens = row.get('failed_tokens', 0) or 0

            total_runs += runs
            total_failed += failed

            error_rate = (failed / runs * 100) if runs > 0 else 0
            token_waste_rate = (failed_tokens / tokens * 100) if tokens > 0 else 0

            results.append({
                group_by: row.get(group_by),
                "total_runs": runs,
                "failed_runs": failed,
                "error_rate_pct": round(error_rate, 2),
                "total_tokens": tokens,
                "failed_tokens": failed_tokens,
                "token_waste_rate_pct": round(token_waste_rate, 2)
            })

        overall_error_rate = (total_failed / total_runs * 100) if total_runs > 0 else 0

        return {
            "overall": {
                "total_runs": total_runs,
                "failed_runs": total_failed,
                "error_rate_pct": round(overall_error_rate, 2)
            },
            "by_group": results
        }
