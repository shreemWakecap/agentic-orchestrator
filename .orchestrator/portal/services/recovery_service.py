"""Recovery service for detecting and managing stale builds.

This module provides functionality to identify plans that are stuck in building
status and enables recovery operations to resume or restart failed builds.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from db import get_database, get_build_state_repository, get_plan_repository, BuildStateRepository, PlanRepository

logger = logging.getLogger(__name__)

# Default threshold for considering a build as stale (in minutes)
DEFAULT_STALE_THRESHOLD_MINUTES = 10


class RecoveryService:
    """Service for detecting and recovering stale builds.

    Identifies plans that have been in 'building' or 'in_progress' status
    without updates for a configurable time period, allowing them to be
    resumed or restarted.
    """

    # Status values that indicate an active build
    ACTIVE_BUILD_STATUSES = ('building', 'in_progress')

    def __init__(
        self,
        build_state_repo: Optional[BuildStateRepository] = None,
        plan_repo: Optional[PlanRepository] = None,
        stale_threshold_minutes: int = DEFAULT_STALE_THRESHOLD_MINUTES
    ):
        """Initialize the recovery service.

        Args:
            build_state_repo: Repository for build state. If None, uses default.
            plan_repo: Repository for plans. If None, uses default.
            stale_threshold_minutes: Minutes without update before build is stale.
        """
        self._repo = build_state_repo or get_build_state_repository()
        self._plan_repo = plan_repo or get_plan_repository()
        self._db = get_database()
        self.stale_threshold_minutes = stale_threshold_minutes

    def is_build_stale(
        self,
        plan_id: str,
        threshold_minutes: Optional[int] = None
    ) -> bool:
        """Check if a specific build is stale.

        Args:
            plan_id: The plan ID to check
            threshold_minutes: Override threshold (uses default if None)

        Returns:
            True if the build is in active status with no recent updates
        """
        threshold = threshold_minutes or self.stale_threshold_minutes
        build_state = self._repo.get(plan_id)

        if not build_state:
            return False

        status = build_state.get('status', '')
        if status not in self.ACTIVE_BUILD_STATUSES:
            return False

        updated_at = build_state.get('updated_at')
        if not updated_at:
            # No update time means we can't determine staleness
            return True

        return self._is_timestamp_stale(updated_at, threshold)

    def get_stale_builds(
        self,
        threshold_minutes: Optional[int] = None
    ) -> List[Dict]:
        """Get all builds that are stuck in building status.

        Args:
            threshold_minutes: Override threshold (uses default if None)

        Returns:
            List of stale build records with enriched information
        """
        threshold = threshold_minutes or self.stale_threshold_minutes
        stale_builds = []

        # Query for all active builds
        active_builds = self._get_active_builds()

        for build in active_builds:
            updated_at = build.get('updated_at')
            if self._is_timestamp_stale(updated_at, threshold):
                enriched = self._enrich_stale_build(build, threshold)
                stale_builds.append(enriched)

        return stale_builds

    def get_recoverable_plans(
        self,
        threshold_minutes: Optional[int] = None
    ) -> List[Dict]:
        """Get all plans that can be recovered with their recovery info.

        This method returns detailed information about each recoverable plan,
        including last update time, failure reason, and progress information.

        Args:
            threshold_minutes: Override threshold (uses default if None)

        Returns:
            List of recoverable plan info dicts with:
                - plan_id: The plan identifier
                - status: Current status (building/in_progress)
                - last_update: ISO timestamp of last update
                - minutes_stale: How many minutes since last update
                - last_error: Most recent error message (if any)
                - current_step: Current step being executed (if any)
                - current_phase: Current phase number
                - completed_steps: List of completed step IDs
                - failed_steps: List of failed step IDs
                - total_steps: Total number of steps
                - progress_percent: Percentage of steps completed
                - execution_mode: 'sequential', 'parallel', or 'coordinated'
                - current_wave_index: Current wave for parallel execution
                - goal_context: Goal verification state (if available)
                - retry_count: Number of retry attempts for current step
        """
        threshold = threshold_minutes or self.stale_threshold_minutes
        recoverable = []

        stale_builds = self.get_stale_builds(threshold)

        for build in stale_builds:
            plan_id = build.get('plan_id')

            # Load goal context if available
            goal_context = self._repo.get_goal_context(plan_id)

            # Get retry count for current step
            retry_count = self._get_current_step_retry_count(plan_id, build.get('current_step'))

            plan_info = {
                'plan_id': plan_id,
                'status': build.get('status'),
                'last_update': build.get('updated_at'),
                'minutes_stale': build.get('minutes_stale', 0),
                'last_error': build.get('last_error'),
                'current_step': build.get('current_step'),
                'current_phase': build.get('current_phase', 0),
                'completed_steps': build.get('completed_steps', []),
                'failed_steps': build.get('failed_steps', []),
                'total_steps': build.get('total_steps', 0),
                'progress_percent': self._calculate_progress(build),
                'started_at': build.get('started_at'),
                'can_resume': self._can_resume(build),
                # Extended state fields
                'execution_mode': build.get('execution_mode', 'sequential'),
                'current_wave_index': build.get('current_wave_index', 0),
                'goal_context': goal_context,
                'retry_count': retry_count,
            }
            recoverable.append(plan_info)

        return recoverable

    def _get_current_step_retry_count(
        self,
        plan_id: str,
        current_step: Optional[str]
    ) -> int:
        """Get retry count for the current step.

        Args:
            plan_id: The plan identifier
            current_step: Current step ID (if any)

        Returns:
            Number of retry attempts for the current step
        """
        if not current_step:
            return 0

        step_state = self._repo.get_step_state(plan_id, current_step)
        if step_state:
            return step_state.get('retry_count', 0)
        return 0

    def get_retry_history(
        self,
        plan_id: str,
        step_id: str
    ) -> List[Dict]:
        """Get retry history for a specific step.

        Args:
            plan_id: The plan identifier
            step_id: The step identifier

        Returns:
            List of retry history entries with timestamp, error, duration_ms
        """
        return self._repo.get_step_retry_history(plan_id, step_id)

    def is_in_backoff(
        self,
        plan_id: str,
        step_id: str,
        base_backoff_seconds: int = 30,
        max_backoff_seconds: int = 300
    ) -> bool:
        """Check if a step is currently in retry backoff period.

        Uses exponential backoff based on retry count:
        backoff = min(base * 2^retry_count, max_backoff)

        Args:
            plan_id: The plan identifier
            step_id: The step identifier
            base_backoff_seconds: Base backoff duration (default 30s)
            max_backoff_seconds: Maximum backoff duration (default 5 min)

        Returns:
            True if the step should not be retried yet due to backoff
        """
        retry_history = self.get_retry_history(plan_id, step_id)
        if not retry_history:
            return False

        # Get the last retry attempt
        last_retry = retry_history[-1]
        last_timestamp_str = last_retry.get('timestamp')

        if not last_timestamp_str:
            return False

        try:
            last_time = datetime.fromisoformat(last_timestamp_str)
            retry_count = len(retry_history)

            # Exponential backoff: base * 2^(retry_count-1), capped at max
            backoff_seconds = min(
                base_backoff_seconds * (2 ** (retry_count - 1)),
                max_backoff_seconds
            )

            # Check if we're still in backoff period
            backoff_expires = last_time + timedelta(seconds=backoff_seconds)
            return datetime.now() < backoff_expires
        except (ValueError, TypeError) as e:
            logger.warning(f"Error checking backoff for {plan_id}/{step_id}: {e}")
            return False

    def get_backoff_remaining(
        self,
        plan_id: str,
        step_id: str,
        base_backoff_seconds: int = 30,
        max_backoff_seconds: int = 300
    ) -> int:
        """Get remaining backoff time in seconds.

        Args:
            plan_id: The plan identifier
            step_id: The step identifier
            base_backoff_seconds: Base backoff duration
            max_backoff_seconds: Maximum backoff duration

        Returns:
            Seconds remaining in backoff, or 0 if not in backoff
        """
        retry_history = self.get_retry_history(plan_id, step_id)
        if not retry_history:
            return 0

        last_retry = retry_history[-1]
        last_timestamp_str = last_retry.get('timestamp')

        if not last_timestamp_str:
            return 0

        try:
            last_time = datetime.fromisoformat(last_timestamp_str)
            retry_count = len(retry_history)

            backoff_seconds = min(
                base_backoff_seconds * (2 ** (retry_count - 1)),
                max_backoff_seconds
            )

            backoff_expires = last_time + timedelta(seconds=backoff_seconds)
            remaining = (backoff_expires - datetime.now()).total_seconds()
            return max(0, int(remaining))
        except (ValueError, TypeError):
            return 0

    def get_recovery_summary(self) -> Dict:
        """Get a summary of all recoverable builds.

        Returns:
            Summary dict with counts and aggregated info
        """
        recoverable = self.get_recoverable_plans()

        return {
            'total_stale': len(recoverable),
            'by_status': self._group_by_status(recoverable),
            'oldest_stale_minutes': max(
                (p.get('minutes_stale', 0) for p in recoverable),
                default=0
            ),
            'plans': recoverable,
        }

    def _get_active_builds(self) -> List[Dict]:
        """Query database for all builds in active status.

        Returns:
            List of build state records with active status
        """
        # Build query for active statuses
        placeholders = ','.join('?' * len(self.ACTIVE_BUILD_STATUSES))
        query = f"""
            SELECT * FROM build_states
            WHERE status IN ({placeholders})
            ORDER BY updated_at ASC
        """

        rows = self._db.fetchall(query, self.ACTIVE_BUILD_STATUSES)

        # Deserialize JSON fields
        for row in rows:
            row['completed_steps'] = self._db.from_json(
                row.get('completed_steps_json'), []
            )
            row['failed_steps'] = self._db.from_json(
                row.get('failed_steps_json'), []
            )
            row['skipped_steps'] = self._db.from_json(
                row.get('skipped_steps_json'), []
            )
            row['files_created'] = self._db.from_json(
                row.get('files_created_json'), []
            )
            row['files_modified'] = self._db.from_json(
                row.get('files_modified_json'), []
            )

        return rows

    def _is_timestamp_stale(
        self,
        timestamp_str: Optional[str],
        threshold_minutes: int
    ) -> bool:
        """Check if a timestamp is older than the threshold.

        Args:
            timestamp_str: ISO format timestamp string
            threshold_minutes: Minutes threshold

        Returns:
            True if timestamp is older than threshold
        """
        if not timestamp_str:
            return True

        try:
            updated_time = datetime.fromisoformat(timestamp_str)
            cutoff = datetime.now() - timedelta(minutes=threshold_minutes)
            return updated_time < cutoff
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid timestamp format: {timestamp_str} - {e}")
            return True

    def _enrich_stale_build(self, build: Dict, threshold: int) -> Dict:
        """Add computed fields to a stale build record.

        Args:
            build: The build state record
            threshold: Stale threshold in minutes

        Returns:
            Build record with additional computed fields
        """
        updated_at = build.get('updated_at')
        minutes_stale = 0

        if updated_at:
            try:
                updated_time = datetime.fromisoformat(updated_at)
                delta = datetime.now() - updated_time
                minutes_stale = int(delta.total_seconds() / 60)
            except (ValueError, TypeError):
                pass

        build['minutes_stale'] = minutes_stale
        build['stale_threshold'] = threshold
        return build

    def _calculate_progress(self, build: Dict) -> float:
        """Calculate build progress as a percentage.

        Args:
            build: Build state record

        Returns:
            Progress percentage (0-100)
        """
        total = build.get('total_steps', 0)
        if total == 0:
            return 0.0

        completed = len(build.get('completed_steps', []))
        return round((completed / total) * 100, 1)

    def _can_resume(self, build: Dict) -> bool:
        """Determine if a build can be resumed vs needs restart.

        A build can be resumed if:
        - It has a valid current step or completed steps
        - It doesn't have critical errors that require restart

        Args:
            build: Build state record

        Returns:
            True if build can be resumed from current state
        """
        # If there's a current step, we can resume from there
        if build.get('current_step'):
            return True

        # If there are completed steps, we can resume from next step
        if build.get('completed_steps'):
            return True

        # Otherwise, need to restart from beginning
        return False

    def _group_by_status(self, plans: List[Dict]) -> Dict[str, int]:
        """Group recoverable plans by their status.

        Args:
            plans: List of plan info dicts

        Returns:
            Dict mapping status to count
        """
        counts = {}
        for plan in plans:
            status = plan.get('status', 'unknown')
            counts[status] = counts.get(status, 0) + 1
        return counts

    def get_plan_name(self, plan_id: str) -> Optional[str]:
        """Get the plan name for UI display.

        Args:
            plan_id: The plan identifier

        Returns:
            Plan name if found, None otherwise
        """
        row = self._db.fetchone(
            "SELECT name FROM plans WHERE id = ?", (plan_id,)
        )
        return row.get('name') if row else None

    def cancel_build(self, plan_id: str) -> Dict:
        """Cancel a build that is in progress or stale.

        Validates that the plan is in a cancelable state before cancelling.
        Uses aggregate root pattern: Plan.status is updated first, then build_states.

        Args:
            plan_id: The plan identifier to cancel

        Returns:
            Dict with 'success' boolean and 'message' or 'error' string
        """
        # Check if build state exists
        build_state = self._repo.get(plan_id)
        if not build_state:
            return {
                'success': False,
                'error': f'No build found for plan {plan_id}'
            }

        # Validate cancelable state
        current_status = build_state.get('status', '')
        cancelable_statuses = ('building', 'in_progress', 'pending', 'paused')

        if current_status not in cancelable_statuses:
            return {
                'success': False,
                'error': f'Build cannot be cancelled: current status is {current_status}'
            }

        # Cancel the build using aggregate root pattern:
        # 1. Update Plan first (authoritative)
        self._plan_repo.update_status(plan_id, 'cancelled')
        # 2. Cascade to build_states
        cancelled = self._repo.cancel(plan_id)

        if cancelled:
            plan_name = self.get_plan_name(plan_id) or plan_id
            logger.info(f"Build cancelled for plan: {plan_name} ({plan_id})")
            return {
                'success': True,
                'message': f'Build cancelled for plan: {plan_name}'
            }
        else:
            return {
                'success': False,
                'error': 'Failed to cancel build'
            }

    def pause_build(self, plan_id: str) -> Dict:
        """Pause a build that is in progress.

        Validates that the plan is in a pausable state before pausing.
        Paused builds can be resumed later.
        Uses aggregate root pattern: Plan.status is updated first, then build_states.

        Args:
            plan_id: The plan identifier to pause

        Returns:
            Dict with 'success' boolean and 'message' or 'error' string
        """
        # Check if build state exists
        build_state = self._repo.get(plan_id)
        if not build_state:
            return {
                'success': False,
                'error': f'No build found for plan {plan_id}'
            }

        # Validate pausable state
        current_status = build_state.get('status', '')
        pausable_statuses = ('building', 'in_progress')

        if current_status not in pausable_statuses:
            return {
                'success': False,
                'error': f'Build cannot be paused: current status is {current_status}'
            }

        # Pause the build using aggregate root pattern:
        # 1. Update Plan first (authoritative)
        self._plan_repo.update_status(plan_id, 'paused')
        # 2. Cascade to build_states
        paused = self._repo.pause(plan_id)

        if paused:
            plan_name = self.get_plan_name(plan_id) or plan_id
            logger.info(f"Build paused for plan: {plan_name} ({plan_id})")
            return {
                'success': True,
                'message': f'Build paused for plan: {plan_name}'
            }
        else:
            return {
                'success': False,
                'error': 'Failed to pause build'
            }


# Factory function for consistency with other services
def get_recovery_service(
    stale_threshold_minutes: int = DEFAULT_STALE_THRESHOLD_MINUTES
) -> RecoveryService:
    """Get a RecoveryService instance.

    Args:
        stale_threshold_minutes: Minutes threshold for stale detection

    Returns:
        Configured RecoveryService instance
    """
    return RecoveryService(stale_threshold_minutes=stale_threshold_minutes)
