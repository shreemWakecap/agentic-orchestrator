"""
TaskSyncService - Bidirectional sync between Claude Tasks and PostgreSQL.

Responsibilities:
- Create Tasks from DB steps at build start
- Sync Task state back to DB at checkpoints
- Restore Tasks from DB on resume
"""
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from db.repositories.plans import PlanRepository
from db.repositories.build_state import BuildStateRepository
from db.repositories.task_mapping import TaskMappingRepository


# Action verb to present continuous mapping
ACTION_TO_ACTIVE_FORM = {
    "create": "Creating",
    "modify": "Modifying",
    "update": "Updating",
    "add": "Adding",
    "delete": "Deleting",
    "remove": "Removing",
    "run": "Running",
    "execute": "Executing",
    "implement": "Implementing",
    "configure": "Configuring",
    "register": "Registering",
    "test": "Testing",
    "install": "Installing",
    "setup": "Setting up",
    "build": "Building",
    "deploy": "Deploying",
    "migrate": "Migrating",
    "refactor": "Refactoring",
    "fix": "Fixing",
    "integrate": "Integrating",
    "write": "Writing",
    "read": "Reading",
}


class TaskSyncService:
    """
    Bidirectional sync between Claude Tasks and PostgreSQL.

    This service manages the mapping between Claude's native Task tools
    and the orchestrator's database-backed step tracking system.

    Key responsibilities:
    - Generate TaskCreate instructions from plan steps
    - Sync Task status back to database at checkpoints
    - Generate resume context when builds are interrupted
    """

    def __init__(
        self,
        plan_repo: PlanRepository,
        build_state_repo: BuildStateRepository,
        task_mapping_repo: TaskMappingRepository
    ):
        """Initialize the service with required repositories.

        Args:
            plan_repo: Repository for plan/step data
            build_state_repo: Repository for build state tracking
            task_mapping_repo: Repository for task-step mappings
        """
        self._plan_repo = plan_repo
        self._build_state_repo = build_state_repo
        self._task_mapping_repo = task_mapping_repo

    def create_tasks_from_plan(self, plan_id: str, session_id: str) -> List[Dict[str, Any]]:
        """
        Generate TaskCreate instructions for a plan's steps.

        Returns a list of dicts that can be passed to the builder agent
        as context for creating Tasks.

        Args:
            plan_id: The plan being executed
            session_id: UUID of the Claude session

        Returns:
            List of task instruction dicts with:
            - step_id: The step this task represents
            - subject: Task subject (imperative form)
            - description: Full task description with ACTION, DO, etc.
            - activeForm: Present continuous form for spinner
            - blocked_by: List of step_ids this depends on
            - blocks: List of step_ids that depend on this task
        """
        steps = self._plan_repo.get_steps(plan_id)
        task_instructions = []

        # First pass: collect all dependencies to compute reverse mapping (blocks)
        blocked_by_map = {}  # step_id -> list of steps it depends on
        for step in steps:
            step_id = step["step_id"]
            blocked_by_map[step_id] = step.get("needs") or []

        # Compute blocks (reverse of blocked_by)
        blocks_map = {step["step_id"]: [] for step in steps}
        for step_id, deps in blocked_by_map.items():
            for dep in deps:
                if dep in blocks_map:
                    blocks_map[dep].append(step_id)

        # Second pass: build task instructions
        for step in steps:
            step_id = step["step_id"]
            subject = self._derive_subject(step)
            active_form = self._derive_active_form(step)
            description = self._format_task_description(step)
            blocked_by = blocked_by_map[step_id]
            blocks = blocks_map[step_id]

            task_instructions.append({
                "step_id": step_id,
                "subject": subject,
                "description": description,
                "activeForm": active_form,
                "blocked_by": blocked_by,
                "blocks": blocks,
            })

            # Pre-create mapping record (session_task_id filled later)
            self._task_mapping_repo.create(
                plan_id=plan_id,
                step_id=step_id,
                task_subject=subject,
                task_description=description,
                task_active_form=active_form,
                blocked_by=blocked_by,
                blocks=blocks,
                session_id=session_id,
            )

        return task_instructions

    def sync_task_state_to_db(self, plan_id: str, task_states: List[Dict[str, Any]]) -> None:
        """
        Sync Task states back to database.

        Called at checkpoints (after each step/wave completion).

        Args:
            plan_id: The plan being executed
            task_states: List of {id, status, ...} from TaskList output
        """
        # Get mappings to resolve task_id -> step_id
        mappings = self._task_mapping_repo.get_by_plan(plan_id)
        step_id_by_task = {
            m["session_task_id"]: m["step_id"]
            for m in mappings
            if m.get("session_task_id")
        }

        for task in task_states:
            task_id = str(task.get("id"))
            step_id = step_id_by_task.get(task_id)

            if step_id:
                status = self._map_task_status(task.get("status"))

                # Update StepState
                self._build_state_repo.set_step_state(
                    plan_id=plan_id,
                    step_id=step_id,
                    status=status,
                )

                # Update TaskMapping status
                self._task_mapping_repo.update_status(plan_id, step_id, status)

        # Update overall build progress
        self._update_build_progress(plan_id, task_states)

    def restore_tasks_for_resume(self, plan_id: str, new_session_id: str) -> str:
        """
        Generate context for rebuilding Tasks on resume.

        Returns a prompt fragment that tells the builder agent
        how to recreate the task state from DB.

        Args:
            plan_id: The plan being resumed
            new_session_id: New session ID for this execution

        Returns:
            Prompt fragment with resume context
        """
        build_state = self._build_state_repo.get(plan_id)

        if not build_state:
            return ""

        completed = set(build_state.get("completed_steps", []))
        failed = set(build_state.get("failed_steps", []))

        # Get task mappings for more detail
        mappings = self._task_mapping_repo.get_by_plan(plan_id)
        mapping_by_step = {m["step_id"]: m for m in mappings}

        # Format completed steps
        completed_lines = []
        for step_id in completed:
            mapping = mapping_by_step.get(step_id, {})
            subject = mapping.get("task_subject", step_id)
            completed_lines.append(f"- {step_id}: {subject}")

        completed_list = "\n".join(completed_lines) if completed_lines else "- None"

        # Format failed steps
        failed_lines = []
        for step_id in failed:
            mapping = mapping_by_step.get(step_id, {})
            subject = mapping.get("task_subject", step_id)
            failed_lines.append(f"- {step_id}: {subject}")

        failed_list = "\n".join(failed_lines) if failed_lines else "- None"

        resume_context = f"""## RESUME CONTEXT

This build is being resumed from a previous session. Previous state:
- Completed steps: {len(completed)}
- Failed steps: {len(failed)}

**Steps already completed (SKIP these - do NOT create Tasks for them):**
{completed_list}

**Steps that failed previously (may retry):**
{failed_list}

**Instructions:**
1. Create Tasks ONLY for steps that are NOT in the completed list above
2. For completed steps, do NOT create Tasks - they are already done
3. For failed steps, create Tasks normally - they will be retried
4. Set up blockedBy relationships as normal
5. If a step depends on a completed step, that dependency is already satisfied
"""
        return resume_context

    def update_task_session_mapping(
        self,
        plan_id: str,
        step_id: str,
        session_task_id: str
    ) -> None:
        """Update the session_task_id after TaskCreate returns.

        Args:
            plan_id: The plan ID
            step_id: The step ID
            session_task_id: The task ID returned by TaskCreate
        """
        self._task_mapping_repo.update_session_info(
            plan_id=plan_id,
            step_id=step_id,
            session_id=None,  # Keep existing
            session_task_id=session_task_id
        )

    def _derive_subject(self, step: Dict[str, Any]) -> str:
        """Derive task subject from step.

        Args:
            step: Step data dict

        Returns:
            Task subject string (e.g., "Create health.py")
        """
        action = step.get("action", "implement").title()
        target = step.get("target") or step.get("description", "")[:50]

        # Clean up target for readability
        if "/" in target:
            target = target.split("/")[-1]  # Use filename only

        return f"{action} {target}"

    def _derive_active_form(self, step: Dict[str, Any]) -> str:
        """Derive present continuous activeForm from step action.

        Args:
            step: Step data dict

        Returns:
            Active form string (e.g., "Creating health.py")
        """
        action = step.get("action", "implement").lower()
        target = step.get("target") or step.get("description", "")[:40]

        # Clean up target
        if "/" in target:
            target = target.split("/")[-1]

        # Get present continuous form
        active_verb = ACTION_TO_ACTIVE_FORM.get(action)
        if not active_verb:
            # Default: capitalize and add "ing"
            # Handle verbs ending in 'e' (e.g., "configure" -> "Configuring")
            if action.endswith("e"):
                active_verb = f"{action[:-1].title()}ing"
            else:
                active_verb = f"{action.title()}ing"

        return f"{active_verb} {target}"

    def _format_task_description(self, step: Dict[str, Any]) -> str:
        """Format full task description.

        Args:
            step: Step data dict

        Returns:
            Formatted description string
        """
        inputs = step.get("inputs") or step.get("in") or []
        return f"""ACTION: {step.get('action', 'implement')}
DO: {step.get('description', '')}
IN: {json.dumps(inputs)}
OUT: {step.get('target') or step.get('out', '')}
DONE: {step.get('done', 'Step completed successfully')}"""

    def _map_task_status(self, task_status: str) -> str:
        """Map Claude Task status to StepState status.

        Args:
            task_status: Status from Claude Task

        Returns:
            Mapped status string
        """
        mapping = {
            "pending": "pending",
            "in_progress": "in_progress",
            "completed": "completed",
        }
        return mapping.get(task_status, "pending")

    def _update_build_progress(self, plan_id: str, task_states: List[Dict[str, Any]]) -> None:
        """Update overall build progress based on task states.

        Args:
            plan_id: The plan ID
            task_states: List of task state dicts
        """
        total = len(task_states)
        completed = sum(1 for t in task_states if t.get("status") == "completed")
        in_progress = sum(1 for t in task_states if t.get("status") == "in_progress")

        # Determine overall status
        if completed == total and total > 0:
            status = "completed"
        elif in_progress > 0 or completed > 0:
            status = "building"
        else:
            status = "pending"

        self._build_state_repo.update(
            plan_id=plan_id,
            status=status,
            completed_steps=[str(t.get("id")) for t in task_states if t.get("status") == "completed"],
        )


def get_task_sync_service(
    plan_repo: PlanRepository = None,
    build_state_repo: BuildStateRepository = None,
    task_mapping_repo: TaskMappingRepository = None
) -> TaskSyncService:
    """Get a TaskSyncService instance.

    Convenience function that creates repositories if not provided.

    Args:
        plan_repo: Optional plan repository
        build_state_repo: Optional build state repository
        task_mapping_repo: Optional task mapping repository

    Returns:
        TaskSyncService instance
    """
    from db.repositories.plans import get_plan_repository
    from db.repositories.build_state import get_build_state_repository
    from db.repositories.task_mapping import get_task_mapping_repository

    return TaskSyncService(
        plan_repo=plan_repo or get_plan_repository(),
        build_state_repo=build_state_repo or get_build_state_repository(),
        task_mapping_repo=task_mapping_repo or get_task_mapping_repository(),
    )
