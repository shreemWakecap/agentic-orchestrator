"""Run management service for handling stuck workflow runs.

Provides high-level operations for managing workflow runs including:
- Force stopping stuck runs
- Identifying stale/stuck runs
- Cleaning up associated resources

Thread Safety:
- Uses RunRepository for database operations
- Integrates with TaskManager for background task cancellation
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional

from db import get_run_repository, RunRepository

logger = logging.getLogger(__name__)


# Statuses that can be force stopped
STOPPABLE_STATUSES = {"running", "pending"}


class RunManagementService:
    """Service for managing workflow runs.

    Handles force stopping stuck runs, querying stale runs,
    and cleaning up associated resources.

    Args:
        run_repo: Optional RunRepository instance. If not provided,
                 creates one using get_run_repository().
        project_id: Optional project ID for scoping operations.
    """

    def __init__(
        self,
        run_repo: Optional[RunRepository] = None,
        project_id: Optional[str] = None,
    ):
        self._run_repo = run_repo
        self._project_id = project_id

    @property
    def run_repo(self) -> RunRepository:
        """Get or create the RunRepository instance."""
        if self._run_repo is None:
            self._run_repo = get_run_repository()
        return self._run_repo

    def can_force_stop(self, run: Dict) -> bool:
        """Check if a run can be force stopped.

        A run can be force stopped if:
        - It exists
        - Its status is in STOPPABLE_STATUSES (running or pending)

        Args:
            run: Run dictionary with at least 'status' key

        Returns:
            True if the run can be force stopped, False otherwise
        """
        if not run:
            return False

        status = run.get("status", "").lower()
        return status in STOPPABLE_STATUSES

    def force_stop_run(self, run_id: str) -> Dict:
        """Force stop a stuck workflow run.

        Validates the run exists and is in a stoppable state,
        then updates its status to 'force_stopped' and cleans up
        any associated resources (cancels background tasks).

        Args:
            run_id: The unique identifier of the run to stop

        Returns:
            Dict with:
                - success: bool indicating if operation succeeded
                - message: Human-readable result message
                - previous_status: Status before force stop (if successful)
                - new_status: New status after force stop (if successful)
                - error: Error message (if failed)
        """
        # Get the run to validate it exists and check status
        run = self.run_repo.get(run_id)

        if not run:
            logger.warning(f"Force stop requested for non-existent run: {run_id}")
            return {
                "success": False,
                "error": f"Run not found: {run_id}",
                "message": "The specified run does not exist.",
            }

        previous_status = run.get("status", "unknown")

        # Validate run can be stopped
        if not self.can_force_stop(run):
            logger.warning(
                f"Force stop requested for run {run_id} with non-stoppable status: {previous_status}"
            )
            return {
                "success": False,
                "error": f"Cannot force stop run with status: {previous_status}",
                "message": f"Run is in '{previous_status}' status and cannot be force stopped. "
                          f"Only runs with status 'running' or 'pending' can be force stopped.",
                "current_status": previous_status,
            }

        # Try to cancel background task if exists
        self._cancel_background_task(run_id)

        # Call repository to force stop the run
        try:
            success = self.run_repo.force_stop(run_id)

            if success:
                logger.info(
                    f"Force stopped run {run_id}: {previous_status} -> force_stopped"
                )
                return {
                    "success": True,
                    "message": f"Run {run_id} has been force stopped.",
                    "previous_status": previous_status,
                    "new_status": "force_stopped",
                    "run_id": run_id,
                    "stopped_at": datetime.now().isoformat(),
                }
            else:
                logger.error(f"Repository force_stop returned False for run {run_id}")
                return {
                    "success": False,
                    "error": "Force stop operation failed at database level",
                    "message": "Failed to update run status in database.",
                }

        except Exception as e:
            logger.exception(f"Error force stopping run {run_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"An error occurred while force stopping the run: {e}",
            }

    def get_stuck_runs(self, stale_minutes: int = 30) -> List[Dict]:
        """Get runs that appear to be stuck.

        Finds runs that have been in 'running' or 'pending' status
        for longer than the specified threshold.

        Args:
            stale_minutes: Number of minutes after which a run
                          is considered stuck. Defaults to 30.

        Returns:
            List of run dictionaries for stuck runs, each containing:
                - All standard run fields
                - can_force_stop: bool indicating if run can be stopped
                - stuck_duration_minutes: How long the run has been stuck
        """
        try:
            stuck_runs = self.run_repo.list_stuck(stale_minutes=stale_minutes)

            # Enrich with additional metadata
            enriched_runs = []
            now = datetime.now()

            for run in stuck_runs:
                # Calculate how long it's been stuck
                started_at_str = run.get("started_at")
                if started_at_str:
                    try:
                        started_at = datetime.fromisoformat(started_at_str)
                        duration = now - started_at
                        stuck_minutes = int(duration.total_seconds() / 60)
                    except (ValueError, TypeError):
                        stuck_minutes = stale_minutes  # Default to threshold
                else:
                    stuck_minutes = stale_minutes

                enriched_run = {
                    **run,
                    "can_force_stop": self.can_force_stop(run),
                    "stuck_duration_minutes": stuck_minutes,
                }
                enriched_runs.append(enriched_run)

            logger.debug(
                f"Found {len(enriched_runs)} stuck runs (threshold: {stale_minutes} minutes)"
            )
            return enriched_runs

        except Exception as e:
            logger.exception(f"Error getting stuck runs: {e}")
            return []

    def _cancel_background_task(self, run_id: str) -> bool:
        """Attempt to cancel background task associated with a run.

        Tries to find and cancel the task in TaskManager.
        Logs but does not raise on failure.

        Args:
            run_id: The run ID (used as task ID in TaskManager)

        Returns:
            True if task was found and cancelled, False otherwise
        """
        try:
            from portal.services.task_manager import get_task_manager

            task_manager = get_task_manager()

            # Check if task exists
            task_status = task_manager.get_task_status(run_id)
            if task_status:
                # Attempt to cancel
                cancelled = task_manager.cancel_task(run_id)
                if cancelled:
                    logger.info(f"Cancelled background task for run {run_id}")
                    return True
                else:
                    logger.debug(
                        f"Could not cancel task for run {run_id} "
                        f"(status: {task_status.get('status')})"
                    )
            else:
                logger.debug(f"No active task found for run {run_id}")

            return False

        except Exception as e:
            logger.warning(f"Error cancelling background task for run {run_id}: {e}")
            return False


def get_run_management_service(
    project_id: Optional[str] = None,
) -> RunManagementService:
    """Factory function to create RunManagementService.

    Args:
        project_id: Optional project ID for scoping operations

    Returns:
        Configured RunManagementService instance
    """
    return RunManagementService(project_id=project_id)
