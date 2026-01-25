"""
Plan Repository - ORM-based implementation.

Handles all plan-related database operations using SQLAlchemy ORM.
All operations are scoped to the current active project.

SOLID Revamp:
- Implements IPlanRepository interface
- Accepts optional project_id for dependency injection
- Falls back to contextvar if project_id not provided
"""
import json
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from ..connection import Database

from ..models import Plan, PlanPhase, PlanStep
from .base import get_current_project_id
from .interfaces import IPlanRepository


class PlanRepository(IPlanRepository):
    """Repository for plan operations using ORM.

    Implements IPlanRepository interface for dependency injection.
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

    def create(self, plan_id: str, goal: str, request: str, raw_content: str,
               context: list[str] = None, verify: list[str] = None) -> int:
        """Create a new plan. Returns the row ID."""
        project_id = self.project_id

        with self.db.session() as session:
            plan = Plan(
                plan_id=plan_id,
                goal=goal,
                request=request,
                raw_content=raw_content,
                context_json=json.dumps(context or []),
                verify_json=json.dumps(verify or []),
                created_at=datetime.now(),
                updated_at=datetime.now(),
                project_id=project_id
            )
            session.add(plan)
            session.flush()
            return plan.id

    def get_by_id(self, plan_id: str) -> Optional[dict]:
        """Get plan by plan_id (scoped to current project)."""
        project_id = self.project_id

        with self.db.session() as session:
            query = session.query(Plan).filter_by(plan_id=plan_id)
            if project_id:
                query = query.filter_by(project_id=project_id)
            plan = query.first()
            if not plan:
                return None

            return self._plan_to_dict(plan)

    def list_by_status(self, status: str) -> List[dict]:
        """List plans by status (scoped to current project)."""
        project_id = self.project_id

        with self.db.session() as session:
            query = session.query(Plan).filter_by(status=status)
            if project_id:
                query = query.filter_by(project_id=project_id)
            plans = query.order_by(Plan.created_at.desc()).all()
            return [self._plan_to_dict(p) for p in plans]

    def list_all(self) -> List[dict]:
        """List all plans ordered by creation (scoped to current project)."""
        project_id = self.project_id

        with self.db.session() as session:
            query = session.query(Plan)
            if project_id:
                query = query.filter_by(project_id=project_id)
            plans = query.order_by(Plan.created_at.desc()).all()
            return [self._plan_to_dict(p) for p in plans]

    def update_status(self, plan_id: str, status: str):
        """Update plan status (scoped to current project)."""
        project_id = self.project_id

        with self.db.session() as session:
            query = session.query(Plan).filter_by(plan_id=plan_id)
            if project_id:
                query = query.filter_by(project_id=project_id)
            plan = query.first()
            if plan:
                plan.status = status
                plan.updated_at = datetime.now()
                if status == 'completed':
                    plan.completed_at = datetime.now()

    def update_content(self, plan_id: str, goal: str, request: str, raw_content: str):
        """Update plan content (scoped to current project)."""
        project_id = self.project_id

        with self.db.session() as session:
            query = session.query(Plan).filter_by(plan_id=plan_id)
            if project_id:
                query = query.filter_by(project_id=project_id)
            plan = query.first()
            if plan:
                plan.goal = goal
                plan.request = request
                plan.raw_content = raw_content
                plan.updated_at = datetime.now()

    def delete(self, plan_id: str):
        """Delete a plan (scoped to current project)."""
        project_id = self.project_id

        with self.db.session() as session:
            query = session.query(Plan).filter_by(plan_id=plan_id)
            if project_id:
                query = query.filter_by(project_id=project_id)
            query.delete()

    def add_phase(self, plan_id: str, phase_id: str, name: str,
                  phase_number: int, can_parallelize: bool = False):
        """Add a phase to a plan."""
        with self.db.session() as session:
            phase = PlanPhase(
                plan_id=plan_id,
                phase_id=phase_id,
                name=name,
                phase_number=phase_number,
                can_parallelize=can_parallelize
            )
            session.add(phase)

    def add_step(self, plan_id: str, phase_id: str, step_id: str, action: str,
                 description: str, step_order: int, target: str = None,
                 done: str = None, inputs: list[str] = None, needs: list[str] = None):
        """Add a step to a plan."""
        with self.db.session() as session:
            step = PlanStep(
                plan_id=plan_id,
                phase_id=phase_id,
                step_id=step_id,
                action=action,
                target=target,
                description=description,
                done=done,
                inputs_json=json.dumps(inputs or []),
                needs_json=json.dumps(needs or []),
                step_order=step_order
            )
            session.add(step)

    def get_steps(self, plan_id: str) -> List[dict]:
        """Get all steps for a plan."""
        with self.db.session() as session:
            steps = session.query(PlanStep).filter_by(plan_id=plan_id).order_by(PlanStep.step_order).all()
            return [{
                'id': s.id,
                'plan_id': s.plan_id,
                'phase_id': s.phase_id,
                'step_id': s.step_id,
                'action': s.action,
                'target': s.target,
                'description': s.description,
                'done': s.done,
                'inputs': json.loads(s.inputs_json or '[]'),
                'needs': json.loads(s.needs_json or '[]'),
                'step_order': s.step_order,
            } for s in steps]

    def get_phases(self, plan_id: str) -> List[dict]:
        """Get all phases for a plan."""
        with self.db.session() as session:
            phases = session.query(PlanPhase).filter_by(plan_id=plan_id).order_by(PlanPhase.phase_number).all()
            return [{
                'id': p.id,
                'plan_id': p.plan_id,
                'phase_id': p.phase_id,
                'name': p.name,
                'phase_number': p.phase_number,
                'can_parallelize': p.can_parallelize,
            } for p in phases]

    def get_next_plan_number(self) -> int:
        """Get the next plan number for ID generation (scoped to current project)."""
        project_id = self.project_id

        with self.db.session() as session:
            from sqlalchemy import func
            query = session.query(func.max(Plan.id))
            if project_id:
                query = query.filter(Plan.project_id == project_id)
            result = query.scalar()
            return (result or 0) + 1

    def exists(self, plan_id: str) -> bool:
        """Check if a plan exists (scoped to current project)."""
        project_id = self.project_id

        with self.db.session() as session:
            query = session.query(Plan).filter_by(plan_id=plan_id)
            if project_id:
                query = query.filter_by(project_id=project_id)
            return query.count() > 0

    def _plan_to_dict(self, plan: Plan) -> dict:
        """Convert Plan model to dictionary."""
        return {
            'id': plan.id,
            'plan_id': plan.plan_id,
            'goal': plan.goal,
            'request': plan.request,
            'raw_content': plan.raw_content,
            'context': json.loads(plan.context_json or '[]'),
            'verify': json.loads(plan.verify_json or '[]'),
            'status': plan.status,
            'created_at': plan.created_at.isoformat() if plan.created_at else None,
            'updated_at': plan.updated_at.isoformat() if plan.updated_at else None,
            'completed_at': plan.completed_at.isoformat() if plan.completed_at else None,
        }
