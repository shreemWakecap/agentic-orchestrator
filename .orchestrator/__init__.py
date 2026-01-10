"""
SDLC Orchestrator

A minimal, self-improving orchestration system for software development.

Workflows:
    - PlanningWorkflow: Create implementation plans with multiple agents

Usage:
    from orchestrator.workflows import PlanningWorkflow

    workflow = PlanningWorkflow(project_root=Path("."))
    result = workflow.run("Add user authentication")
"""
from .core import Agent, AgentResult, Workflow, WorkflowResult
from .workflows import PlanningWorkflow

__version__ = "1.0.0"
__all__ = [
    "Agent",
    "AgentResult",
    "Workflow",
    "WorkflowResult",
    "PlanningWorkflow",
]
