"""
Run Repository - ORM-based implementation.

Handles active run tracking and events using SQLAlchemy ORM.
All operations are scoped to the current active project.

SOLID Revamp:
- Implements IRunRepository interface
- Accepts optional project_id for dependency injection
- Falls back to contextvar if project_id not provided
"""
import json
from datetime import datetime, timedelta
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from ..connection import Database

from ..models import ActiveRun, RunEvent
from .base import get_current_project_id
from .interfaces import IRunRepository


class RunRepository(IRunRepository):
    """Repository for active run tracking using ORM.

    Implements IRunRepository interface for dependency injection.
    All operations are scoped to the current active project.

    Args:
        db: Database connection instance
        project_id: Optional project ID for explicit scoping.
                   If not provided, falls back to contextvar.
    """

    def __init__(self, db: "Database", project_id: Optional[str] = None):
        self.db = db
        self._project_id = project_id

    @property
    def project_id(self) -> Optional[str]:
        """Get the project ID for this repository.

        Returns injected project_id if available, otherwise
        falls back to the contextvar.
        """
        if self._project_id:
            return self._project_id
        return get_current_project_id()

    def create(self, run_id: str, workflow: str, description: str = None,
               plan_id: str = None, plan_path: str = None,
               triggered_by: str = "manual") -> int:
        """Create a new run.

        Args:
            run_id: Unique run identifier
            workflow: Workflow type (planning, building, scouting, etc.)
            description: Optional description of the run
            plan_id: Associated plan ID (optional)
            plan_path: Path to plan file (optional)
            triggered_by: How this run was triggered (manual, system, auto_pre_planning, post_build)
        """
        project_id = self.project_id

        with self.db.session() as session:
            run = ActiveRun(
                run_id=run_id,
                workflow=workflow,
                status='pending',
                started_at=datetime.now(),
                plan_id=plan_id,
                plan_path=plan_path,
                description=description,
                progress=0,
                data_json='{}',
                triggered_by=triggered_by,
                project_id=project_id
            )
            session.add(run)
            session.flush()
            return run.id

    def get(self, run_id: str) -> Optional[dict]:
        """Get run by ID (scoped to current project)."""
        project_id = self.project_id

        with self.db.session() as session:
            query = session.query(ActiveRun).filter_by(run_id=run_id)
            if project_id:
                query = query.filter_by(project_id=project_id)
            run = query.first()
            if not run:
                return None
            return self._run_to_dict(run)

    def update(self, run_id: str, **kwargs):
        """Update run fields."""
        with self.db.session() as session:
            run = session.query(ActiveRun).filter_by(run_id=run_id).first()
            if not run:
                return

            # Handle 'data' field specially
            if 'data' in kwargs:
                kwargs['data_json'] = json.dumps(kwargs.pop('data'))

            for key, value in kwargs.items():
                if hasattr(run, key):
                    setattr(run, key, value)

    def add_event(self, run_id: str, event_type: str, data: dict = None):
        """Add event to run."""
        with self.db.session() as session:
            event = RunEvent(
                run_id=run_id,
                event_type=event_type,
                timestamp=datetime.now(),
                data_json=json.dumps(data or {})
            )
            session.add(event)

    def get_events(self, run_id: str, since_id: int = 0) -> List[dict]:
        """Get events for a run since a given ID."""
        with self.db.session() as session:
            events = session.query(RunEvent).filter(
                RunEvent.run_id == run_id,
                RunEvent.id > since_id
            ).order_by(RunEvent.timestamp).all()

            return [{
                'id': e.id,
                'run_id': e.run_id,
                'event_type': e.event_type,
                'timestamp': e.timestamp.isoformat() if e.timestamp else None,
                'data': json.loads(e.data_json or '{}'),
            } for e in events]

    def list_active(self, status: str = None) -> List[dict]:
        """List active runs with optional status filter (scoped to current project)."""
        project_id = self.project_id

        with self.db.session() as session:
            query = session.query(ActiveRun)
            if project_id:
                query = query.filter_by(project_id=project_id)
            if status:
                query = query.filter_by(status=status)
            runs = query.order_by(ActiveRun.started_at.desc()).all()
            return [self._run_to_dict(r) for r in runs]

    def delete(self, run_id: str):
        """Delete a run and its events (scoped to current project)."""
        project_id = self.project_id

        with self.db.session() as session:
            query = session.query(ActiveRun).filter_by(run_id=run_id)
            if project_id:
                query = query.filter_by(project_id=project_id)
            query.delete()

    def list_by_project(
        self,
        project_id: str,
        status: str = None,
        workflow_type: str = None,
        limit: int = 50,
    ) -> List[dict]:
        """List runs for a specific project.

        Args:
            project_id: Project to filter by
            status: Optional status filter
            workflow_type: Optional workflow type filter
            limit: Maximum results

        Returns:
            List of run dicts
        """
        with self.db.session() as session:
            query = session.query(ActiveRun).filter(ActiveRun.project_id == project_id)

            if status:
                query = query.filter(ActiveRun.status == status)
            if workflow_type:
                query = query.filter(ActiveRun.workflow == workflow_type)

            query = query.order_by(ActiveRun.started_at.desc()).limit(limit)

            return [self._run_to_dict(run) for run in query.all()]

    def get_project_stats(self, project_id: str) -> dict:
        """Get run statistics for a project.

        Args:
            project_id: Project to get stats for

        Returns:
            Dict with counts by status and workflow type
        """
        with self.db.session() as session:
            runs = session.query(ActiveRun).filter(
                ActiveRun.project_id == project_id
            ).all()

            stats = {
                "total": len(runs),
                "by_status": {},
                "by_workflow": {},
            }

            for run in runs:
                # Count by status
                status = run.status or "unknown"
                stats["by_status"][status] = stats["by_status"].get(status, 0) + 1

                # Count by workflow type
                workflow = run.workflow or "unknown"
                stats["by_workflow"][workflow] = stats["by_workflow"].get(workflow, 0) + 1

            return stats

    def force_stop(self, run_id: str) -> bool:
        """Force stop a stuck run.

        Updates run status to 'force_stopped', sets completed_at timestamp,
        clears any pending events, and adds a force_stop event.

        Args:
            run_id: The run identifier to force stop

        Returns:
            True if run was found and updated, False otherwise
        """
        project_id = self.project_id

        with self.db.session() as session:
            query = session.query(ActiveRun).filter_by(run_id=run_id)
            if project_id:
                query = query.filter_by(project_id=project_id)
            run = query.first()

            if not run:
                return False

            # Update run status
            run.status = 'force_stopped'
            run.completed_at = datetime.now()
            run.error = 'Run was force stopped by user'

            # Delete any pending events for this run
            session.query(RunEvent).filter(
                RunEvent.run_id == run_id,
                RunEvent.event_type == 'pending'
            ).delete()

            # Add force_stop event
            force_stop_event = RunEvent(
                run_id=run_id,
                event_type='force_stop',
                timestamp=datetime.now(),
                data_json=json.dumps({
                    'reason': 'User initiated force stop',
                    'previous_status': run.status if run.status != 'force_stopped' else 'unknown'
                })
            )
            session.add(force_stop_event)

            return True

    def list_stuck(self, stale_minutes: int = 30) -> List[dict]:
        """Find runs stuck in running/pending status for longer than specified minutes.

        Args:
            stale_minutes: Number of minutes after which a run is considered stuck.
                          Defaults to 30 minutes.

        Returns:
            List of run dicts that are stuck
        """
        project_id = self.project_id
        cutoff_time = datetime.now() - timedelta(minutes=stale_minutes)

        with self.db.session() as session:
            query = session.query(ActiveRun).filter(
                ActiveRun.status.in_(['running', 'pending']),
                ActiveRun.started_at < cutoff_time
            )
            if project_id:
                query = query.filter_by(project_id=project_id)

            runs = query.order_by(ActiveRun.started_at.asc()).all()
            return [self._run_to_dict(r) for r in runs]

    def _run_to_dict(self, run: ActiveRun) -> dict:
        """Convert ActiveRun model to dictionary."""
        return {
            'id': run.id,
            'run_id': run.run_id,
            'project_id': run.project_id,
            'workflow': run.workflow,
            'status': run.status,
            'started_at': run.started_at.isoformat() if run.started_at else None,
            'completed_at': run.completed_at.isoformat() if run.completed_at else None,
            'plan_id': run.plan_id,
            'plan_path': run.plan_path,
            'description': run.description,
            'progress': run.progress,
            'error': run.error,
            'data': json.loads(run.data_json or '{}'),
            'triggered_by': run.triggered_by or 'manual',
        }
