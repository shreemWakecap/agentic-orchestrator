"""
Knowledge-Enhanced Planning Workflow.

Takes a user request and creates a plan in the SQLite database.

Flow:
    User Request → Expert Selection → Planner Agent → Database (plans table)

The planning workflow:
1. Loads codebase knowledge (if available from scout)
2. Selects relevant experts based on request keywords
3. Gathers expert guidance for the planner
4. Runs planner with enriched context
5. Saves structured plan to database

Enhanced with:
- Knowledge store integration for architecture context
- Expert selection and consultation
- Displays "Consulting experts: ..." for transparency
"""
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from core import Agent, Workflow, WorkflowResult, get_agent_config
from core.plan_parser import PlanParser, validate_plan_coverage
from core.knowledge_store import KnowledgeStore
from core.expert_selector import ExpertSelector
from db import get_plan_repository, get_build_state_repository


class PlanningWorkflow(Workflow):
    """
    Knowledge-enhanced planning workflow.

    Creates implementation plans from user requests using:
    - Codebase knowledge from scout (if available)
    - Expert selection based on request keywords
    - Expert guidance injected into planner context
    """

    def __init__(
        self,
        project_root: Path,
        output_dir: Optional[Path] = None,
    ):
        self.project_root = project_root
        self._config = get_agent_config(project_root)

        # Output dir for any temporary files (kept for compatibility)
        output_dir = output_dir or project_root / ".orchestrator" / "specs" / "pending"
        output_dir.mkdir(parents=True, exist_ok=True)

        super().__init__(name="Planning Workflow", output_dir=output_dir)

        # Database repositories
        self._plan_repo = get_plan_repository(project_root)
        self._build_state_repo = get_build_state_repository(project_root)

        # Knowledge and expert systems
        self.knowledge_store = KnowledgeStore(project_root)
        self.expert_selector = ExpertSelector(project_root)

        # Load the planner agent
        self._load_agents()

    def _load_agents(self):
        """Load required agents."""
        try:
            self.register_agent(Agent.load("planner", self.project_root))
        except FileNotFoundError:
            self.console.print("[red]Error: planner agent not found[/red]")
            raise

    def _generate_plan_id(self, request: str) -> str:
        """Generate a unique plan ID from the request."""
        # Get next number from database
        next_num = self._plan_repo.get_next_plan_number()

        # Create slug from request
        words = re.sub(r"[^\w\s]", "", request.lower()).split()
        slug = "-".join(words[:4]) if words else "feature"

        return f"{next_num:03d}_{slug}"

    def _get_codebase_summary(self) -> str:
        """Get a brief codebase summary for context."""
        summary_parts = []

        # List top-level structure
        try:
            items = list(self.project_root.iterdir())
            dirs = sorted([i.name for i in items if i.is_dir() and not i.name.startswith(".")])[:15]
            files = sorted([i.name for i in items if i.is_file() and not i.name.startswith(".")])[:10]

            if dirs:
                summary_parts.append(f"Directories: {', '.join(dirs)}")
            if files:
                summary_parts.append(f"Root files: {', '.join(files)}")
        except Exception:
            pass

        # Check for common config files
        config_files = ["package.json", "pyproject.toml", "Cargo.toml", "go.mod", "requirements.txt"]
        found = [f for f in config_files if (self.project_root / f).exists()]
        if found:
            summary_parts.append(f"Config: {', '.join(found)}")

        return "\n".join(summary_parts) if summary_parts else "No codebase info available"

    def execute(self, request: str) -> WorkflowResult:
        """
        Execute the planning workflow.

        Args:
            request: User's feature request in plain text

        Returns:
            WorkflowResult with the path to the created plan
        """
        from core.symbols import CHECK, CROSS, ARROW_RIGHT

        self.console.print(f"\n[bold]Planning:[/bold] {request[:80]}...")

        # Generate plan ID
        plan_id = self._generate_plan_id(request)

        self.console.print(f"  [dim]Plan ID: {plan_id}[/dim]")

        # Get codebase context (basic or from knowledge store)
        codebase_summary = self._get_codebase_summary()

        # Get architecture context from knowledge store
        arch_context = ""
        if self.knowledge_store.exists():
            arch_context = self.knowledge_store.get_planning_context()
            if arch_context:
                self.console.print(f"  [dim]Using codebase knowledge[/dim]")

        # Select relevant experts
        expert_names = self.expert_selector.select_experts(request)
        expert_context = ""
        if expert_names:
            self.console.print(f"  [dim]Consulting experts: {', '.join(expert_names)}[/dim]")
            expert_context = self.expert_selector.get_expert_context(expert_names)

        # Run planner agent
        self.console.print(f"\n[cyan]{ARROW_RIGHT}[/cyan] Running planner agent...")

        # Build enhanced prompt with knowledge and expert context
        prompt_sections = [f"""Create an implementation plan for this request:

## REQUEST
{request}

## CODEBASE
{codebase_summary}"""]

        if arch_context:
            prompt_sections.append(f"""
## ARCHITECTURE CONTEXT
{arch_context}""")

        if expert_context:
            prompt_sections.append(f"""
## EXPERT GUIDANCE
{expert_context}""")

        prompt_sections.append("""
## INSTRUCTIONS
1. First, explore the codebase using Glob/Read to understand:
   - Project structure and patterns
   - Relevant existing files
   - Conventions to follow

2. Then output a complete plan in the required format:
   GOAL, CONTEXT, STEPS (with ACTION/DO/IN/OUT/DONE/NEEDS), VERIFY

Remember:
- Explore first, then plan
- Be specific with file paths
- Include DONE criteria for each step
- Follow existing patterns you discover
- Use architecture and expert guidance above (if provided)
""")

        planner_prompt = "\n".join(prompt_sections)

        result = self.run_agent(
            "planner",
            message=planner_prompt,
            show_progress=True
        )

        if not result.success:
            self.console.print(f"  [red]{CROSS}[/red] Planner failed: {result.error}")
            return WorkflowResult(
                success=False,
                error=f"Planner failed: {result.error}"
            )

        # Extract plan content from agent response
        plan_content = self._extract_plan_content(result.content)

        if not plan_content:
            self.console.print(f"  [red]{CROSS}[/red] No valid plan found in response")
            return WorkflowResult(
                success=False,
                error="Planner did not produce a valid plan"
            )

        # Validate the plan
        parser = PlanParser()
        parse_result = parser.parse(plan_content, plan_id)

        if not parse_result.success:
            self.console.print(f"  [yellow]Warning: Plan has issues: {parse_result.error_summary()}[/yellow]")
            # Still save it, but warn

        # Check coverage
        coverage_ok, coverage_msg = validate_plan_coverage(request, parse_result.plan) if parse_result.plan else (True, "")
        if not coverage_ok:
            self.console.print(f"  [yellow]Warning: {coverage_msg}[/yellow]")

        # Add metadata header for raw content
        full_content = f"""# Plan: {plan_id}

Request: {request}
Created: {datetime.now().isoformat()}
Status: pending

---

{plan_content}
"""

        # Save to database
        goal = parse_result.plan.goal if parse_result.plan else ""
        context = parse_result.plan.context if parse_result.plan else []
        verify = parse_result.plan.verify if parse_result.plan else []

        self._plan_repo.create(
            plan_id=plan_id,
            goal=goal,
            request=request,
            raw_content=full_content,
            context=context,
            verify=verify
        )

        # Save phases and steps to database
        if parse_result.plan:
            for phase in parse_result.plan.phases:
                self._plan_repo.add_phase(
                    plan_id=plan_id,
                    phase_id=phase.phase_id,
                    name=phase.name,
                    phase_number=phase.phase_number,
                    can_parallelize=phase.can_parallelize
                )

                for step_order, step in enumerate(phase.steps):
                    self._plan_repo.add_step(
                        plan_id=plan_id,
                        phase_id=phase.phase_id,
                        step_id=step.id,
                        action=step.action.value,
                        description=step.description,
                        step_order=step_order,
                        target=step.target,
                        done=step.done,
                        inputs=step.inputs,
                        needs=step.needs
                    )

            # Create initial build state
            self._build_state_repo.create(
                plan_id=plan_id,
                total_steps=parse_result.plan.total_steps
            )

        self.console.print(f"\n[green]{CHECK}[/green] Plan created: {plan_id}")

        if parse_result.plan:
            self.console.print(f"  Goal: [dim]{parse_result.plan.goal[:60]}...[/dim]" if len(parse_result.plan.goal) > 60 else f"  Goal: [dim]{parse_result.plan.goal}[/dim]")
            self.console.print(f"  Steps: [cyan]{parse_result.plan.total_steps}[/cyan]")

        return WorkflowResult(
            success=True,
            data={
                "plan_id": plan_id,
                "steps": parse_result.plan.total_steps if parse_result.plan else 0,
                "goal": parse_result.plan.goal if parse_result.plan else ""
            }
        )

    def _extract_plan_content(self, response: str) -> str:
        """Extract the plan content from agent response."""
        # Look for GOAL: section as start marker
        goal_match = re.search(r"(GOAL:.*)", response, re.DOTALL | re.IGNORECASE)
        if goal_match:
            return goal_match.group(1).strip()

        # Try to find plan in code block
        code_match = re.search(r"```(?:markdown)?\s*(GOAL:.*?)```", response, re.DOTALL | re.IGNORECASE)
        if code_match:
            return code_match.group(1).strip()

        # Return full response if it looks like a plan
        if "GOAL:" in response.upper() or "STEPS:" in response.upper():
            return response.strip()

        return ""


def run(args=None) -> int:
    """Run planning action from CLI."""
    if not args:
        print("Usage: plan <request>")
        print('Example: plan "Add user authentication with JWT"')
        return 1

    request = " ".join(args)
    project_root = Path(__file__).parent.parent.parent

    workflow = PlanningWorkflow(project_root=project_root)
    result = workflow.run(request)

    return 0 if result.success else 1


if __name__ == "__main__":
    import sys
    sys.exit(run(sys.argv[1:]))
