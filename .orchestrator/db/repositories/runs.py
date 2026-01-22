"""
Run Repository - ORM-based implementation.

Handles active run tracking and events using SQLAlchemy ORM.
"""
import json
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from ..connection import Database

from ..models import ActiveRun, RunEvent


class RunRepository:
    """Repository for active run tracking using ORM."""

    def __init__(self, db: "Database"):
        self.db = db

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
                triggered_by=triggered_by
            )
            session.add(run)
            session.flush()
            return run.id

    def get(self, run_id: str) -> Optional[dict]:
        """Get run by ID."""
        with self.db.session() as session:
            run = session.query(ActiveRun).filter_by(run_id=run_id).first()
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
        """List active runs with optional status filter."""
        with self.db.session() as session:
            query = session.query(ActiveRun)
            if status:
                query = query.filter_by(status=status)
            runs = query.order_by(ActiveRun.started_at.desc()).all()
            return [self._run_to_dict(r) for r in runs]

    def delete(self, run_id: str):
        """Delete a run and its events."""
        with self.db.session() as session:
            session.query(ActiveRun).filter_by(run_id=run_id).delete()

    def _run_to_dict(self, run: ActiveRun) -> dict:
        """Convert ActiveRun model to dictionary."""
        return {
            'id': run.id,
            'run_id': run.run_id,
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
