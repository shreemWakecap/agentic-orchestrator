"""
Smart Building Workflow: Executes implementation plans with parallel sub-agents.

For simple plans: Parser → Builder (per step) → Tester → Reviewer
For complex/master plans: Parser → Coordinator → [Parallel Builders] → Integrator → Tester → Reviewer

Features:
- Incremental building with progress tracking
- Parallel execution of independent steps
- Resume capability after failures
- Automatic file organization (pending → completed/failed)
"""
import json
import re
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..core import Agent, Workflow, WorkflowResult


@dataclass
class BuildStep:
    """A single build step to execute."""
    id: str
    action: str  # create, modify, delete, run
    target: str
    description: str
    code_hint: str = ""
    dependencies: list[str] = field(default_factory=list)
    complexity: str = "simple"


@dataclass
class BuildPhase:
    """A phase containing multiple steps."""
    id: str
    name: str
    steps: list[BuildStep]
    can_parallelize: bool = False
    parallel_groups: list[list[str]] = field(default_factory=list)


@dataclass
class ParsedPlan:
    """Structured representation of a plan."""
    plan_id: str
    plan_type: str  # simple or master
    source_file: Path
    phases: list[BuildPhase]
    validation_commands: list[str]
    sub_features: list[dict] = field(default_factory=list)
    raw_content: str = ""


