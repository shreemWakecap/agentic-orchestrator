"""Workflow submission service - handles workflow submission logic.

This service extracts business logic from route handlers, providing
a clean separation between HTTP handling and business logic.

SOLID Revamp:
- Extracted from routes for SRP compliance
- Accepts all dependencies via constructor (DIP)
- Testable in isolation
"""
import logging
import uuid
from typing import Optional, TYPE_CHECKING

from db import RunRepository, IProjectContextProvider

if TYPE_CHECKING:
    from portal.services.task_manager import TaskManager

logger = logging.getLogger(__name__)


class WorkflowSubmissionService:
    """Service for submitting workflows to background execution.

    Handles the business logic for workflow submission:
    - Generates run IDs
    - Creates run records
    - Submits tasks to TaskManager
    - Manages project context propagation

    All dependencies are injected via constructor for testability.
    """

    def __init__(
        self,
        run_repo: RunRepository,
        task_manager: "TaskManager",
        context_provider: IProjectContextProvider,
    ):
        """Initialize the workflow submission service.

        Args:
            run_repo: Repository for run records
            task_manager: Task manager for background execution
            context_provider: Provider for current project context
        """
        self.run_repo = run_repo
        self.task_manager = task_manager
        self.context_provider = context_provider

    def _generate_run_id(self) -> str:
        """Generate a unique run ID."""
        return str(uuid.uuid4())[:8]

    def submit_planning_workflow(self, description: str) -> str:
        """Submit a planning workflow for background execution.

        Args:
            description: Planning request description

        Returns:
            The generated run_id
        """
        from portal.services.workflow_runner import run_planning_workflow_sync

        run_id = self._generate_run_id()
        project_id = self.context_provider.get_project_id()

        # Create run record
        self.run_repo.create(
            run_id,
            workflow="planning",
            description=description,
            triggered_by="manual",
        )

        # Submit to task manager with project context
        self.task_manager.submit_task(
            func=run_planning_workflow_sync,
            args=(run_id, description, project_id),
        )

        logger.info(f"Submitted planning workflow: run_id={run_id}, project_id={project_id}")
        return run_id

    def submit_building_workflow(self, plan_id: str) -> str:
        """Submit a building workflow for background execution.

        Args:
            plan_id: ID of the plan to build

        Returns:
            The generated run_id
        """
        from portal.services.workflow_runner import run_building_workflow_sync

        run_id = self._generate_run_id()
        project_id = self.context_provider.get_project_id()

        # Create run record
        self.run_repo.create(
            run_id,
            workflow="building",
            plan_id=plan_id,
            triggered_by="manual",
        )

        # Submit to task manager with project context
        self.task_manager.submit_task(
            func=run_building_workflow_sync,
            args=(run_id, plan_id, project_id),
        )

        logger.info(f"Submitted building workflow: run_id={run_id}, plan_id={plan_id}, project_id={project_id}")
        return run_id

    def submit_building_workflow_resume(
        self,
        plan_id: str,
        from_step: Optional[str] = None,
    ) -> str:
        """Submit a building workflow in resume mode.

        Args:
            plan_id: ID of the plan to resume building
            from_step: Optional step ID to resume from

        Returns:
            The generated run_id
        """
        from portal.services.workflow_runner import run_building_workflow_resume_sync

        run_id = self._generate_run_id()
        project_id = self.context_provider.get_project_id()

        # Create run record
        self.run_repo.create(
            run_id,
            workflow="building",
            plan_id=plan_id,
            triggered_by="manual",
        )

        # Submit to task manager with project context and resume parameters
        self.task_manager.submit_task(
            func=run_building_workflow_resume_sync,
            args=(run_id, plan_id, from_step, project_id),
        )

        logger.info(f"Submitted building resume workflow: run_id={run_id}, plan_id={plan_id}, from_step={from_step}")
        return run_id

    def submit_scouting_workflow(
        self,
        scan_type: str = "full",
        target_paths: list = None,
        target_keywords: list = None,
        target_tech: list = None,
        generate_experts: bool = False,
    ) -> str:
        """Submit a scouting workflow for background execution.

        Args:
            scan_type: Type of scan ("full" or "quick")
            target_paths: Optional paths to focus on
            target_keywords: Optional keywords to search for
            target_tech: Optional technologies to focus on
            generate_experts: Whether to auto-generate missing experts

        Returns:
            The generated run_id
        """
        from portal.services.workflow_runner import run_scouting_workflow_sync

        run_id = self._generate_run_id()
        project_id = self.context_provider.get_project_id()

        # Create run record with description
        description = f"Scouting: {scan_type}"
        if target_paths:
            description += f" paths={target_paths}"
        if target_keywords:
            description += f" keywords={target_keywords}"

        self.run_repo.create(
            run_id,
            workflow="scouting",
            description=description,
            triggered_by="manual",
        )

        # Submit to task manager with project context
        self.task_manager.submit_task(
            func=run_scouting_workflow_sync,
            args=(run_id,),
            kwargs={
                "scan_type": scan_type,
                "target_paths": target_paths,
                "target_keywords": target_keywords,
                "target_tech": target_tech,
                "generate_experts": generate_experts,
                "project_id": project_id,
            },
        )

        logger.info(f"Submitted scouting workflow: run_id={run_id}, scan_type={scan_type}")
        return run_id


def get_workflow_submission_service(
    run_repo: RunRepository = None,
    task_manager: "TaskManager" = None,
    context_provider: IProjectContextProvider = None,
) -> WorkflowSubmissionService:
    """Factory function for WorkflowSubmissionService.

    Args:
        run_repo: Repository for runs. If None, uses default.
        task_manager: Task manager. If None, uses default.
        context_provider: Context provider. If None, uses default.

    Returns:
        Configured WorkflowSubmissionService instance
    """
    from db import get_run_repository, RegistryFallbackProjectProvider
    from portal.services.task_manager import get_task_manager

    return WorkflowSubmissionService(
        run_repo=run_repo or get_run_repository(),
        task_manager=task_manager or get_task_manager(),
        context_provider=context_provider or RegistryFallbackProjectProvider(),
    )
