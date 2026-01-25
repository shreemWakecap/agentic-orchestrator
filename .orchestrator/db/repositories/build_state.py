"""
Build State Repository - ORM-based implementation.

Handles build state and step state database operations using SQLAlchemy ORM.

SOLID Revamp:
- Implements IBuildStateRepository interface
- Accepts optional project_id for future scoping needs
- BuildState is linked to Plan which is already project-scoped
"""
import json
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from ..connection import Database

from ..models import BuildState, StepState, GoalVerificationState
from .interfaces import IBuildStateRepository


class BuildStateRepository(IBuildStateRepository):
    """Repository for build state operations using ORM.

    Implements IBuildStateRepository interface for dependency injection.

    Note: BuildState is linked to Plan via plan_id, and Plan is already
    project-scoped, so build states are transitively project-scoped.

    Args:
        db: Database connection instance
        project_id: Optional project ID (for consistency with other repos)
    """

    def __init__(self, db: "Database", project_id: Optional[str] = None):
        self.db = db
        self._project_id = project_id  # Reserved for future use

    def create(self, plan_id: str, total_steps: int = 0) -> int:
        """Create build state for a plan."""
        with self.db.session() as session:
            build_state = BuildState(
                plan_id=plan_id,
                status='pending',
                total_steps=total_steps,
                started_at=datetime.now(),
                updated_at=datetime.now(),
                completed_steps_json='[]',
                failed_steps_json='[]',
                skipped_steps_json='[]',
                files_created_json='[]',
                files_modified_json='[]'
            )
            session.add(build_state)
            session.flush()
            return build_state.id

    def get(self, plan_id: str) -> Optional[dict]:
        """Get build state for a plan."""
        with self.db.session() as session:
            bs = session.query(BuildState).filter_by(plan_id=plan_id).first()
            if not bs:
                return None

            return self._build_state_to_dict(bs)

    def update(self, plan_id: str, **kwargs):
        """Update build state fields."""
        if not kwargs:
            return

        with self.db.session() as session:
            bs = session.query(BuildState).filter_by(plan_id=plan_id).first()
            if not bs:
                return

            bs.updated_at = datetime.now()

            # Handle JSON fields
            json_field_mapping = {
                'completed_steps': 'completed_steps_json',
                'failed_steps': 'failed_steps_json',
                'skipped_steps': 'skipped_steps_json',
                'files_created': 'files_created_json',
                'files_modified': 'files_modified_json',
            }

            for key, value in kwargs.items():
                if key in json_field_mapping:
                    setattr(bs, json_field_mapping[key], json.dumps(value))
                elif hasattr(bs, key):
                    setattr(bs, key, value)

    def set_step_state(self, plan_id: str, step_id: str, status: str,
                       started_at: str = None, completed_at: str = None,
                       retry_count: int = 0, error: str = None,
                       files_affected: list[str] = None, summary: str = None):
        """Create or update step state."""
        with self.db.session() as session:
            existing = session.query(StepState).filter_by(plan_id=plan_id, step_id=step_id).first()

            if existing:
                existing.status = status
                if started_at:
                    existing.started_at = datetime.fromisoformat(started_at) if isinstance(started_at, str) else started_at
                if completed_at:
                    existing.completed_at = datetime.fromisoformat(completed_at) if isinstance(completed_at, str) else completed_at
                existing.retry_count = retry_count
                existing.error = error
                existing.files_affected_json = json.dumps(files_affected or [])
                existing.summary = summary
            else:
                step_state = StepState(
                    plan_id=plan_id,
                    step_id=step_id,
                    status=status,
                    started_at=datetime.fromisoformat(started_at) if started_at else None,
                    completed_at=datetime.fromisoformat(completed_at) if completed_at else None,
                    retry_count=retry_count,
                    error=error,
                    files_affected_json=json.dumps(files_affected or []),
                    summary=summary
                )
                session.add(step_state)

    def get_step_states(self, plan_id: str) -> List[dict]:
        """Get all step states for a plan."""
        with self.db.session() as session:
            states = session.query(StepState).filter_by(plan_id=plan_id).all()
            return [self._step_state_to_dict(s) for s in states]

    def get_step_state(self, plan_id: str, step_id: str) -> Optional[dict]:
        """Get step state for a specific step."""
        with self.db.session() as session:
            state = session.query(StepState).filter_by(plan_id=plan_id, step_id=step_id).first()
            if not state:
                return None
            return self._step_state_to_dict(state)

    def exists(self, plan_id: str) -> bool:
        """Check if build state exists for a plan."""
        with self.db.session() as session:
            return session.query(BuildState).filter_by(plan_id=plan_id).count() > 0

    def clear(self, plan_id: str) -> bool:
        """Clear all build state and step states for a plan."""
        with self.db.session() as session:
            session.query(StepState).filter_by(plan_id=plan_id).delete()
            deleted = session.query(BuildState).filter_by(plan_id=plan_id).delete()
            return deleted > 0

    def cancel(self, plan_id: str) -> bool:
        """Cancel a build by setting status to 'cancelled'."""
        with self.db.session() as session:
            bs = session.query(BuildState).filter_by(plan_id=plan_id).first()
            if not bs:
                return False
            bs.status = 'cancelled'
            bs.updated_at = datetime.now()
            return True

    def pause(self, plan_id: str) -> bool:
        """Pause a build by setting status to 'paused'."""
        with self.db.session() as session:
            bs = session.query(BuildState).filter_by(plan_id=plan_id).first()
            if not bs:
                return False
            bs.status = 'paused'
            bs.updated_at = datetime.now()
            return True

    def update_status(self, plan_id: str, status: str) -> bool:
        """Update build state status."""
        self.update(plan_id, status=status)
        return True

    # =====================================================
    # GOAL CONTEXT PERSISTENCE
    # =====================================================

    def save_goal_context(self, plan_id: str, goal_context: dict) -> None:
        """Save or update goal verification state."""
        with self.db.session() as session:
            existing = session.query(GoalVerificationState).filter_by(plan_id=plan_id).first()

            if existing:
                existing.goal = goal_context.get('goal', '')
                existing.original_request = goal_context.get('original_request', '')
                existing.verification_attempt = goal_context.get('verification_attempts', 0)
                existing.missing_items_json = json.dumps(goal_context.get('missing_items', []))
                existing.completion_percentage = goal_context.get('completion_percentage', 0)
                existing.goal_achieved = goal_context.get('goal_achieved', False)
                existing.context_notes_json = json.dumps(goal_context.get('context_notes', []))
                existing.verify_commands_json = json.dumps(goal_context.get('verify_commands', []))
                existing.updated_at = datetime.now()
            else:
                state = GoalVerificationState(
                    plan_id=plan_id,
                    goal=goal_context.get('goal', ''),
                    original_request=goal_context.get('original_request', ''),
                    verification_attempt=goal_context.get('verification_attempts', 0),
                    missing_items_json=json.dumps(goal_context.get('missing_items', [])),
                    completion_percentage=goal_context.get('completion_percentage', 0),
                    goal_achieved=goal_context.get('goal_achieved', False),
                    context_notes_json=json.dumps(goal_context.get('context_notes', [])),
                    verify_commands_json=json.dumps(goal_context.get('verify_commands', [])),
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                session.add(state)

    def get_goal_context(self, plan_id: str) -> Optional[dict]:
        """Load goal verification state."""
        with self.db.session() as session:
            state = session.query(GoalVerificationState).filter_by(plan_id=plan_id).first()
            if not state:
                return None

            return {
                'goal': state.goal or '',
                'original_request': state.original_request or '',
                'verification_attempts': state.verification_attempt or 0,
                'missing_items': json.loads(state.missing_items_json or '[]'),
                'completion_percentage': state.completion_percentage or 0,
                'goal_achieved': bool(state.goal_achieved),
                'context_notes': json.loads(state.context_notes_json or '[]'),
                'verify_commands': json.loads(state.verify_commands_json or '[]'),
            }

    def clear_goal_context(self, plan_id: str) -> bool:
        """Clear goal verification state for a plan."""
        with self.db.session() as session:
            deleted = session.query(GoalVerificationState).filter_by(plan_id=plan_id).delete()
            return deleted > 0

    # =====================================================
    # RETRY HISTORY TRACKING
    # =====================================================

    def add_step_retry_history(self, plan_id: str, step_id: str, error: str, duration_ms: int) -> None:
        """Append to step retry history."""
        with self.db.session() as session:
            state = session.query(StepState).filter_by(plan_id=plan_id, step_id=step_id).first()
            if not state:
                return

            history = json.loads(state.retry_history_json or '[]')
            history.append({
                'timestamp': datetime.now().isoformat(),
                'error': error,
                'duration_ms': duration_ms
            })
            state.retry_history_json = json.dumps(history)

    def get_step_retry_history(self, plan_id: str, step_id: str) -> List[dict]:
        """Get retry history for a step."""
        with self.db.session() as session:
            state = session.query(StepState).filter_by(plan_id=plan_id, step_id=step_id).first()
            if not state:
                return []
            return json.loads(state.retry_history_json or '[]')

    # =====================================================
    # FULL OUTPUT STORAGE
    # =====================================================

    def save_step_full_output(self, plan_id: str, step_id: str, output: str) -> None:
        """Save full step output (up to 5000 chars)."""
        with self.db.session() as session:
            state = session.query(StepState).filter_by(plan_id=plan_id, step_id=step_id).first()
            if state:
                state.full_output = output[:5000] if len(output) > 5000 else output

    def get_step_full_output(self, plan_id: str, step_id: str) -> Optional[str]:
        """Get full step output."""
        with self.db.session() as session:
            state = session.query(StepState).filter_by(plan_id=plan_id, step_id=step_id).first()
            return state.full_output if state else None

    # =====================================================
    # BATCH OPERATIONS
    # =====================================================

    def batch_update_step_states(self, plan_id: str, step_updates: List[dict]) -> None:
        """Atomically update multiple step states in one transaction."""
        with self.db.session() as session:
            for update in step_updates:
                step_id = update.get('step_id')
                if not step_id:
                    continue

                existing = session.query(StepState).filter_by(plan_id=plan_id, step_id=step_id).first()

                if existing:
                    existing.status = update.get('status', existing.status)
                    if update.get('started_at'):
                        existing.started_at = datetime.fromisoformat(update['started_at']) if isinstance(update['started_at'], str) else update['started_at']
                    if update.get('completed_at'):
                        existing.completed_at = datetime.fromisoformat(update['completed_at']) if isinstance(update['completed_at'], str) else update['completed_at']
                    existing.retry_count = update.get('retry_count', existing.retry_count)
                    existing.error = update.get('error', existing.error)
                    if 'files_affected' in update:
                        existing.files_affected_json = json.dumps(update['files_affected'])
                    existing.summary = update.get('summary', existing.summary)
                else:
                    state = StepState(
                        plan_id=plan_id,
                        step_id=step_id,
                        status=update.get('status', 'pending'),
                        started_at=datetime.fromisoformat(update['started_at']) if update.get('started_at') else None,
                        completed_at=datetime.fromisoformat(update['completed_at']) if update.get('completed_at') else None,
                        retry_count=update.get('retry_count', 0),
                        error=update.get('error'),
                        files_affected_json=json.dumps(update.get('files_affected', [])),
                        summary=update.get('summary')
                    )
                    session.add(state)

    # =====================================================
    # EXECUTION MODE TRACKING
    # =====================================================

    def update_execution_mode(self, plan_id: str, mode: str, wave_index: int = 0) -> None:
        """Update execution mode and wave index."""
        self.update(plan_id, execution_mode=mode, current_wave_index=wave_index)

    # =====================================================
    # HELPER METHODS
    # =====================================================

    def _build_state_to_dict(self, bs: BuildState) -> dict:
        """Convert BuildState model to dictionary."""
        return {
            'id': bs.id,
            'plan_id': bs.plan_id,
            'status': bs.status,
            'current_step': bs.current_step,
            'current_phase': bs.current_phase,
            'total_steps': bs.total_steps,
            'last_error': bs.last_error,
            'execution_mode': bs.execution_mode,
            'current_wave_index': bs.current_wave_index,
            'completed_steps': json.loads(bs.completed_steps_json or '[]'),
            'failed_steps': json.loads(bs.failed_steps_json or '[]'),
            'skipped_steps': json.loads(bs.skipped_steps_json or '[]'),
            'files_created': json.loads(bs.files_created_json or '[]'),
            'files_modified': json.loads(bs.files_modified_json or '[]'),
            'started_at': bs.started_at.isoformat() if bs.started_at else None,
            'updated_at': bs.updated_at.isoformat() if bs.updated_at else None,
            'completed_at': bs.completed_at.isoformat() if bs.completed_at else None,
        }

    def _step_state_to_dict(self, ss: StepState) -> dict:
        """Convert StepState model to dictionary."""
        return {
            'id': ss.id,
            'plan_id': ss.plan_id,
            'step_id': ss.step_id,
            'status': ss.status,
            'started_at': ss.started_at.isoformat() if ss.started_at else None,
            'completed_at': ss.completed_at.isoformat() if ss.completed_at else None,
            'retry_count': ss.retry_count,
            'error': ss.error,
            'files_affected': json.loads(ss.files_affected_json or '[]'),
            'summary': ss.summary,
            'full_output': ss.full_output,
            'retry_history_json': ss.retry_history_json,
        }
