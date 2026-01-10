"""
Planning Workflow: Orchestrates agents from .claude/agents/ to create plans.

This workflow loads and coordinates:
1. Scout Agent (.claude/agents/scout.md)
2. Architect Agent (.claude/agents/architect.md)
3. Planner Agent (.claude/agents/planner.md)
4. Validator Agent (.claude/agents/validator.md)

Usage:
    workflow = PlanningWorkflow(project_root=Path("."))
    result = workflow.run("Add user authentication with JWT")
"""
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..core import Agent, Workflow, WorkflowResult


class PlanningWorkflow(Workflow):
    """
    Orchestrates planning agents to create implementation plans.

    Agents are loaded from .claude/agents/:
    - scout.md: Explores codebase for context
    - architect.md: Designs the approach
    - planner.md: Creates detailed steps
    - validator.md: Ensures plan quality

    Output: A markdown file in .specs/ with the complete plan
    """

    def __init__(
        self,
        project_root: Path,
        output_dir: Optional[Path] = None,
    ):
        self.project_root = project_root
        output_dir = output_dir or project_root / ".specs"

        super().__init__(name="Planning Workflow", output_dir=output_dir)

        # Load agents from .claude/agents/
        self.register_agent(Agent.load("scout", project_root))
        self.register_agent(Agent.load("architect", project_root))
        self.register_agent(Agent.load("planner", project_root))
        self.register_agent(Agent.load("validator", project_root))

    def _get_codebase_context(self) -> str:
        """Gather basic codebase context for the scout."""
        context_parts = []

        # List top-level structure
        try:
            items = list(self.project_root.iterdir())
            dirs = [i.name for i in items if i.is_dir() and not i.name.startswith('.')]
            files = [i.name for i in items if i.is_file() and not i.name.startswith('.')]

            context_parts.append("## Project Structure")
            context_parts.append(f"Directories: {', '.join(sorted(dirs)[:20])}")
            context_parts.append(f"Root files: {', '.join(sorted(files)[:20])}")
        except Exception:
            pass

        # Check for common config files
        config_files = [
            "package.json", "pyproject.toml", "Cargo.toml", "go.mod",
            "requirements.txt", "setup.py", "pom.xml", "build.gradle"
        ]
        found_configs = [f for f in config_files if (self.project_root / f).exists()]
        if found_configs:
            context_parts.append(f"\nConfig files found: {', '.join(found_configs)}")

        return "\n".join(context_parts)

    def _generate_filename(self, request: str) -> str:
        """Generate a kebab-case filename from the request."""
        words = re.sub(r'[^\w\s]', '', request.lower()).split()
        stop_words = {'a', 'an', 'the', 'to', 'for', 'with', 'and', 'or', 'in', 'on', 'add', 'create', 'implement'}
        words = [w for w in words if w not in stop_words][:5]
        return '-'.join(words) + '.md'

    def execute(self, request: str) -> WorkflowResult:
        """Execute the planning workflow."""
        steps_completed = []

        # Step 1: Scout the codebase
        self.console.print("[bold]Phase 1:[/bold] Scouting codebase...")
        codebase_context = self._get_codebase_context()

        scout_result = self.run_agent(
            "scout",
            message=f"User request: {request}\n\nGather context about this codebase to help plan this feature.",
            context=codebase_context
        )

        if not scout_result.success:
            return WorkflowResult(success=False, error=f"Scout failed: {scout_result.error}")

        steps_completed.append("scout")

        # Step 2: Architect the solution
        self.console.print("\n[bold]Phase 2:[/bold] Designing architecture...")

        architect_result = self.run_agent(
            "architect",
            message=f"User request: {request}\n\nDesign the architecture for this feature.",
            context=f"## Codebase Context (from Scout)\n\n{scout_result.content}"
        )

        if not architect_result.success:
            return WorkflowResult(success=False, error=f"Architect failed: {architect_result.error}")

        steps_completed.append("architect")

        # Step 3: Create detailed plan
        self.console.print("\n[bold]Phase 3:[/bold] Creating implementation plan...")

        planner_result = self.run_agent(
            "planner",
            message=f"User request: {request}\n\nCreate a detailed implementation plan.",
            context=f"## Codebase Context\n\n{scout_result.content}\n\n## Architecture\n\n{architect_result.content}"
        )

        if not planner_result.success:
            return WorkflowResult(success=False, error=f"Planner failed: {planner_result.error}")

        steps_completed.append("planner")

        # Step 4: Validate the plan
        self.console.print("\n[bold]Phase 4:[/bold] Validating plan...")

        validator_result = self.run_agent(
            "validator",
            message=f"Validate this implementation plan for: {request}",
            context=f"## Plan to Validate\n\n{planner_result.content}"
        )

        if not validator_result.success:
            return WorkflowResult(success=False, error=f"Validator failed: {validator_result.error}")

        steps_completed.append("validator")

        # Compile final plan
        self.console.print("\n[bold]Phase 5:[/bold] Compiling final plan...")

        final_plan = self._compile_plan(
            request=request,
            scout=scout_result.content,
            architect=architect_result.content,
            planner=planner_result.content,
            validator=validator_result.content
        )

        # Save to file
        filename = self._generate_filename(request)
        output_path = self.save_output(filename, final_plan)

        return WorkflowResult(
            success=True,
            output_file=output_path,
            steps_completed=steps_completed,
            data={
                "scout": scout_result.content,
                "architect": architect_result.content,
                "planner": planner_result.content,
                "validator": validator_result.content
            }
        )

    def _compile_plan(
        self,
        request: str,
        scout: str,
        architect: str,
        planner: str,
        validator: str
    ) -> str:
        """Compile all agent outputs into a final plan document."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        filename = self._generate_filename(request)

        return f"""# Plan: {request}

> Generated by Planning Workflow on {timestamp}

## Overview

**Request:** {request}

---

## Codebase Context

{scout}

---

## Architecture Design

{architect}

---

## Implementation Plan

{planner}

---

## Validation

{validator}

---

## Next Steps

1. Review this plan and make any adjustments
2. Implement the steps in order
3. Validate with the commands provided
"""


def main():
    """CLI entry point."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m orchestrator.workflows.planning 'Your request'")
        sys.exit(1)

    request = " ".join(sys.argv[1:])
    project_root = Path.cwd()

    workflow = PlanningWorkflow(project_root=project_root)
    result = workflow.run(request)

    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
