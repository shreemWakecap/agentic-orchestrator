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
- Token usage signal emission for analytics tracking
"""
import asyncio
import re
import uuid
from datetime import datetime
from pathlib import Path

from core import Agent, Workflow, WorkflowResult, get_agent_config
from core.plan_parser import PlanParser, validate_plan_coverage, validate_integration_completeness
from core.knowledge_store import KnowledgeStore
from core.expert_selector import ExpertSelector
from core.staleness_checker import StalenessChecker
from core.rule_checker import RuleChecker
from db import get_plan_repository, get_build_state_repository
from portal.services.token_usage_signal import get_token_usage_signal, TokenUsageSignal


class PlanningWorkflow(Workflow):
    """
    Knowledge-enhanced planning workflow.

    Creates implementation plans from user requests using:
    - Codebase knowledge from scout (if available)
    - Expert selection based on request keywords
    - Expert guidance injected into planner context
    """

    def __init__(self, project_root: Path, auto_scout_on_stale: bool = True):
        self.project_root = project_root
        self._config = get_agent_config(project_root)
        self.auto_scout_on_stale = auto_scout_on_stale

        super().__init__(name="Planning Workflow")

        # Database repositories
        self._plan_repo = get_plan_repository()
        self._build_state_repo = get_build_state_repository()

        # Knowledge and expert systems
        self.knowledge_store = KnowledgeStore(project_root)
        self.expert_selector = ExpertSelector(project_root)
        self.staleness_checker = StalenessChecker(project_root)

        # Token usage signal for analytics
        self._token_signal: TokenUsageSignal = get_token_usage_signal()

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

    def _emit_signal_sync(self, coro) -> None:
        """Emit a token usage signal from synchronous context."""
        try:
            # Try to get running loop
            try:
                loop = asyncio.get_running_loop()
                # If we're in an async context, create a task
                asyncio.ensure_future(coro)
            except RuntimeError:
                # No running loop, create one
                asyncio.run(coro)
        except Exception as e:
            self.console.print(f"  [dim]Token signal error: {e}[/dim]")

    def _estimate_tokens_for_planning(self, request: str, arch_context: str, expert_context: str) -> tuple[int, int]:
        """
        Estimate tokens for planning based on prompt size.

        Returns:
            Tuple of (estimated_input_tokens, estimated_output_tokens)
        """
        # Base prompt size
        base_prompt_tokens = 500  # Fixed instructions

        # Variable content
        request_tokens = len(request.split()) * 1.3  # Approx 1.3 tokens per word
        arch_tokens = len(arch_context.split()) * 1.3 if arch_context else 0
        expert_tokens = len(expert_context.split()) * 1.3 if expert_context else 0

        estimated_input = int(base_prompt_tokens + request_tokens + arch_tokens + expert_tokens)

        # Output estimation: plans typically 2-4x the request description
        # Plus exploration output from the agent
        estimated_output = int(estimated_input * 2.5) + 1000  # Base for plan structure

        return estimated_input, estimated_output

    def _calculate_cost_estimate(self, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate estimated cost based on token counts.

        Uses Claude Sonnet pricing as default:
        - Input: $3 per 1M tokens
        - Output: $15 per 1M tokens
        """
        input_cost_per_million = 3.0
        output_cost_per_million = 15.0

        input_cost = (input_tokens / 1_000_000) * input_cost_per_million
        output_cost = (output_tokens / 1_000_000) * output_cost_per_million

        return round(input_cost + output_cost, 6)

    def execute(self, request: str) -> WorkflowResult:
        """
        Execute the planning workflow.

        Args:
            request: User's feature request in plain text

        Returns:
            WorkflowResult with the path to the created plan
        """
        from core.symbols import CHECK, CROSS, ARROW_RIGHT, WARNING

        self.console.print(f"\n[bold]Planning:[/bold] {request[:80]}...")

        # Check if knowledge is stale
        is_stale, stale_reason = self.staleness_checker.is_stale()

        if is_stale:
            if self.auto_scout_on_stale:
                self.console.print(f"\n[yellow]{WARNING}[/yellow] Knowledge is stale: {stale_reason}")
                self.console.print(f"  [dim]Running scout to refresh knowledge...[/dim]")

                # Run unified scout
                try:
                    from workflows.unified_scout import UnifiedScoutWorkflow
                    scout_workflow = UnifiedScoutWorkflow(self.project_root)
                    changed_paths = self.staleness_checker.get_changed_paths()
                    scout_result = scout_workflow.run(
                        target_paths=changed_paths if changed_paths else None,
                        trigger="auto_pre_planning"
                    )

                    if scout_result.success:
                        self.console.print(f"  [green]{CHECK}[/green] Knowledge refreshed")
                    else:
                        self.console.print(f"  [yellow]Warning: Scout failed, continuing with stale knowledge[/yellow]")
                except Exception as e:
                    self.console.print(f"  [yellow]Warning: Could not run scout: {e}[/yellow]")
            else:
                self.console.print(f"\n[yellow]{WARNING}[/yellow] Warning: Knowledge may be stale ({stale_reason})")
                self.console.print(f"  [dim]Consider running 'scout' before planning[/dim]")

        # Generate plan ID and job ID for tracking
        plan_id = self._generate_plan_id(request)
        job_id = f"planning-{uuid.uuid4().hex[:8]}"

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

        # Estimate tokens for this planning run
        estimated_input, estimated_output = self._estimate_tokens_for_planning(
            request, arch_context, expert_context
        )

        # Emit estimation signal before planning starts
        self._emit_signal_sync(
            self._token_signal.emit_estimation_completed(
                job_id=job_id,
                plan_id=plan_id,
                estimated_input_tokens=estimated_input,
                estimated_output_tokens=estimated_output,
                model=self._config.get("model", "claude-sonnet-4-20250514"),
                cost_estimate=self._calculate_cost_estimate(estimated_input, estimated_output),
                metadata={
                    "workflow": "planning",
                    "request": request[:200],
                    "has_arch_context": bool(arch_context),
                    "experts_consulted": expert_names,
                }
            )
        )

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

