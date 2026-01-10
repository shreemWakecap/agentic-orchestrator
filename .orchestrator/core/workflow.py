"""
Workflow: Base class for orchestrating multiple agents.

A workflow defines how agents work together to accomplish a task.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from .agent import Agent, AgentResult


@dataclass
class WorkflowResult:
    """Result from a workflow execution."""
    success: bool
    output_file: Optional[Path] = None
    steps_completed: list[str] = field(default_factory=list)
    total_tokens: int = 0
    error: Optional[str] = None
    data: dict[str, Any] = field(default_factory=dict)


class Workflow(ABC):
    """
    Base class for workflows.

    A workflow orchestrates multiple agents to accomplish a complex task.
    Subclasses implement the `execute` method to define the workflow logic.
    """

    def __init__(self, name: str, output_dir: Path):
        self.name = name
        self.output_dir = output_dir
        self.console = Console()
        self.agents: dict[str, Agent] = {}
        self.results: dict[str, AgentResult] = {}

    def register_agent(self, agent: Agent) -> None:
        """Register an agent for use in this workflow."""
        self.agents[agent.name] = agent

    def run_agent(
        self,
        agent_name: str,
        message: str,
        context: Optional[str] = None,
        show_progress: bool = True
    ) -> AgentResult:
        """
        Run a registered agent and store the result.

        Args:
            agent_name: Name of the registered agent
            message: Message to send to the agent
            context: Optional context from previous steps
            show_progress: Whether to show a spinner

        Returns:
            AgentResult from the agent
        """
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
                result = agent.run(message, context)
        else:
            result = agent.run(message, context)

        self.results[agent_name] = result

        # Log result
        if result.success:
            self.console.print(f"  [green]✓[/green] {agent_name} complete ({result.tokens_used} tokens)")
        else:
            self.console.print(f"  [red]✗[/red] {agent_name} failed: {result.error}")

        return result

    def get_result(self, agent_name: str) -> Optional[AgentResult]:
        """Get the result from a previously run agent."""
        return self.results.get(agent_name)

    def save_output(self, filename: str, content: str) -> Path:
        """Save workflow output to a file."""
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
        self.console.print(Panel(
            f"[bold]{self.name}[/bold]\n\n{request}",
            title="Workflow Started",
            border_style="cyan",
            width=80
        ))
        self.console.print()

        start_time = datetime.now()

        try:
            result = self.execute(request)
        except Exception as e:
            result = WorkflowResult(success=False, error=str(e))

        duration = (datetime.now() - start_time).total_seconds()

        # Summary
        self.console.print()
        if result.success:
            self.console.print(Panel(
                f"[green]✓ Workflow completed successfully[/green]\n\n"
                f"Output: {result.output_file}\n"
                f"Steps: {len(result.steps_completed)}\n"
                f"Tokens: {result.total_tokens}\n"
                f"Duration: {duration:.1f}s",
                title="Complete",
                border_style="green",
                width=80
            ))
        else:
            self.console.print(Panel(
                f"[red]✗ Workflow failed[/red]\n\n{result.error}",
                title="Error",
                border_style="red",
                width=80
            ))

        return result