@dataclass
class StepResult:
    """Result of executing a single step."""
    step_id: str
    status: str  # completed, failed, skipped
    action_taken: str
    target: str
    summary: str
    files_affected: list[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class BuildState:
    """Tracks the current state of a build."""
    plan_id: str
    plan_file: str
    status: str  # pending, in_progress, completed, failed
    started_at: str
    current_phase: int = 0
    completed_steps: list[str] = field(default_factory=list)
    failed_steps: list[str] = field(default_factory=list)
    step_results: dict[str, dict] = field(default_factory=dict)
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "plan_file": self.plan_file,
            "status": self.status,
            "started_at": self.started_at,
            "current_phase": self.current_phase,
            "completed_steps": self.completed_steps,
            "failed_steps": self.failed_steps,
            "step_results": self.step_results,
            "files_created": self.files_created,
            "files_modified": self.files_modified,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BuildState":
        return cls(**data)


class BuildingWorkflow(Workflow):
    """
    Smart building workflow with parallel execution and progress tracking.

    For simple plans:
        Parser → Builder (sequential steps) → Tester → Reviewer

    For complex/master plans:
        Parser → Coordinator → [Parallel Builders] → Integrator → Tester → Reviewer

    Features:
    - Incremental building with checkpoint saves
    - Resume from failure
    - Parallel step execution
    - Automatic plan file organization
    """

    def __init__(
        self,
        project_root: Path,
        specs_dir: Optional[Path] = None,
        max_parallel: int = 3,
    ):
        self.project_root = project_root
        self.max_parallel = max_parallel
        self.specs_dir = specs_dir or project_root / ".specs"

        # Ensure directory structure
        self._ensure_specs_structure()

        super().__init__(name="Smart Building Workflow", output_dir=self.specs_dir)

        # Load all agents
        self._load_agents()

        # Build state
        self.build_state: Optional[BuildState] = None

    def _ensure_specs_structure(self):
        """Create the .specs directory structure."""
        dirs = ["pending", "in-progress", "completed", "failed"]
        for d in dirs:
            (self.specs_dir / d).mkdir(parents=True, exist_ok=True)

    def _load_agents(self):
        """Load all agents needed for building."""
        agents = ["parser", "builder", "tester", "reviewer", "coordinator", "integrator"]
        for agent_name in agents:
            try:
                self.register_agent(Agent.load(agent_name, self.project_root))
            except FileNotFoundError:
                self.console.print(f"[yellow]Warning: Agent '{agent_name}' not found[/yellow]")

    def _get_state_file(self, plan_path: Path) -> Path:
        """Get the state file path for a plan."""
        return plan_path.parent / f".{plan_path.stem}.state.json"

    def _save_state(self, plan_path: Path):
        """Save current build state."""
        if self.build_state:
            state_file = self._get_state_file(plan_path)
            state_file.write_text(
                json.dumps(self.build_state.to_dict(), indent=2),
                encoding="utf-8"
            )

    def _load_state(self, plan_path: Path) -> Optional[BuildState]:
        """Load existing build state if available."""
        state_file = self._get_state_file(plan_path)
        if state_file.exists():
            try:
                data = json.loads(state_file.read_text(encoding="utf-8"))
                return BuildState.from_dict(data)
            except Exception:
                return None
        return None

    def _move_plan(self, plan_path: Path, destination: str):
        """Move plan file to a destination folder."""
        dest_dir = self.specs_dir / destination
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest_path = dest_dir / plan_path.name

        # Handle state file too
        state_file = self._get_state_file(plan_path)
        if state_file.exists():
            dest_state = dest_dir / state_file.name
            shutil.move(str(state_file), str(dest_state))

        shutil.move(str(plan_path), str(dest_path))
        return dest_path

    def _parse_json_from_response(self, response: str) -> dict:
        """Extract JSON from agent response."""
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {}

    def _get_relevant_context(self, step: BuildStep) -> str:
        """Get relevant file context for a build step."""
        context_parts = []

        # If modifying a file, read it
        if step.action == "modify" and step.target:
            target_path = self.project_root / step.target
            if target_path.exists():
                try:
                    content = target_path.read_text(encoding="utf-8")
                    # Truncate for context protection
                    if len(content) > 3000:
                        content = content[:3000] + "\n... (truncated)"
                    context_parts.append(f"## Current content of {step.target}\n```\n{content}\n```")
                except Exception:
                    pass

        # Get directory context for creates
        if step.action == "create" and step.target:
            target_path = self.project_root / step.target
            parent = target_path.parent
            if parent.exists():
                try:
                    siblings = [f.name for f in parent.iterdir() if f.is_file()][:10]
                    context_parts.append(f"## Files in {parent.relative_to(self.project_root)}\n{', '.join(siblings)}")
                except Exception:
                    pass

        return "\n\n".join(context_parts) if context_parts else ""

    def _execute_step(self, step: BuildStep, phase_context: str) -> StepResult:
        """Execute a single build step using agentic builder."""
        step_context = self._get_relevant_context(step)

        full_context = f"""## Phase Context
{phase_context[:1500]}

## Step Context
{step_context}

## Code Hint from Plan
{step.code_hint[:1000] if step.code_hint else 'None provided'}
"""

        # Builder runs in agentic mode - it can actually write files
        result = self.run_agent(
            "builder",
            message=f"""Execute this build step:

**Action:** {step.action}
**Target:** {step.target}
**Description:** {step.description}

IMPORTANT: Actually create/modify the files as specified. Use the Write tool to create files, Edit tool to modify existing files.

After completing, summarize what you did.""",
            context=full_context,
            show_progress=False
        )

        if not result.success:
            return StepResult(
                step_id=step.id,
                status="failed",
                action_taken="none",
                target=step.target,
                summary="",
                error=result.error
            )

        # Get files from agentic result
        files_affected = []
        if result.files_created:
            files_affected.extend(result.files_created)
        if result.files_modified:
            files_affected.extend(result.files_modified)
        if not files_affected:
            files_affected = [step.target] if step.target else []

        # Determine action taken
        action_taken = step.action
        if result.files_created:
            action_taken = "created"
        elif result.files_modified:
            action_taken = "modified"

        return StepResult(
            step_id=step.id,
            status="completed",
            action_taken=action_taken,
            target=step.target,
            summary=result.content[:200] if result.content else f"Completed {step.action} on {step.target}",
            files_affected=files_affected,
            error=None
        )

    def _run_simple_build(self, plan: ParsedPlan, plan_path: Path) -> WorkflowResult:
        """Run sequential build for simple plans."""
        steps_completed = []

        for phase_idx, phase in enumerate(plan.phases):
            self.console.print(f"\n[bold]Phase {phase_idx + 1}/{len(plan.phases)}:[/bold] {phase.name}")

            self.build_state.current_phase = phase_idx
            self._save_state(plan_path)

            phase_context = f"Building phase: {phase.name}\nDescription: {phase.name}"

            for step in phase.steps:
                # Skip already completed
                if step.id in self.build_state.completed_steps:
                    self.console.print(f"  [dim]↷ {step.id} (already done)[/dim]")
                    continue

                self.console.print(f"  [cyan]→[/cyan] {step.description[:60]}...")

                result = self._execute_step(step, phase_context)

                # Track result
                self.build_state.step_results[step.id] = {
                    "status": result.status,
                    "summary": result.summary,
                    "files_affected": result.files_affected
                }

                if result.status == "completed":
                    self.build_state.completed_steps.append(step.id)
                    self.build_state.files_created.extend(
                        [f for f in result.files_affected if result.action_taken == "created"]
                    )
                    self.build_state.files_modified.extend(
                        [f for f in result.files_affected if result.action_taken == "modified"]
                    )
                    self.console.print(f"  [green]✓[/green] {result.summary[:50]}")
                    steps_completed.append(step.id)
                else:
                    self.build_state.failed_steps.append(step.id)
                    self.console.print(f"  [red]✗[/red] {result.error or 'Failed'}")
                    self._save_state(plan_path)
                    return WorkflowResult(
                        success=False,
                        error=f"Step {step.id} failed: {result.error}",
                        steps_completed=steps_completed
                    )

                self._save_state(plan_path)

            # Run tests after phase
            self.console.print(f"\n  [bold]Testing phase {phase_idx + 1}...[/bold]")
            test_result = self._run_phase_tests(plan, phase_idx)
            if not test_result:
                self.console.print("  [yellow]⚠[/yellow] Tests had issues (continuing)")

        # Final review
        self.console.print("\n[bold]Final Review...[/bold]")
        review_result = self._run_review(plan)

        return WorkflowResult(
            success=True,
            output_file=plan_path,
            steps_completed=steps_completed,
            data={
                "plan_type": "simple",
                "files_created": self.build_state.files_created,
                "files_modified": self.build_state.files_modified,
                "review": review_result
            }
        )

    def _build_phase_parallel(self, phase: BuildPhase, phase_context: str) -> list[StepResult]:
        """Build steps in a phase with parallelization."""
        results = []

        # Group steps for parallel execution
        if phase.parallel_groups:
            groups = phase.parallel_groups
        else:
            # Default: all steps can run in parallel
            groups = [[s.id for s in phase.steps]]

        for group in groups:
            group_steps = [s for s in phase.steps if s.id in group]

            if len(group_steps) <= 1:
                # Sequential for single step
                for step in group_steps:
                    if step.id not in self.build_state.completed_steps:
                        results.append(self._execute_step(step, phase_context))
            else:
                # Parallel execution
                with ThreadPoolExecutor(max_workers=self.max_parallel) as executor:
                    futures = {
                        executor.submit(self._execute_step, step, phase_context): step
                        for step in group_steps
                        if step.id not in self.build_state.completed_steps
                    }

                    for future in as_completed(futures):
                        step = futures[future]
                        try:
                            result = future.result()
                            results.append(result)
                            self.console.print(f"    [green]✓[/green] {step.id}: {result.summary[:40]}")
                        except Exception as e:
                            results.append(StepResult(
                                step_id=step.id,
                                status="failed",
                                action_taken="none",
                                target=step.target,
                                summary="",
                                error=str(e)
                            ))
                            self.console.print(f"    [red]✗[/red] {step.id}: {e}")

        return results

    def _run_complex_build(self, plan: ParsedPlan, plan_path: Path, coordination: dict) -> WorkflowResult:
        """Run coordinated parallel build for complex plans."""
        steps_completed = []
        execution_plan = coordination.get("execution_plan", [])

        for batch in execution_plan:
            batch_id = batch.get("batch_id", 0)
            phase_id = batch.get("phase", "unknown")
            step_ids = batch.get("steps", [])
            parallel = batch.get("parallel", False)

            # Find phase
            phase = next((p for p in plan.phases if p.id == phase_id), None)
            if not phase:
                continue

            self.console.print(f"\n[bold]Batch {batch_id}:[/bold] {phase.name}")
            self.console.print(f"  Steps: {len(step_ids)}, Parallel: {parallel}")

            phase_context = f"Phase: {phase.name}"
            steps_to_build = [s for s in phase.steps if s.id in step_ids]

            if parallel and len(steps_to_build) > 1:
                self.console.print(f"  Running {len(steps_to_build)} steps in parallel...")
                results = self._build_phase_parallel(
                    BuildPhase(
                        id=phase_id,
                        name=phase.name,
                        steps=steps_to_build,
                        can_parallelize=True
                    ),
                    phase_context
                )
            else:
                results = []
                for step in steps_to_build:
                    if step.id in self.build_state.completed_steps:
                        continue
                    self.console.print(f"  [cyan]→[/cyan] {step.description[:50]}...")
                    result = self._execute_step(step, phase_context)
                    results.append(result)

                    if result.status == "completed":
                        self.console.print("  [green]✓[/green] Done")
                    else:
                        self.console.print(f"  [red]✗[/red] {result.error}")

            # Process results
            for result in results:
                self.build_state.step_results[result.step_id] = {
                    "status": result.status,
                    "summary": result.summary
                }

                if result.status == "completed":
                    self.build_state.completed_steps.append(result.step_id)
                    steps_completed.append(result.step_id)
                else:
                    self.build_state.failed_steps.append(result.step_id)

            self._save_state(plan_path)

            # Check for failures
            failed = [r for r in results if r.status == "failed"]
            if failed:
                return WorkflowResult(
                    success=False,
                    error=f"Batch {batch_id} had {len(failed)} failures",
                    steps_completed=steps_completed
                )

        # Integration phase for master plans
        if plan.plan_type == "master" and plan.sub_features:
            self.console.print("\n[bold]Integration Phase...[/bold]")
            self._run_integration(plan)

        # Testing
        self.console.print("\n[bold]Final Testing...[/bold]")
        self._run_phase_tests(plan, -1)

        # Review
        self.console.print("\n[bold]Final Review...[/bold]")
        review_result = self._run_review(plan)

        return WorkflowResult(
            success=True,
            output_file=plan_path,
            steps_completed=steps_completed,
            data={
                "plan_type": "complex",
                "batches_executed": len(execution_plan),
                "files_created": self.build_state.files_created,
                "files_modified": self.build_state.files_modified,
                "review": review_result
            }
        )

    def _run_phase_tests(self, plan: ParsedPlan, phase_idx: int) -> bool:
        """Run tests after a phase."""
        commands = plan.validation_commands or ["echo 'No tests configured'"]

        result = self.run_agent(
            "tester",
            message=f"""Run validation for phase {phase_idx + 1}.

Validation commands from plan:
{chr(10).join(f'- {cmd}' for cmd in commands)}

Check that the implementation is working correctly.""",
            context=f"Completed steps: {', '.join(self.build_state.completed_steps[-5:])}",
            show_progress=False
        )

        return result.success

    def _run_integration(self, plan: ParsedPlan) -> bool:
        """Run integration for master plans."""
        sub_features_text = "\n".join([
            f"- {sf.get('name', 'Unknown')}: {sf.get('phase_ids', [])}"
            for sf in plan.sub_features
        ])

        result = self.run_agent(
            "integrator",
            message=f"""Integrate the sub-features that were built:

{sub_features_text}

Ensure all features work together correctly.""",
            context=f"Files created: {', '.join(self.build_state.files_created[:20])}",
            show_progress=True
        )

        return result.success

    def _run_review(self, plan: ParsedPlan) -> dict:
        """Run final code review."""
        result = self.run_agent(
            "reviewer",
            message=f"""Review the implementation of: {plan.plan_id}

Files created: {len(self.build_state.files_created)}
Files modified: {len(self.build_state.files_modified)}
Steps completed: {len(self.build_state.completed_steps)}

Provide a quality assessment.""",
            context=f"Plan type: {plan.plan_type}",
            show_progress=True
        )

        if result.success:
            return self._parse_json_from_response(result.content)
        return {"status": "skipped", "reason": "Reviewer failed"}

    def execute(self, plan_path_str: str) -> WorkflowResult:
        """
        Execute the building workflow for a plan file.

        Args:
            plan_path_str: Path to the plan file (relative or absolute)
        """
        # Resolve plan path
        plan_path = Path(plan_path_str)
        if not plan_path.is_absolute():
            plan_path = self.project_root / plan_path_str

        if not plan_path.exists():
            # Try in .specs directories
            for subdir in ["pending", "in-progress", ""]:
                test_path = self.specs_dir / subdir / plan_path.name if subdir else self.specs_dir / plan_path.name
                if test_path.exists():
                    plan_path = test_path
                    break

        if not plan_path.exists():
            return WorkflowResult(success=False, error=f"Plan not found: {plan_path}")

        self.console.print(f"[dim]Loading plan: {plan_path}[/dim]")

        # Load or create build state
        existing_state = self._load_state(plan_path)
        if existing_state and existing_state.completed_steps:
            self.console.print(f"[yellow]Resuming build ({len(existing_state.completed_steps)} steps done)[/yellow]")
            self.build_state = existing_state
            self.build_state.status = "in_progress"
        else:
            self.build_state = BuildState(
                plan_id=plan_path.stem,
                plan_file=str(plan_path),
                status="in_progress",
                started_at=datetime.now().isoformat()
            )

        # Move to in-progress
        if plan_path.parent.name != "in-progress":
            plan_path = self._move_plan(plan_path, "in-progress")
            self.build_state.plan_file = str(plan_path)

        self._save_state(plan_path)

        # Phase 1: Parse the plan
        self.console.print("\n[bold]Phase 1:[/bold] Parsing plan...")
        plan_content = plan_path.read_text(encoding="utf-8")

        parser_result = self.run_agent(
            "parser",
            message="Parse this implementation plan and extract structured build steps.",
            context=f"## Plan File: {plan_path.name}\n\n{plan_content[:8000]}"
        )

        if not parser_result.success:
            self._move_plan(plan_path, "failed")
            return WorkflowResult(success=False, error=f"Parser failed: {parser_result.error}")

        parsed_data = self._parse_json_from_response(parser_result.content)

        # Build ParsedPlan from response
        phases = []
        for phase_data in parsed_data.get("phases", []):
            steps = []
            for step_data in phase_data.get("steps", []):
                steps.append(BuildStep(
                    id=step_data.get("id", f"step-{len(steps)}"),
                    action=step_data.get("action", "create"),
                    target=step_data.get("target", ""),
                    description=step_data.get("description", ""),
                    code_hint=step_data.get("code_hint", ""),
                    dependencies=step_data.get("dependencies", []),
                    complexity=step_data.get("estimated_complexity", "simple")
                ))

            phases.append(BuildPhase(
                id=phase_data.get("id", f"phase-{len(phases)}"),
                name=phase_data.get("name", "Unknown Phase"),
                steps=steps,
                can_parallelize=phase_data.get("can_parallelize", False),
                parallel_groups=phase_data.get("parallel_groups", [])
            ))

        plan = ParsedPlan(
            plan_id=parsed_data.get("plan_id", plan_path.stem),
            plan_type=parsed_data.get("plan_type", "simple"),
            source_file=plan_path,
            phases=phases,
            validation_commands=parsed_data.get("validation_commands", []),
            sub_features=parsed_data.get("sub_features", []),
            raw_content=plan_content
        )

        total_steps = sum(len(p.steps) for p in phases)
        self.console.print(f"  Plan type: [cyan]{plan.plan_type}[/cyan]")
        self.console.print(f"  Phases: [cyan]{len(phases)}[/cyan]")
        self.console.print(f"  Total steps: [cyan]{total_steps}[/cyan]")

        # Decide: simple or complex build
        if plan.plan_type == "master" or total_steps > 15:
            # Complex build with coordination
            self.console.print("\n[bold]Phase 2:[/bold] Coordinating build...")

            coord_result = self.run_agent(
                "coordinator",
                message="Create an execution plan with batches for parallel building.",
                context=json.dumps(parsed_data, indent=2)[:5000]
            )

            if coord_result.success:
                coordination = self._parse_json_from_response(coord_result.content)
                result = self._run_complex_build(plan, plan_path, coordination)
            else:
                # Fallback to simple
                self.console.print("[yellow]Coordinator failed, using simple build[/yellow]")
                result = self._run_simple_build(plan, plan_path)
        else:
            # Simple sequential build
            result = self._run_simple_build(plan, plan_path)

        # Move plan based on result
        if result.success:
            self.build_state.status = "completed"
            self._save_state(plan_path)
            final_path = self._move_plan(plan_path, "completed")
            result.output_file = final_path
            self.console.print(f"\n[green]Plan moved to:[/green] {final_path}")
        else:
            self.build_state.status = "failed"
            self._save_state(plan_path)
            final_path = self._move_plan(plan_path, "failed")
            self.console.print(f"\n[red]Plan moved to:[/red] {final_path}")

        return result


def main():
    """CLI entry point."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m orchestrator.workflows.building <plan-file>")
        print("Example: python -m orchestrator.workflows.building .specs/pending/user-auth.md")
        sys.exit(1)

    plan_path = sys.argv[1]
    project_root = Path.cwd()

    workflow = BuildingWorkflow(project_root=project_root)
    result = workflow.run(plan_path)

    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
