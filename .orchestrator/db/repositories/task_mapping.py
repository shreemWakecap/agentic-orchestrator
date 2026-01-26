"""
TaskMapping Repository - CRUD operations for task-step mappings.

This repository manages the TaskMapping table which maps Claude's native
Task IDs to PlanStep IDs for session persistence and progress tracking.
"""
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import select

from ..models import TaskMapping
from .base import BaseRepository


class TaskMappingRepository(BaseRepository):
    """Repository for TaskMapping CRUD operations.

    This repository provides methods to manage the mapping between
    Claude's native Task tools and the orchestrator's plan steps.

    Key responsibilities:
    - Create mappings when plans are executed
    - Track session-specific task IDs
    - Sync task status from Claude back to database
    - Support resume by restoring task state
    """

    model = TaskMapping
    table_name = "task_mappings"

    # Fields that contain JSON data
    JSON_FIELDS = ["blocked_by", "blocks"]

    def __init__(self, db=None, project_id: Optional[str] = None):
        """Initialize the repository.

        Args:
            db: Database connection instance (optional)
            project_id: Optional project ID for scoping (not used for TaskMapping
                       as it's scoped by plan_id which is already project-scoped)
        """
        super().__init__(db)
        self._project_id = project_id

    def create(
        self,
        plan_id: str,
        step_id: str,
        task_subject: str,
        task_description: str = "",
        task_active_form: str = "",
        blocked_by: Optional[List[str]] = None,
        blocks: Optional[List[str]] = None,
        session_id: Optional[str] = None,
        session_task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new task mapping.

        Args:
            plan_id: The plan this task belongs to
            step_id: The step ID this task maps to
            task_subject: Task subject/title
            task_description: Full task description
            task_active_form: Present continuous form for spinner display
            blocked_by: List of step_ids this task depends on
            blocks: List of step_ids that depend on this task
            session_id: Claude session UUID
            session_task_id: Task ID within the Claude session

        Returns:
            Created task mapping as dictionary
        """
        with self.session() as session:
            mapping = TaskMapping(
                plan_id=plan_id,
                step_id=step_id,
                task_subject=task_subject,
                task_description=task_description,
                task_active_form=task_active_form,
                blocked_by_json=json.dumps(blocked_by or []),
                blocks_json=json.dumps(blocks or []),
                session_id=session_id,
                session_task_id=session_task_id,
                status="pending",
                created_at=datetime.utcnow(),
            )
            session.add(mapping)
            session.commit()
            session.refresh(mapping)
            return self._to_dict(mapping)

    def get_by_plan(self, plan_id: str) -> List[Dict[str, Any]]:
        """Get all task mappings for a plan.

        Args:
            plan_id: The plan ID to query

        Returns:
            List of task mappings ordered by id
        """
        with self.session() as session:
            stmt = select(TaskMapping).where(
                TaskMapping.plan_id == plan_id
            ).order_by(TaskMapping.id)
            result = session.execute(stmt)
            mappings = result.scalars().all()
            return [self._to_dict(m) for m in mappings]

    def get_by_step(self, plan_id: str, step_id: str) -> Optional[Dict[str, Any]]:
        """Get task mapping for a specific step.

        Args:
            plan_id: The plan ID
            step_id: The step ID

        Returns:
            Task mapping dict or None if not found
        """
        with self.session() as session:
            stmt = select(TaskMapping).where(
                TaskMapping.plan_id == plan_id,
                TaskMapping.step_id == step_id
            )
            result = session.execute(stmt)
            mapping = result.scalar_one_or_none()
            return self._to_dict(mapping) if mapping else None

    def get_by_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all task mappings for a Claude session.

        Args:
            session_id: The Claude session UUID

        Returns:
            List of task mappings for the session
        """
        with self.session() as session:
            stmt = select(TaskMapping).where(
                TaskMapping.session_id == session_id
            ).order_by(TaskMapping.id)
            result = session.execute(stmt)
            mappings = result.scalars().all()
            return [self._to_dict(m) for m in mappings]

    def update_session_info(
        self,
        plan_id: str,
        step_id: str,
        session_id: str,
        session_task_id: str
    ) -> bool:
        """Update session tracking info when Tasks are created.

        Called after Claude's TaskCreate returns a task ID.

        Args:
            plan_id: The plan ID
            step_id: The step ID
            session_id: Claude session UUID
            session_task_id: Task ID returned by TaskCreate

        Returns:
            True if updated, False if mapping not found
        """
        with self.session() as session:
            stmt = select(TaskMapping).where(
                TaskMapping.plan_id == plan_id,
                TaskMapping.step_id == step_id
            )
            result = session.execute(stmt)
            mapping = result.scalar_one_or_none()
            if mapping:
                mapping.session_id = session_id
                mapping.session_task_id = session_task_id
                session.commit()
                return True
            return False

    def update_status(
        self,
        plan_id: str,
        step_id: str,
        status: str,
        synced_at: Optional[datetime] = None
    ) -> bool:
        """Update task status (synced from Claude Tasks).

        Called during checkpoint sync to persist task state.

        Args:
            plan_id: The plan ID
            step_id: The step ID
            status: New status (pending/in_progress/completed)
            synced_at: Timestamp of sync (defaults to now)

        Returns:
            True if updated, False if mapping not found
        """
        with self.session() as session:
            stmt = select(TaskMapping).where(
                TaskMapping.plan_id == plan_id,
                TaskMapping.step_id == step_id
            )
            result = session.execute(stmt)
            mapping = result.scalar_one_or_none()
            if mapping:
                mapping.status = status
                mapping.synced_at = synced_at or datetime.utcnow()
                session.commit()
                return True
            return False

    def batch_update_status(
        self,
        plan_id: str,
        status_updates: List[Dict[str, str]]
    ) -> int:
        """Batch update statuses for multiple steps.

        Efficient bulk update for syncing multiple task states at once.

        Args:
            plan_id: The plan ID
            status_updates: List of {"step_id": str, "status": str} dicts

        Returns:
            Number of mappings updated
        """
        updated = 0
        with self.session() as session:
            for update in status_updates:
                stmt = select(TaskMapping).where(
                    TaskMapping.plan_id == plan_id,
                    TaskMapping.step_id == update["step_id"]
                )
                result = session.execute(stmt)
                mapping = result.scalar_one_or_none()
                if mapping:
                    mapping.status = update["status"]
                    mapping.synced_at = datetime.utcnow()
                    updated += 1
            session.commit()
        return updated

    def delete_by_plan(self, plan_id: str) -> int:
        """Delete all task mappings for a plan.

        Used when a plan is deleted or needs to be re-executed from scratch.

        Args:
            plan_id: The plan ID

        Returns:
            Number of mappings deleted
        """
        with self.session() as session:
            stmt = select(TaskMapping).where(TaskMapping.plan_id == plan_id)
            result = session.execute(stmt)
            mappings = result.scalars().all()
            count = len(mappings)
            for mapping in mappings:
                session.delete(mapping)
            session.commit()
            return count

    def get_pending_tasks(self, plan_id: str) -> List[Dict[str, Any]]:
        """Get all pending task mappings for a plan.

        Useful for resume scenarios to find tasks that haven't started.

        Args:
            plan_id: The plan ID

        Returns:
            List of pending task mappings
        """
        with self.session() as session:
            stmt = select(TaskMapping).where(
                TaskMapping.plan_id == plan_id,
                TaskMapping.status == "pending"
            ).order_by(TaskMapping.id)
            result = session.execute(stmt)
            mappings = result.scalars().all()
            return [self._to_dict(m) for m in mappings]

    def get_completed_tasks(self, plan_id: str) -> List[Dict[str, Any]]:
        """Get all completed task mappings for a plan.

        Args:
            plan_id: The plan ID

        Returns:
            List of completed task mappings
        """
        with self.session() as session:
            stmt = select(TaskMapping).where(
                TaskMapping.plan_id == plan_id,
                TaskMapping.status == "completed"
            ).order_by(TaskMapping.id)
            result = session.execute(stmt)
            mappings = result.scalars().all()
            return [self._to_dict(m) for m in mappings]

    def count_by_status(self, plan_id: str) -> Dict[str, int]:
        """Count task mappings by status for a plan.

        Args:
            plan_id: The plan ID

        Returns:
            Dict with counts: {"pending": N, "in_progress": N, "completed": N}
        """
        with self.session() as session:
            stmt = select(TaskMapping).where(TaskMapping.plan_id == plan_id)
            result = session.execute(stmt)
            mappings = result.scalars().all()

            counts = {"pending": 0, "in_progress": 0, "completed": 0, "failed": 0}
            for m in mappings:
                status = m.status or "pending"
                if status in counts:
                    counts[status] += 1
            return counts

    def _to_dict(self, mapping: TaskMapping) -> Dict[str, Any]:
        """Convert model to dictionary.

        Args:
            mapping: TaskMapping model instance

        Returns:
            Dictionary representation
        """
        if mapping is None:
            return None
        return {
            "id": mapping.id,
            "plan_id": mapping.plan_id,
            "step_id": mapping.step_id,
            "task_subject": mapping.task_subject,
            "task_description": mapping.task_description,
            "task_active_form": mapping.task_active_form,
            "blocked_by": json.loads(mapping.blocked_by_json or "[]"),
            "blocks": json.loads(mapping.blocks_json or "[]"),
            "session_id": mapping.session_id,
            "session_task_id": mapping.session_task_id,
            "status": mapping.status,
            "created_at": mapping.created_at.isoformat() if mapping.created_at else None,
            "synced_at": mapping.synced_at.isoformat() if mapping.synced_at else None,
        }


def get_task_mapping_repository(db=None) -> TaskMappingRepository:
    """Get a TaskMappingRepository instance.

    Convenience function for getting a repository instance.

    Args:
        db: Optional database connection

    Returns:
        TaskMappingRepository instance
    """
    return TaskMappingRepository(db)
