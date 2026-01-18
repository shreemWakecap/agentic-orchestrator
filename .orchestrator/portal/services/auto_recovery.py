"""Auto-recovery background task for detecting and handling stale builds.

This module provides a background task that periodically checks for builds
that have become stuck (stale) and can optionally mark them as paused to
allow for recovery.
"""
import asyncio
import logging
from datetime import datetime
from typing import Callable, List, Optional

from .recovery_service import RecoveryService, get_recovery_service

logger = logging.getLogger(__name__)

# Default check interval in seconds
DEFAULT_CHECK_INTERVAL_SECONDS = 60

# Default stale threshold for auto-recovery (in minutes)
DEFAULT_AUTO_STALE_THRESHOLD_MINUTES = 15


class AutoRecoveryTask:
    """Background task for automatic detection and handling of stale builds.

    This task runs periodically to identify builds that have become stuck
    without updates for a configurable time period. When stale builds are
    detected, it can optionally pause them to allow manual recovery.

    Attributes:
        check_interval: Seconds between stale build checks
        stale_threshold_minutes: Minutes without update before build is stale
        auto_pause: Whether to automatically pause stale builds
    """

    def __init__(
        self,
        recovery_service: Optional[RecoveryService] = None,
        check_interval: int = DEFAULT_CHECK_INTERVAL_SECONDS,
        stale_threshold_minutes: int = DEFAULT_AUTO_STALE_THRESHOLD_MINUTES,
        auto_pause: bool = True,
        on_stale_detected: Optional[Callable[[List[dict]], None]] = None,
    ):
        """Initialize the auto-recovery task.

        Args:
            recovery_service: RecoveryService instance. If None, creates default.
            check_interval: Seconds between checks for stale builds.
            stale_threshold_minutes: Minutes threshold for stale detection.
            auto_pause: If True, automatically pause detected stale builds.
            on_stale_detected: Optional callback when stale builds are found.
        """
        self._recovery_service = recovery_service or get_recovery_service(
            stale_threshold_minutes=stale_threshold_minutes
        )
        self.check_interval = check_interval
        self.stale_threshold_minutes = stale_threshold_minutes
        self.auto_pause = auto_pause
        self._on_stale_detected = on_stale_detected

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_check: Optional[datetime] = None
        self._stale_count = 0
        self._paused_count = 0

    @property
    def is_running(self) -> bool:
        """Check if the background task is currently running."""
        return self._running and self._task is not None

    @property
    def last_check_time(self) -> Optional[datetime]:
        """Get the timestamp of the last stale build check."""
        return self._last_check

    @property
    def stats(self) -> dict:
        """Get statistics about the auto-recovery task."""
        return {
            'is_running': self.is_running,
            'last_check': self._last_check.isoformat() if self._last_check else None,
            'check_interval_seconds': self.check_interval,
            'stale_threshold_minutes': self.stale_threshold_minutes,
            'auto_pause_enabled': self.auto_pause,
            'total_stale_detected': self._stale_count,
            'total_auto_paused': self._paused_count,
        }

    async def start(self) -> None:
        """Start the background auto-recovery task.

        The task will run periodically checking for stale builds.
        If already running, this method does nothing.
        """
        if self._running:
            logger.warning("Auto-recovery task is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            f"Auto-recovery task started (interval={self.check_interval}s, "
            f"threshold={self.stale_threshold_minutes}min, auto_pause={self.auto_pause})"
        )

    async def stop(self) -> None:
        """Stop the background auto-recovery task.

        Gracefully stops the task and waits for it to complete.
        If not running, this method does nothing.
        """
        if not self._running:
            logger.warning("Auto-recovery task is not running")
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Auto-recovery task stopped")

    async def check_and_mark_stale(self) -> List[dict]:
        """Check for stale builds and optionally mark them as paused.

        This method performs a single check for stale builds. When stale
        builds are detected:
        - If auto_pause is True, pauses each stale build
        - Triggers the on_stale_detected callback if configured
        - Logs information about detected and paused builds

        Returns:
            List of stale build info dicts that were detected
        """
        self._last_check = datetime.now()

        # Get stale builds using the recovery service
        stale_builds = self._recovery_service.get_stale_builds(
            threshold_minutes=self.stale_threshold_minutes
        )

        if not stale_builds:
            logger.debug("No stale builds detected")
            return []

        self._stale_count += len(stale_builds)
        logger.info(f"Detected {len(stale_builds)} stale build(s)")

        # Process each stale build
        paused_builds = []
        for build in stale_builds:
            plan_id = build.get('plan_id')
            minutes_stale = build.get('minutes_stale', 0)
            status = build.get('status', 'unknown')

            logger.warning(
                f"Stale build detected: plan_id={plan_id}, "
                f"status={status}, stale_for={minutes_stale}min"
            )

            # Auto-pause if enabled
            if self.auto_pause:
                result = self._recovery_service.pause_build(plan_id)
                if result.get('success'):
                    self._paused_count += 1
                    paused_builds.append(build)
                    logger.info(f"Auto-paused stale build: {plan_id}")
                else:
                    logger.error(
                        f"Failed to auto-pause build {plan_id}: "
                        f"{result.get('error')}"
                    )

        # Trigger callback if configured
        if self._on_stale_detected and stale_builds:
            try:
                self._on_stale_detected(stale_builds)
            except Exception as e:
                logger.error(f"Error in on_stale_detected callback: {e}")

        return stale_builds

    async def _run_loop(self) -> None:
        """Internal loop that periodically checks for stale builds."""
        logger.debug("Auto-recovery loop started")

        while self._running:
            try:
                await self.check_and_mark_stale()
            except Exception as e:
                logger.error(f"Error during stale build check: {e}", exc_info=True)

            # Wait for next check interval
            try:
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break

        logger.debug("Auto-recovery loop ended")


# Singleton instance for application-wide use
_auto_recovery_task: Optional[AutoRecoveryTask] = None


def get_auto_recovery_task(
    check_interval: int = DEFAULT_CHECK_INTERVAL_SECONDS,
    stale_threshold_minutes: int = DEFAULT_AUTO_STALE_THRESHOLD_MINUTES,
    auto_pause: bool = True,
) -> AutoRecoveryTask:
    """Get or create the singleton AutoRecoveryTask instance.

    Args:
        check_interval: Seconds between checks for stale builds.
        stale_threshold_minutes: Minutes threshold for stale detection.
        auto_pause: If True, automatically pause detected stale builds.

    Returns:
        The singleton AutoRecoveryTask instance.
    """
    global _auto_recovery_task
    if _auto_recovery_task is None:
        _auto_recovery_task = AutoRecoveryTask(
            check_interval=check_interval,
            stale_threshold_minutes=stale_threshold_minutes,
            auto_pause=auto_pause,
        )
    return _auto_recovery_task


async def start_auto_recovery(
    check_interval: int = DEFAULT_CHECK_INTERVAL_SECONDS,
    stale_threshold_minutes: int = DEFAULT_AUTO_STALE_THRESHOLD_MINUTES,
    auto_pause: bool = True,
) -> AutoRecoveryTask:
    """Convenience function to start the auto-recovery task.

    Creates the singleton instance if needed and starts it.

    Args:
        check_interval: Seconds between checks for stale builds.
        stale_threshold_minutes: Minutes threshold for stale detection.
        auto_pause: If True, automatically pause detected stale builds.

    Returns:
        The running AutoRecoveryTask instance.
    """
    task = get_auto_recovery_task(
        check_interval=check_interval,
        stale_threshold_minutes=stale_threshold_minutes,
        auto_pause=auto_pause,
    )
    await task.start()
    return task


async def stop_auto_recovery() -> None:
    """Convenience function to stop the auto-recovery task."""
    global _auto_recovery_task
    if _auto_recovery_task:
        await _auto_recovery_task.stop()
