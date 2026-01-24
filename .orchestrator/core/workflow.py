"""
Workflow: Base class for orchestrating multiple agents.

A workflow defines how agents work together to accomplish a task.

Multi-Project Support:
    Workflows can be scoped to a specific project using project_id.
    When set, all database operations and knowledge stores are
    automatically filtered by the project context.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Event
from typing import Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from .agent import Agent, AgentResult


class WorkflowCancelledError(Exception):
    """Raised when a workflow is cancelled during execution."""
    pass


@dataclass
class WorkflowResult:
    """Result from a workflow execution."""
    success: bool
    output_file: Optional[Path] = None
    steps_completed: list[str] = field(default_factory=list)
    total_tokens: int = 0
    error: Optional[str] = None
    data: dict[str, Any] = field(default_factory=dict)
    project_id: Optional[str] = None


class Workflow(ABC):
    """
    Base class for workflows.

    A workflow orchestrates multiple agents to accomplish a complex task.
    Subclasses implement the `execute` method to define the workflow logic.

    Supports cancellation via `cancel()` method and tracks total token usage.

    Multi-Project Support:
        Pass project_id to scope the workflow to a specific project.
        The project context is automatically set for all operations.

        Example:
            workflow = PlanningWorkflow(project_root, project_id="uuid-123")
            result = workflow.run("Add new feature")
    """

    def __init__(
        self,
        name: str,
        output_dir: Optional[Path] = None,
        project_id: Optional[str] = None,
        project_slug: Optional[str] = None,
    ):
        self.name = name
        self.output_dir = output_dir
        self.console = Console()
        self.agents: dict[str, Agent] = {}
        self.results: dict[str, AgentResult] = {}
        # Token tracking
        self._total_tokens: int = 0
        # Cancellation support (thread-safe)
        self._cancel_event: Event = Event()
        # Project context (multi-project mode)
        self._project_id = project_id
        self._project_slug = project_slug
        self._context_token = None

    @property
    def project_id(self) -> Optional[str]:
        """Get the project ID for this workflow."""
        if self._project_id:
            return self._project_id
        # Try to get from context
        try:
            from db.project_context import get_optional_project_id
            return get_optional_project_id()
        except ImportError:
            return None

    def _enter_project_context(self) -> None:
        """Enter the project context for this workflow."""
        if self._project_id and not self._context_token:
            try:
                from db.project_context import project_context
                self._context_token = project_context.set_project_sync(
                    self._project_id,
                    self._project_slug
                )
            except ImportError:
                pass

    def _exit_project_context(self) -> None:
        """Exit the project context for this workflow."""
        if self._context_token:
            try:
                from db.project_context import project_context
                project_context.reset_project(self._context_token)
                self._context_token = None
            except ImportError:
                pass

    def register_agent(self, agent: Agent) -> None:
        """Register an agent for use in this workflow."""
        self.agents[agent.name] = agent

    def cancel(self) -> None:
        """
        Cancel the workflow execution.

        Sets the cancellation flag which will be checked before each agent run.
        Already running agents will complete, but no new agents will start.
        Thread-safe: can be called from any thread.
        """
        self._cancel_event.set()
        from .symbols import WARNING
        self.console.print(f"[yellow]{WARNING} Workflow cancellation requested[/yellow]")

    def reset_cancellation(self) -> None:
        """Reset the cancellation flag for reuse of the workflow."""
        self._cancel_event.clear()

    @property
    def is_cancelled(self) -> bool:
        """Check if the workflow has been cancelled."""
        return self._cancel_event.is_set()

    @property
    def total_tokens(self) -> int:
        """Get the total tokens consumed by all agents so far."""
        return self._total_tokens

    def _check_cancellation(self) -> None:
        """Check if cancelled and raise if so."""
        if self.is_cancelled:
            raise WorkflowCancelledError("Workflow was cancelled")

    def run_agent(
        self,
        agent_name: str,
        message: str,
        context: Optional[str] = None,
        show_progress: bool = True,
        thinking_enabled: Optional[bool] = None,
        thinking_budget: Optional[int] = None,
    ) -> AgentResult:
        """
        Run a registered agent and store the result.

        Args:
            agent_name: Name of the registered agent
            message: Message to send to the agent
            context: Optional context from previous steps
            show_progress: Whether to show a spinner
            thinking_enabled: Enable extended thinking (default from config)
            thinking_budget: Token budget for thinking (default from config)

        Returns:
            AgentResult from the agent

        Raises:
            WorkflowCancelledError: If the workflow was cancelled before this agent could run
        """
        # Check for cancellation before starting
        self._check_cancellation()

        if agent_name not in self.agents:
            raise ValueError(f"Agent '{agent_name}' not registered")

        agent = self.agents[agent_name]

        if show_progress:
            with Progress(
                SpinnerColumn(),
                TextColumn(f"[cyan]{agent_name}[/cyan] working..."),
                console=self.console,
                transient=True
            ) as progress:
                progress.add_task("", total=None)
                result = agent.run(
                    message, context,
                    thinking_enabled=thinking_enabled,
                    thinking_budget=thinking_budget
                )
        else:
            result = agent.run(
                message, context,
                thinking_enabled=thinking_enabled,
                thinking_budget=thinking_budget
            )

        self.results[agent_name] = result

        # Accumulate token usage
        self._total_tokens += result.tokens_used

        # Log result
        from .symbols import CHECK, CROSS
        if result.success:
            tokens_info = f" ({result.tokens_used} tokens)" if result.tokens_used > 0 else ""
            self.console.print(f"  [green]{CHECK}[/green] {agent_name} complete{tokens_info}")
        else:
            self.console.print(f"  [red]{CROSS}[/red] {agent_name} failed: {result.error}")

        # Check for cancellation after agent completes (for next iteration)
        # Don't raise here, just return the result

        return result

    def get_result(self, agent_name: str) -> Optional[AgentResult]:
        """Get the result from a previously run agent."""
        return self.results.get(agent_name)

    def save_output(self, filename: str, content: str) -> Path:
        """Save workflow output to a file."""
        if self.output_dir is None:
            raise ValueError("Cannot save output: output_dir is not configured")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.output_dir / filename
        output_path.write_text(content, encoding="utf-8")
        return output_path

    @abstractmethod
    def execute(self, request: str) -> WorkflowResult:
        """
        Execute the workflow.

        Args:
            request: The user's request to process

        Returns:
            WorkflowResult with the outcome
        """
        pass

    def run(self, request: str) -> WorkflowResult:
        """
        Run the workflow with nice console output.

        Args:
            request: The user's request

        Returns:
            WorkflowResult
        """
        # Reset state for fresh run
        self.reset_cancellation()
        self._total_tokens = 0

        # Enter project context if set
        self._enter_project_context()

        # Escape backslashes in request for Rich markup (Windows paths)
        display_request = str(request).replace("\\", "/")

        # Show project info if available
        project_info = ""
        if self.project_id and self._project_slug:
            project_info = f"\n[dim]Project: {self._project_slug}[/dim]"

        self.console.print(Panel(
            f"[bold]{self.name}[/bold]{project_info}\n\n{display_request}",
            title="Workflow Started",
            border_style="cyan",
            width=80
        ))
        self.console.print()

        start_time = datetime.now()

        try:
            result = self.execute(request)
            # Ensure total_tokens is set from accumulated count
            result.total_tokens = self._total_tokens
            result.project_id = self.project_id
        except WorkflowCancelledError:
            result = WorkflowResult(
                success=False,
                error="Workflow was cancelled",
                total_tokens=self._total_tokens,
                project_id=self.project_id
            )
        except Exception as e:
            result = WorkflowResult(
                success=False,
                error=str(e),
                total_tokens=self._total_tokens,
                project_id=self.project_id
            )
        finally:
            # Always exit project context
            self._exit_project_context()

        duration = (datetime.now() - start_time).total_seconds()

        # Summary
        from .symbols import CHECK, CROSS, WARNING
        self.console.print()
        if result.success:
            # Escape backslashes for Rich markup (Windows paths)
            output_display = str(result.output_file).replace("\\", "/") if result.output_file else "None"
            self.console.print(Panel(
                f"[green]{CHECK} Workflow completed successfully[/green]\n\n"
                f"Output: {output_display}\n"
                f"Steps: {len(result.steps_completed)}\n"
                f"Tokens: {result.total_tokens:,}\n"
                f"Duration: {duration:.1f}s",
                title="Complete",
                border_style="green",
                width=80
            ))
        elif self.is_cancelled:
            self.console.print(Panel(
                f"[yellow]{WARNING} Workflow cancelled[/yellow]\n\n"
                f"Steps completed: {len(result.steps_completed)}\n"
                f"Tokens used: {result.total_tokens:,}\n"
                f"Duration: {duration:.1f}s",
                title="Cancelled",
                border_style="yellow",
                width=80
            ))
        else:
            # Escape backslashes in error for Rich markup (Windows paths)
            error_display = str(result.error).replace("\\", "/") if result.error else "Unknown error"
            self.console.print(Panel(
                f"[red]{CROSS} Workflow failed[/red]\n\n{error_display}",
                title="Error",
                border_style="red",
                width=80
            ))

        return result