2. **CRITICAL: Trace a Similar Feature End-to-End**
   Before planning, find ONE existing feature similar to what you're building.
   Trace its COMPLETE integration chain by answering:
   - What repository does it use? Where is it exported?
   - What service wraps that repository?
   - How is the service injected into routes? (check dependencies.py)
   - How are routes registered in app.py?
   - How does the page route get data to the template?

   Your plan MUST include equivalent steps for EACH layer you discover.

3. Then output a complete plan in the required format:
   GOAL, CONTEXT, STEPS (with ACTION/DO/IN/OUT/DONE/NEEDS), VERIFY

Remember:
- Explore first, trace a similar feature, then plan
- Be specific with file paths
- Include DONE criteria for each step
- Follow existing patterns you discover
- Use architecture and expert guidance above (if provided)
- For new features: ensure ALL integration layers are covered (Repository -> Service -> Routes -> Registration -> Page -> Template)
""")

        planner_prompt = "\n".join(prompt_sections)

        result = self.run_agent(
            "planner",
            message=planner_prompt,
            show_progress=True
        )

        if not result.success:
            self.console.print(f"  [red]{CROSS}[/red] Planner failed: {result.error}")
            # Emit completion signal for failed execution
            self._emit_signal_sync(
                self._token_signal.emit_execution_completed(
                    job_id=job_id,
                    plan_id=plan_id,
                    input_tokens=0,
                    output_tokens=0,
                    estimated_input_tokens=estimated_input,
                    estimated_output_tokens=estimated_output,
                    model=self._config.get("model", "claude-sonnet-4-20250514"),
                    actual_cost=0.0,
                    cost_estimate=self._calculate_cost_estimate(estimated_input, estimated_output),
                    metadata={
                        "workflow": "planning",
                        "plan_id": plan_id,
                        "success": False,
                        "error": result.error,
                    }
                )
            )
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

        # Check integration completeness for new features
        integration_ok, integration_msg = validate_integration_completeness(request, parse_result.plan) if parse_result.plan else (True, "")
        if not integration_ok:
            self.console.print(f"  [yellow]Warning: {integration_msg}[/yellow]")

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
            for phase_number, phase in enumerate(parse_result.plan.phases):
                self._plan_repo.add_phase(
                    plan_id=plan_id,
                    phase_id=phase.id,
                    name=phase.name,
                    phase_number=phase_number,
                    can_parallelize=phase.can_parallelize
                )

                for step_order, step in enumerate(phase.steps):
                    self._plan_repo.add_step(
                        plan_id=plan_id,
                        phase_id=phase.id,
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

        # Check plan against coding rules
        rule_warnings = []
        if parse_result.plan:
            try:
                rule_checker = RuleChecker(self.project_root)
                rule_result = rule_checker.check_plan(parse_result.plan)

                if rule_result.violations:
                    rule_warnings = rule_result.warnings
                    self.console.print(f"\n[yellow]{WARNING}[/yellow] Coding rule checks ({len(rule_result.violations)} issues):")
                    for violation in rule_result.violations[:5]:  # Show first 5
                        severity_color = "red" if violation.severity == "error" else "yellow"
                        self.console.print(f"  [{severity_color}][{violation.severity}][/{severity_color}] {violation.description}")
                    if len(rule_result.violations) > 5:
                        self.console.print(f"  [dim]...and {len(rule_result.violations) - 5} more[/dim]")
            except Exception as e:
                self.console.print(f"  [dim]Could not check coding rules: {e}[/dim]")

        # Extract actual token usage from result if available
        actual_input_tokens = getattr(result, 'input_tokens', 0) or 0
        actual_output_tokens = getattr(result, 'output_tokens', 0) or 0

        # Fallback: estimate from content length if no tokens reported
        if actual_input_tokens == 0 and actual_output_tokens == 0:
            # Rough estimation from content
            actual_input_tokens = int(len(planner_prompt.split()) * 1.3)
            actual_output_tokens = int(len(result.content.split()) * 1.3) if result.content else 0

        actual_cost = self._calculate_cost_estimate(actual_input_tokens, actual_output_tokens)

        # Emit execution completed signal
        self._emit_signal_sync(
            self._token_signal.emit_execution_completed(
                job_id=job_id,
                plan_id=plan_id,
                input_tokens=actual_input_tokens,
                output_tokens=actual_output_tokens,
                estimated_input_tokens=estimated_input,
                estimated_output_tokens=estimated_output,
                model=self._config.get("model", "claude-sonnet-4-20250514"),
                actual_cost=actual_cost,
                cost_estimate=self._calculate_cost_estimate(estimated_input, estimated_output),
                metadata={
                    "workflow": "planning",
                    "plan_id": plan_id,
                    "total_steps": parse_result.plan.total_steps if parse_result.plan else 0,
                    "success": True,
                }
            )
        )

        return WorkflowResult(
            success=True,
            data={
                "plan_id": plan_id,
                "steps": parse_result.plan.total_steps if parse_result.plan else 0,
                "goal": parse_result.plan.goal if parse_result.plan else "",
                "rule_warnings": rule_warnings
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
