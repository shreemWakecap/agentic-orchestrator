"""
Process Executor - Handles CLI subprocess execution.

Spawns CLI commands as subprocesses with:
- Real-time output capture
- Timeout enforcement
- Graceful termination
- Exit code handling
"""
import asyncio
import os
import sys
import signal
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, Callable, Awaitable, AsyncIterator, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ProcessState(str, Enum):
    """Process execution state."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class ProcessResult:
    """Result of process execution."""
    job_id: str
    state: ProcessState
    exit_code: Optional[int] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None


# Type for output line callback
OutputCallback = Callable[[str, str], Awaitable[None]]  # (job_id, line) -> None


class ProcessExecutor:
    """
    Executes CLI commands as subprocesses.

    Usage:
        executor = ProcessExecutor(project_root="/path/to/project")

        async def handle_output(job_id, line):
            print(f"[{job_id}] {line}")

        result = await executor.execute(
            job_id="abc123",
            job_type="plan",
            parameters={"spec_id": "feat-001"},
            output_callback=handle_output,
            timeout_seconds=3600
        )
    """

    def __init__(
        self,
        project_root: Optional[Path] = None,
        cli_command: str = "uv run cli.py",
        env_vars: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize process executor.

        Args:
            project_root: Working directory for CLI commands
            cli_command: Base CLI command (default: uv run cli.py)
            env_vars: Additional environment variables
        """
        self.project_root = project_root or Path.cwd()
        self.cli_command = cli_command
        self.env_vars = env_vars or {}

        # Track running processes for cancellation
        self._processes: Dict[str, asyncio.subprocess.Process] = {}

    def build_command(
        self,
        job_type: str,
        parameters: Dict[str, Any],
    ) -> List[str]:
        """
        Build CLI command from job type and parameters.

        Args:
            job_type: Type of job (plan, build, etc.)
            parameters: Job parameters

        Returns:
            List of command arguments
        """
        # Start with base command
        cmd_parts = self.cli_command.split()
        cmd_parts.append(job_type)

        # Add common parameters
        if parameters.get("spec_id"):
            cmd_parts.extend(["--spec", str(parameters["spec_id"])])

        # Add output format flag for structured output
        cmd_parts.extend(["--output", "jsonl"])

        # Add job-specific parameters
        for key, value in parameters.items():
            if key.startswith("_"):  # Skip internal params
                continue
            if key in ["spec_id", "output"]:  # Already handled
                continue
            if value is True:
                cmd_parts.append(f"--{key}")
            elif value is not False and value is not None:
                cmd_parts.extend([f"--{key}", str(value)])

        # Handle resume from checkpoint
        if parameters.get("_resume_from_checkpoint"):
            cmd_parts.extend(["--resume-checkpoint", parameters["_resume_from_checkpoint"]])

        return cmd_parts

    def build_environment(
        self,
        job_id: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """
        Build environment variables for subprocess.

        Args:
            job_id: Job identifier
            parameters: Job parameters (used for resume state)

        Returns:
            Environment dict for subprocess
        """
        import json

        env = os.environ.copy()
        env.update(self.env_vars)
        env["JOB_ID"] = job_id
        env["PYTHONUNBUFFERED"] = "1"  # Ensure output is not buffered

        # Pass resume state via environment if present
        if parameters:
            if parameters.get("_resume_state"):
                env["RESUME_STATE"] = json.dumps(parameters["_resume_state"])
            if parameters.get("_resume_from_checkpoint"):
                env["RESUME_CHECKPOINT_ID"] = parameters["_resume_from_checkpoint"]

        return env

    async def execute(
        self,
        job_id: str,
        job_type: str,
        parameters: Dict[str, Any],
        output_callback: Optional[OutputCallback] = None,
        timeout_seconds: int = 3600,
    ) -> ProcessResult:
        """
        Execute a job as a subprocess.

        Args:
            job_id: Job identifier
            job_type: Type of job (plan, build, etc.)
            parameters: Job parameters
            output_callback: Async callback for each output line
            timeout_seconds: Maximum execution time

        Returns:
            ProcessResult with outcome details
        """
        cmd = self.build_command(job_type, parameters)
        env = self.build_environment(job_id, parameters)

        logger.info(f"Executing job {job_id}: {' '.join(cmd)}")

        started_at = datetime.utcnow()
        result = ProcessResult(
            job_id=job_id,
            state=ProcessState.PENDING,
            started_at=started_at,
        )

        try:
            # Spawn subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,  # Merge stderr into stdout
                cwd=str(self.project_root),
                env=env,
            )

            self._processes[job_id] = process
            result.state = ProcessState.RUNNING

            logger.info(f"Job {job_id} started with PID {process.pid}")

            # Read output with timeout
            try:
                await asyncio.wait_for(
                    self._read_output(job_id, process, output_callback),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                logger.warning(f"Job {job_id} timed out after {timeout_seconds}s")
                await self._terminate_process(job_id, process)
                result.state = ProcessState.TIMEOUT
                result.error_message = f"Timeout after {timeout_seconds} seconds"

            # Get exit code
            if result.state == ProcessState.RUNNING:
                exit_code = await process.wait()
                result.exit_code = exit_code

                if exit_code == 0:
                    result.state = ProcessState.COMPLETED
                else:
                    result.state = ProcessState.FAILED
                    result.error_message = f"Process exited with code {exit_code}"

                logger.info(f"Job {job_id} completed with exit code {exit_code}")

        except asyncio.CancelledError:
            logger.info(f"Job {job_id} cancelled")
            await self._terminate_process(job_id, self._processes.get(job_id))
            result.state = ProcessState.CANCELLED
            result.error_message = "Job cancelled"
            raise

        except Exception as e:
            logger.exception(f"Job {job_id} failed with error: {e}")
            result.state = ProcessState.FAILED
            result.error_message = str(e)

        finally:
            self._processes.pop(job_id, None)
            result.completed_at = datetime.utcnow()
            result.duration_seconds = (result.completed_at - started_at).total_seconds()

        return result

    async def _read_output(
        self,
        job_id: str,
        process: asyncio.subprocess.Process,
        callback: Optional[OutputCallback],
    ):
        """Read process output line by line."""
        if not process.stdout:
            return

        while True:
            line = await process.stdout.readline()
            if not line:
                break

            line_str = line.decode("utf-8", errors="replace").rstrip("\n\r")

            if callback:
                try:
                    await callback(job_id, line_str)
                except Exception as e:
                    logger.error(f"Output callback error: {e}")

    async def _terminate_process(
        self,
        job_id: str,
        process: Optional[asyncio.subprocess.Process],
        grace_period: float = 5.0,
    ):
        """Terminate a process gracefully."""
        if not process or process.returncode is not None:
            return

        logger.info(f"Terminating process for job {job_id}")

        # Try SIGTERM first
        try:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=grace_period)
                logger.info(f"Process for job {job_id} terminated gracefully")
                return
            except asyncio.TimeoutError:
                pass
        except ProcessLookupError:
            return  # Process already dead

        # Force kill with SIGKILL
        logger.warning(f"Force killing process for job {job_id}")
        try:
            process.kill()
            await process.wait()
        except ProcessLookupError:
            pass  # Process already dead

    async def cancel(self, job_id: str) -> bool:
        """
        Cancel a running job.

        Args:
            job_id: Job to cancel

        Returns:
            True if job was running and cancelled
        """
        process = self._processes.get(job_id)
        if not process:
            return False

        await self._terminate_process(job_id, process)
        return True

    def get_running_jobs(self) -> List[str]:
        """Get list of currently running job IDs."""
        return list(self._processes.keys())

    def is_running(self, job_id: str) -> bool:
        """Check if a job is currently running."""
        process = self._processes.get(job_id)
        return process is not None and process.returncode is None


# Singleton instance
_executor: Optional[ProcessExecutor] = None


def get_process_executor() -> ProcessExecutor:
    """Get the global process executor instance."""
    global _executor
    if _executor is None:
        _executor = ProcessExecutor()
    return _executor


def init_process_executor(
    project_root: Optional[Path] = None,
    cli_command: str = "uv run cli.py",
    env_vars: Optional[Dict[str, str]] = None,
) -> ProcessExecutor:
    """Initialize the global process executor."""
    global _executor
    _executor = ProcessExecutor(
        project_root=project_root,
        cli_command=cli_command,
        env_vars=env_vars,
    )
    return _executor
