"""
Plan Repository - ORM-based implementation.

Handles all plan-related database operations using SQLAlchemy ORM.
"""
import json
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from ..connection import Database

from ..models import Plan, PlanPhase, PlanStep


class PlanRepository:
    """Repository for plan operations using ORM."""

    def __init__(self, db: "Database"):
        self.db = db

    def create(self, plan_id: str, goal: str, request: str, raw_content: str,
               context: list[str] = None, verify: list[str] = None) -> int:
        """Create a new plan. Returns the row ID."""
        with self.db.session() as session:
            plan = Plan(
                plan_id=plan_id,
                goal=goal,
                request=request,
                raw_content=raw_content,
                context_json=json.dumps(context or []),
                verify_json=json.dumps(verify or []),
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            session.add(plan)
            session.flush()
            return plan.id

    def get_by_id(self, plan_id: str) -> Optional[dict]:
        """Get plan by plan_id."""
        with self.db.session() as session:
            plan = session.query(Plan).filter_by(plan_id=plan_id).first()
            if not plan:
                return None

            return self._plan_to_dict(plan)

    def list_by_status(self, status: str) -> List[dict]:
        """List plans by status."""
        with self.db.session() as session:
            plans = session.query(Plan).filter_by(status=status).order_by(Plan.created_at.desc()).all()
            return [self._plan_to_dict(p) for p in plans]

    def list_all(self) -> List[dict]:
        """List all plans ordered by creation."""
        with self.db.session() as session:
            plans = session.query(Plan).order_by(Plan.created_at.desc()).all()
            return [self._plan_to_dict(p) for p in plans]

    def update_status(self, plan_id: str, status: str):
        """Update plan status."""
        with self.db.session() as session:
            plan = session.query(Plan).filter_by(plan_id=plan_id).first()
            if plan:
                plan.status = status
                plan.updated_at = datetime.now()
                if status == 'completed':
                    plan.completed_at = datetime.now()

    def update_content(self, plan_id: str, goal: str, request: str, raw_content: str):
        """Update plan content (goal, request, raw_content)."""
        with self.db.session() as session:
            plan = session.query(Plan).filter_by(plan_id=plan_id).first()
            if plan:
                plan.goal = goal
                plan.request = request
                plan.raw_content = raw_content
                plan.updated_at = datetime.now()

    def delete(self, plan_id: str):
        """Delete a plan (cascades to steps, phases, build state)."""
        with self.db.session() as session:
            session.query(Plan).filter_by(plan_id=plan_id).delete()

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
        """Get the next plan number for ID generation."""
        with self.db.session() as session:
            from sqlalchemy import func
            result = session.query(func.max(Plan.id)).scalar()
            return (result or 0) + 1

    def exists(self, plan_id: str) -> bool:
        """Check if a plan exists."""
        with self.db.session() as session:
            return session.query(Plan).filter_by(plan_id=plan_id).count() > 0

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
