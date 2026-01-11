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

__version__ = "1.0.0"

# Lazy imports to avoid issues when running from within the package
def __getattr__(name):
    """Lazy import of submodules to avoid relative import issues."""
    if name in ("Agent", "AgentResult", "Workflow", "WorkflowResult"):
        from core import Agent, AgentResult, Workflow, WorkflowResult
        return locals()[name]
    elif name == "PlanningWorkflow":
        from workflows import PlanningWorkflow
        return PlanningWorkflow
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "Agent",
    "AgentResult",
    "Workflow",
    "WorkflowResult",
    "PlanningWorkflow",
]
