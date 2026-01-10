"""
Planning Workflow: Orchestrates multiple agents to create implementation plans.

This workflow coordinates:
1. Scout Agent - Explores the codebase to gather context
2. Architect Agent - Designs the high-level approach
3. Planner Agent - Creates detailed implementation steps
4. Validator Agent - Ensures the plan is complete and actionable

Usage:
    workflow = PlanningWorkflow(project_root=Path("."))
    result = workflow.run("Add user authentication with JWT")
"""
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..core import Agent, Workflow, WorkflowResult


# Agent system prompts
SCOUT_PROMPT = """You are a codebase scout. Your job is to explore a codebase and gather context for a task.

Given a user request, identify:
1. What type of project this is (language, framework, architecture)
2. Key files and directories relevant to the request
3. Existing patterns and conventions
4. Dependencies and integrations that might be affected

Be concise but thorough. Focus on information that will help plan the implementation.

Output format:
## Project Overview
<brief description of the project type and stack>

## Relevant Files
<list of files that will likely need to be modified or referenced>

## Existing Patterns
<patterns and conventions to follow>

## Dependencies
<any dependencies or integrations to consider>

## Considerations
<any risks, edge cases, or important notes>
"""

ARCHITECT_PROMPT = """You are a software architect. Your job is to design the high-level approach for implementing a feature.

Given:
- A user request
- Context about the codebase (from the scout)

Design:
1. The overall architecture/approach
2. Components that need to be created or modified
3. Data flow and interactions
4. Any technical decisions that need to be made

Keep the design practical and aligned with existing patterns. Don't over-engineer.

Output format:
## Approach
<high-level description of the implementation approach>

## Components
<list of components to create or modify>

## Data Flow
<how data moves through the system>

## Technical Decisions
<key decisions and their rationale>

## Open Questions
<anything that needs clarification>
"""

PLANNER_PROMPT = """You are a technical planner. Your job is to create detailed, actionable implementation steps.

Given:
- A user request
- Codebase context (from scout)
- Architecture design (from architect)

Create:
1. Step-by-step implementation tasks
2. Specific files to create or modify
3. Code snippets or pseudocode where helpful
4. Testing approach

Each step should be:
- Specific and actionable
- Small enough to complete in one session
- Clear about what files are affected

Output format:
## Implementation Steps

### Step 1: <title>
**Files:** <files to modify>
**Description:** <what to do>
<optional code snippet or pseudocode>

### Step 2: <title>
...continue for all steps...

## Testing Strategy
<how to verify the implementation works>

## Validation Commands
<specific commands to run to validate>
"""

VALIDATOR_PROMPT = """You are a plan validator. Your job is to ensure an implementation plan is complete and actionable.

Check that the plan:
1. Has clear, specific steps (not vague)
2. Covers all aspects of the request
3. Includes testing approach
4. Follows existing codebase patterns
5. Has no missing dependencies or prerequisites

If issues found, list them clearly. If the plan is good, confirm it's ready.

Output format:
## Validation Result
<APPROVED or NEEDS_REVISION>

## Checklist
- [ ] or [x] Clear, specific steps
- [ ] or [x] Complete coverage of request
- [ ] or [x] Testing approach included
- [ ] or [x] Follows codebase patterns
- [ ] or [x] No missing prerequisites

## Issues (if any)
<list any problems that need to be fixed>

## Recommendations (if any)
<suggestions for improvement>
"""


class PlanningWorkflow(Workflow):
    """
    Orchestrates multiple agents to create a comprehensive implementation plan.

    The workflow:
    1. Scout: Explores codebase for context
    2. Architect: Designs the approach
    3. Planner: Creates detailed steps
    4. Validator: Ensures plan quality

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

        # Register agents (they use Claude Code CLI, not direct API)
        self.register_agent(Agent(
            name="scout",
            system_prompt=SCOUT_PROMPT,
            cwd=project_root,
        ))
        self.register_agent(Agent(
            name="architect",
            system_prompt=ARCHITECT_PROMPT,
            cwd=project_root,
        ))
        self.register_agent(Agent(
            name="planner",
            system_prompt=PLANNER_PROMPT,
            cwd=project_root,
        ))
        self.register_agent(Agent(
            name="validator",
            system_prompt=VALIDATOR_PROMPT,
            cwd=project_root,
        ))

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

        # Read CLAUDE.md if exists
        claude_md = self.project_root / "CLAUDE.md"
        if claude_md.exists():
            context_parts.append("\n## Project Guidelines (CLAUDE.md)")
            context_parts.append(claude_md.read_text(encoding="utf-8")[:2000])

        return "\n".join(context_parts)

    def _generate_filename(self, request: str) -> str:
        """Generate a kebab-case filename from the request."""
        # Extract key words
        words = re.sub(r'[^\w\s]', '', request.lower()).split()
        # Remove common words
        stop_words = {'a', 'an', 'the', 'to', 'for', 'with', 'and', 'or', 'in', 'on', 'add', 'create', 'implement'}
        words = [w for w in words if w not in stop_words][:5]
        return '-'.join(words) + '.md'

    def execute(self, request: str) -> WorkflowResult:
        """Execute the planning workflow."""
        steps_completed = []
        total_tokens = 0

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
        total_tokens += scout_result.tokens_used

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
        total_tokens += architect_result.tokens_used

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
        total_tokens += planner_result.tokens_used

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
        total_tokens += validator_result.tokens_used

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
            total_tokens=total_tokens,
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
2. Run `/build .specs/{self._generate_filename(request)}` to implement
3. Run `/test` to validate the implementation
4. Run `/review` for code review
"""


def main():
    """CLI entry point for planning workflow."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m orchestrator.workflows.planning 'Your request here'")
        print("   or: uv run plan 'Your request here'")
        sys.exit(1)

    request = " ".join(sys.argv[1:])
    project_root = Path.cwd()

    workflow = PlanningWorkflow(project_root=project_root)
    result = workflow.run(request)

    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
