"""Async workflow base class for MCP integration.

Provides the foundation for async MCP-based workflows with
streaming progress updates and parallel agent execution.
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Callable, List, Tuple, Any
from pathlib import Path
from datetime import datetime

from rich.console import Console

from .mcp_client import MCPClient, StreamEvent
from .mcp_agent import MCPAgent, MCPAgentConfig, MCPAgentPool
from .workflow import WorkflowResult


@dataclass
class AsyncWorkflowState:
    """State for async workflow execution."""
    started_at: str = ""
    status: str = "pending"  # pending, running, completed, failed, cancelled
    current_phase: str = ""
    current_agent: str = ""
    completed_agents: List[str] = field(default_factory=list)
    total_tokens: int = 0
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "started_at": self.started_at,
            "status": self.status,
            "current_phase": self.current_phase,
            "current_agent": self.current_agent,
            "completed_agents": self.completed_agents,
            "total_tokens": self.total_tokens,
            "error": self.error
        }


class AsyncWorkflow(ABC):
    """Base class for async MCP-based workflows."""

    def __init__(
        self,
        name: str,
        project_root: Path,
        output_dir: Path,
        mcp_client: MCPClient
    ):
        """
        Initialize async workflow.

        Args:
            name: Workflow name
            project_root: Project root directory
            output_dir: Directory for output files
            mcp_client: MCP client for agent communication
        """
        self.name = name
        self.project_root = project_root
        self.output_dir = output_dir
        self.mcp_client = mcp_client
        self.console = Console()

        # Agent pool
        self.agents_dir = project_root / ".claude" / "agents"
        self.agent_pool = MCPAgentPool(mcp_client, self.agents_dir)

        # State
        self.state = AsyncWorkflowState()
        self._total_tokens = 0
        self._cancel_event = asyncio.Event()
        self._progress_callback: Optional[Callable[[str, StreamEvent], None]] = None

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def register_agent(
        self,
        name: str,
        timeout: int = 300,
        max_tokens: int = 4096,
        tools: Optional[List[str]] = None
    ) -> MCPAgent:
        """Register an agent with the workflow."""
        return self.agent_pool.register(name, timeout, max_tokens, tools)

    def on_progress(self, callback: Callable[[str, StreamEvent], None]):
        """
        Set callback for progress events.

        Args:
            callback: Function(agent_name, event) called on progress
        """
        self._progress_callback = callback

    async def run_agent(
        self,
        agent_name: str,
        message: str,
        context: Optional[str] = None
    ) -> Any:
        """
        Run an agent and return result.

        Args:
            agent_name: Name of registered agent
            message: Task message
            context: Additional context

        Returns:
            AgentResult from agent execution

        Raises:
            asyncio.CancelledError: If workflow was cancelled
        """
        if self._cancel_event.is_set():
            raise asyncio.CancelledError("Workflow cancelled")

        self.state.current_agent = agent_name

        def progress_handler(event: StreamEvent):
            if self._progress_callback:
                self._progress_callback(agent_name, event)

        result = await self.agent_pool.run(agent_name, message, context, progress_handler)

        self._total_tokens += result.tokens_used
        self.state.total_tokens = self._total_tokens
        self.state.completed_agents.append(agent_name)

        return result

    async def run_agents_parallel(
        self,
        tasks: List[Tuple[str, str, Optional[str]]]
    ) -> List[Any]:
        """
        Run multiple agents in parallel.

        Args:
            tasks: List of (agent_name, message, context) tuples

        Returns:
            List of AgentResults in same order as tasks
        """
        if self._cancel_event.is_set():
            raise asyncio.CancelledError("Workflow cancelled")

        async def run_task(agent_name: str, message: str, context: Optional[str]):
            return await self.run_agent(agent_name, message, context)

        return await asyncio.gather(*[
            run_task(name, msg, ctx) for name, msg, ctx in tasks
        ])

    def cancel(self):
        """Cancel the workflow execution."""
        self._cancel_event.set()
        self.state.status = "cancelled"

    def reset_cancel(self):
        """Reset cancel state for re-running."""
        self._cancel_event.clear()

    @property
    def is_cancelled(self) -> bool:
        """Check if workflow was cancelled."""
        return self._cancel_event.is_set()

    @property
    def total_tokens(self) -> int:
        """Get total tokens used so far."""
        return self._total_tokens

    async def execute(self, request: str) -> WorkflowResult:
        """
        Execute the workflow.

        Args:
            request: The request/task to execute

        Returns:
            WorkflowResult with outcome and metadata
        """
        self.state.started_at = datetime.now().isoformat()
        self.state.status = "running"

        try:
            result = await self._execute_impl(request)
            self.state.status = "completed" if result.success else "failed"
            return result

        except asyncio.CancelledError:
            self.state.status = "cancelled"
            return WorkflowResult(
                success=False,
                output_file=None,
                steps_completed=self.state.completed_agents,
                total_tokens=self._total_tokens,
                error="Workflow cancelled"
            )

        except Exception as e:
            self.state.status = "failed"
            self.state.error = str(e)
            return WorkflowResult(
                success=False,
                output_file=None,
                steps_completed=self.state.completed_agents,
                total_tokens=self._total_tokens,
                error=str(e)
            )

    @abstractmethod
    async def _execute_impl(self, request: str) -> WorkflowResult:
        """
        Implementation of workflow execution.

        Subclasses must implement this method.

        Args:
            request: The request/task to execute

        Returns:
            WorkflowResult with outcome and metadata
        """
        pass

    def print_header(self, title: str):
        """Print workflow header."""
        self.console.print(f"\n[bold blue]{'=' * 60}[/bold blue]")
        self.console.print(f"[bold]{title}[/bold]")
        self.console.print(f"[bold blue]{'=' * 60}[/bold blue]\n")

    def print_phase(self, phase: str):
        """Print phase header."""
        self.state.current_phase = phase
        self.console.print(f"\n[bold cyan]>>> {phase}[/bold cyan]")

    def print_agent(self, agent_name: str, action: str = "Running"):
        """Print agent status."""
        self.console.print(f"  [dim]{action}[/dim] [yellow]{agent_name}[/yellow]...")

    def print_success(self, message: str):
        """Print success message."""
        self.console.print(f"[green]✓ {message}[/green]")

    def print_error(self, message: str):
        """Print error message."""
        self.console.print(f"[red]✗ {message}[/red]")

    def print_info(self, message: str):
        """Print info message."""
        self.console.print(f"[dim]{message}[/dim]")


class AsyncWorkflowRunner:
    """Runner for executing async workflows."""

    def __init__(self, mcp_client: MCPClient):
        """
        Initialize workflow runner.

        Args:
            mcp_client: MCP client for workflows
        """
        self.mcp_client = mcp_client
        self._running_workflow: Optional[AsyncWorkflow] = None

    async def run(self, workflow: AsyncWorkflow, request: str) -> WorkflowResult:
        """
        Run a workflow.

        Args:
            workflow: Workflow to execute
            request: Request/task for workflow

        Returns:
            WorkflowResult from execution
        """
        self._running_workflow = workflow

        try:
            return await workflow.execute(request)
        finally:
            self._running_workflow = None

    def cancel(self):
        """Cancel currently running workflow."""
        if self._running_workflow:
            self._running_workflow.cancel()

    @property
    def is_running(self) -> bool:
        """Check if a workflow is currently running."""
        return self._running_workflow is not None
