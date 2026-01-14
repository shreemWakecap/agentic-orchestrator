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

from core import Agent, Workflow, WorkflowResult, get_agent_config


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
class StepState:
    """Tracks the state of a single step."""
    step_id: str
    status: str  # pending, in_progress, completed, failed, skipped
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    retry_count: int = 0
    error: Optional[str] = None
    files_affected: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "retry_count": self.retry_count,
            "error": self.error,
            "files_affected": self.files_affected,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StepState":
        return cls(**data)


@dataclass
class BuildState:
    """Tracks the current state of a build with step-level granularity."""
    plan_id: str
    plan_file: str
    status: str  # pending, building, completed, failed, paused
    started_at: str
    updated_at: str = ""
    current_phase: int = 0
    current_step: str = ""  # Current step being executed
    total_steps: int = 0
    completed_steps: list[str] = field(default_factory=list)
    failed_steps: list[str] = field(default_factory=list)
    skipped_steps: list[str] = field(default_factory=list)
    step_states: dict[str, dict] = field(default_factory=dict)  # step_id -> StepState
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    last_error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "plan_file": self.plan_file,
            "status": self.status,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "current_phase": self.current_phase,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps,
            "failed_steps": self.failed_steps,
            "skipped_steps": self.skipped_steps,
            "step_states": self.step_states,
            "files_created": self.files_created,
            "files_modified": self.files_modified,
            "last_error": self.last_error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BuildState":
        # Handle backwards compatibility
        if "step_results" in data and "step_states" not in data:
            # Migrate old format to new format
            data["step_states"] = {}
            for step_id, result in data.pop("step_results", {}).items():
                data["step_states"][step_id] = {
                    "step_id": step_id,
                    "status": result.get("status", "completed"),
                    "summary": result.get("summary", ""),
                    "files_affected": result.get("files_affected", []),
                }
        # Remove old fields if present
        data.pop("step_results", None)
        # Add new fields with defaults if missing
        data.setdefault("updated_at", data.get("started_at", ""))
        data.setdefault("current_step", "")
        data.setdefault("total_steps", 0)
        data.setdefault("skipped_steps", [])
        data.setdefault("step_states", {})
        data.setdefault("last_error", None)
        return cls(**data)

    def get_step_state(self, step_id: str) -> Optional[StepState]:
        """Get the state of a specific step."""
        if step_id in self.step_states:
            return StepState.from_dict(self.step_states[step_id])
        return None

    def set_step_state(self, step_state: StepState):
        """Update the state of a step."""
        self.step_states[step_state.step_id] = step_state.to_dict()
        self.updated_at = datetime.now().isoformat()

    def get_progress(self) -> tuple[int, int]:
        """Get (completed_count, total_count)."""
        return len(self.completed_steps), self.total_steps

    def can_retry_step(self, step_id: str, max_retries: int = 3) -> bool:
        """Check if a step can be retried."""
        state = self.get_step_state(step_id)
        if not state:
            return True
        return state.retry_count < max_retries


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
        max_parallel: Optional[int] = None,
    ):
        self.project_root = project_root
        self._config = get_agent_config(project_root)
        self.max_parallel = max_parallel or self._config.parallel.max_sub_features
        self.specs_dir = specs_dir or project_root / ".orchestrator" / "specs"

        # Ensure directory structure
        self._ensure_specs_structure()

        super().__init__(name="Smart Building Workflow", output_dir=self.specs_dir)

        # Load all agents
        self._load_agents()

        # Build state
        self.build_state: Optional[BuildState] = None

    def _ensure_specs_structure(self):
        """Create the specs directory structure."""
        # Main plan directories
        dirs = ["pending", "completed", "failed", "state"]
        for d in dirs:
            (self.specs_dir / d).mkdir(parents=True, exist_ok=True)
        # Note: "in-progress" is no longer used - plans stay in pending during build
        # State is tracked in specs/state/{plan_id}.state.json

    def _load_agents(self):
        """Load all agents needed for building."""
        agents = ["parser", "builder", "tester", "reviewer", "coordinator", "integrator"]
        for agent_name in agents:
            try:
                self.register_agent(Agent.load(agent_name, self.project_root))
            except FileNotFoundError:
                self.console.print(f"[yellow]Warning: Agent '{agent_name}' not found[/yellow]")

    def _verify_file_creation(self, files_affected: list[str], action: str) -> tuple[bool, str]:
        """
        Verify that files were actually created/modified by the builder.

        Args:
            files_affected: List of file paths that should have been affected
            action: The action type (create, modify, etc.)

        Returns:
            Tuple of (success, error_message)
        """
        if not files_affected:
            return True, ""  # No files to verify

        missing_files = []
        empty_files = []

        for file_path in files_affected:
            # Handle both absolute and relative paths
            if Path(file_path).is_absolute():
                full_path = Path(file_path)
            else:
                full_path = self.project_root / file_path

            if action in ("create", "created"):
                if not full_path.exists():
                    missing_files.append(file_path)
                elif full_path.stat().st_size == 0:
                    empty_files.append(file_path)
            elif action in ("modify", "modified"):
                if not full_path.exists():
                    missing_files.append(file_path)

        errors = []
        if missing_files:
            errors.append(f"Files not created: {', '.join(missing_files)}")
        if empty_files:
            errors.append(f"Files are empty: {', '.join(empty_files)}")

        if errors:
            return False, "; ".join(errors)
        return True, ""

    def _is_placeholder_response(self, content: str) -> bool:
        """
        DEPRECATED: Placeholder detection is now handled in agent.py.
        Kept for backwards compatibility.
        """
        if not content or len(content.strip()) < 50:
            return True

        placeholder_patterns = [
            # Generic greetings
            "I'm ready to help you",
            "I'll help you with software engineering",
            "How can I help you",
            "What can I help",
            "Hello! How can I help",
            # Confusion indicators
            "What would you like me to",
            "What would you like to work on",
            "Would you like me to",
            "I understand you've sent",
            "I understand. I'm ready to help",
            "I can see you're on the",
            "I can see you're working",
            # Empty message indicators
            "I see you've sent",
            "I see you've started",
            "you've sent an empty message",
            # Context confusion
            "working in the",
            "on the developmet branch",
            "in your git working tree",
            "Let me know what you'd like",
        ]

        content_lower = content.lower()
        for pattern in placeholder_patterns:
            if pattern.lower() in content_lower:
                return True

        return False

    def _validate_agent_response(self, agent_name: str, result) -> tuple[bool, str]:
        """
        Validate that an agent response is successful and contains content.

        Note: The agent module now handles placeholder detection and retries internally.
        This method primarily checks for explicit failures.

        Args:
            agent_name: Name of the agent for error messages
            result: AgentResult object

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not result.success:
            return False, f"{agent_name} failed: {result.error}"

        if not result.content or len(result.content.strip()) < 50:
            return False, f"{agent_name} returned empty or too short response"

        # Check if agent flagged this as a potential placeholder (warning in error field)
        if result.error and "placeholder" in result.error.lower():
            # Agent already retried and couldn't get good output - fail
            return False, (
                f"{agent_name} returned a placeholder response after retries. "
                f"Details: {result.error}"
            )

        return True, ""

    def _get_state_file(self, plan_path: Path) -> Path:
        """Get the centralized state file path for a plan."""
        # State files are stored in specs/state/{plan_id}.state.json
        return self.specs_dir / "state" / f"{plan_path.stem}.state.json"

    def _save_state(self, plan_path: Path):
        """Save current build state to centralized location."""
        if self.build_state:
            self.build_state.updated_at = datetime.now().isoformat()
            state_file = self._get_state_file(plan_path)
            state_file.parent.mkdir(parents=True, exist_ok=True)
            state_file.write_text(
                json.dumps(self.build_state.to_dict(), indent=2),
                encoding="utf-8"
            )

    def _load_state(self, plan_path: Path) -> Optional[BuildState]:
        """Load existing build state from centralized location."""
        state_file = self._get_state_file(plan_path)
        if state_file.exists():
            try:
                data = json.loads(state_file.read_text(encoding="utf-8"))
                return BuildState.from_dict(data)
            except Exception as e:
                self.console.print(f"[yellow]Warning: Could not load state file: {e}[/yellow]")
                return None

        # Backwards compatibility: check old location (hidden file in plan directory)
        old_state_file = plan_path.parent / f".{plan_path.stem}.state.json"
        if old_state_file.exists():
            try:
                data = json.loads(old_state_file.read_text(encoding="utf-8"))
                state = BuildState.from_dict(data)
                # Migrate to new location
                self.build_state = state
                self._save_state(plan_path)
                old_state_file.unlink()  # Remove old file
                self.console.print("[dim]Migrated state file to centralized location[/dim]")
                return state
            except Exception:
                pass
        return None

    def _load_plan_content(self, plan_path: Path) -> str:
        """
        Load plan content from either a single file or a folder-based plan.

        For folder-based plans (e.g., 001_feature-name/), reads all .md files
        in sorted order and concatenates them.

        For single-file plans, returns the file content directly.

        Args:
            plan_path: Path to plan file or directory

        Returns:
            Combined plan content as a single string
        """
        if plan_path.is_dir():
            # Folder-based plan - read all .md files in sorted order
            md_files = sorted(plan_path.glob("*.md"))
            if not md_files:
                raise ValueError(f"No .md files found in plan folder: {plan_path}")

            contents = []
            for md_file in md_files:
                file_content = md_file.read_text(encoding="utf-8")
                # Add file header for context
                contents.append(f"<!-- File: {md_file.name} -->\n{file_content}")

            return "\n\n---\n\n".join(contents)
        else:
            # Single file plan (legacy format)
            return plan_path.read_text(encoding="utf-8")

    def _archive_plan(self, plan_path: Path, destination: str) -> Path:
        """
        Archive a plan to completed or failed folder.

        This should ONLY be called when a build is fully complete or has
        permanently failed. Plans stay in pending during active building.
        State is tracked separately in specs/state/.

        Args:
            plan_path: Path to the plan folder
            destination: Either "completed" or "failed"

        Returns:
            New path to the archived plan
        """
        if destination not in ("completed", "failed"):
            raise ValueError(f"Invalid archive destination: {destination}")

        dest_dir = self.specs_dir / destination
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest_path = dest_dir / plan_path.name

        # If destination already exists, remove it first (re-running failed plan)
        if dest_path.exists():
            shutil.rmtree(str(dest_path))

        # Move the plan folder
        shutil.move(str(plan_path), str(dest_path))

        # Update state file to reflect new location
        if self.build_state:
            self.build_state.plan_file = str(dest_path)
            self._save_state(dest_path)

        return dest_path

    def _get_plan_status(self, plan_path: Path) -> str:
        """
        Get the current status of a plan based on state file.

        Returns: pending, building, completed, failed, or unknown
        """
        state = self._load_state(plan_path)
        if state:
            return state.status
        return "pending"

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

    def _validate_parsed_structure(self, parsed_data: dict) -> tuple[bool, str]:
        """
        Validate that parser output has the expected structure.

        Args:
            parsed_data: The parsed JSON from the parser agent

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not parsed_data:
            return False, "Parser returned empty or invalid JSON"

        if not isinstance(parsed_data, dict):
            return False, f"Parser returned {type(parsed_data).__name__} instead of dict"

        # Check for phases
        phases = parsed_data.get("phases", [])
        if not isinstance(phases, list):
            return False, "Parser 'phases' field is not a list"

        if not phases:
            return False, "Parser returned no phases in the plan"

        # Validate each phase structure
        for i, phase in enumerate(phases):
            if not isinstance(phase, dict):
                return False, f"Phase {i} is not a dict"

            steps = phase.get("steps", [])
            if not isinstance(steps, list):
                return False, f"Phase {i} 'steps' is not a list"

            # Validate each step structure
            for j, step in enumerate(steps):
                if not isinstance(step, dict):
                    return False, f"Phase {i} step {j} is not a dict"

                # Must have at least action and target or description
                if not step.get("action") and not step.get("description"):
                    return False, f"Phase {i} step {j} has no action or description"

        return True, ""

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

        # Validate builder response (check for success AND placeholder detection)
        valid, error = self._validate_agent_response("Builder", result)
        if not valid:
            return StepResult(
                step_id=step.id,
                status="failed",
                action_taken="none",
                target=step.target,
                summary="",
                error=error
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

        # Verify files were actually created/modified
        if files_affected and action_taken in ("create", "created", "modify", "modified"):
            verified, verify_error = self._verify_file_creation(files_affected, action_taken)
            if not verified:
                return StepResult(
                    step_id=step.id,
                    status="failed",
                    action_taken=action_taken,
                    target=step.target,
                    summary=f"Builder reported success but verification failed: {verify_error}",
                    files_affected=files_affected,
                    error=f"File verification failed: {verify_error}"
                )

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
        """Run sequential build for simple plans with step-level tracking."""
        from core.symbols import ARROW_RIGHT, CHECK, CROSS, WARNING

        steps_completed = []

        for phase_idx, phase in enumerate(plan.phases):
            self.console.print(f"\n[bold]Phase {phase_idx + 1}/{len(plan.phases)}:[/bold] {phase.name}")

            self.build_state.current_phase = phase_idx
            self._save_state(plan_path)

            phase_context = f"Building phase: {phase.name}\nDescription: {phase.name}"

            for step in phase.steps:
                # Check step state for resume capability
                existing_step_state = self.build_state.get_step_state(step.id)

                # Skip already completed steps
                if step.id in self.build_state.completed_steps:
                    self.console.print(f"  [dim]↷ {step.id} (already done)[/dim]")
                    continue

                # Check if step previously failed - attempt retry
                if step.id in self.build_state.failed_steps:
                    if not self.build_state.can_retry_step(step.id):
                        self.console.print(f"  [red]{CROSS}[/red] {step.id} (max retries exceeded)")
                        continue
                    retry_count = existing_step_state.retry_count if existing_step_state else 0
                    self.console.print(f"  [yellow]↻[/yellow] Retrying {step.id} (attempt {retry_count + 1})...")
                    # Remove from failed list for retry
                    self.build_state.failed_steps.remove(step.id)

                # Mark step as in_progress
                self.build_state.current_step = step.id
                step_state = StepState(
                    step_id=step.id,
                    status="in_progress",
                    started_at=datetime.now().isoformat(),
                    retry_count=(existing_step_state.retry_count if existing_step_state else 0)
                )
                self.build_state.set_step_state(step_state)
                self._save_state(plan_path)

                # Display progress
                completed, total = self.build_state.get_progress()
                progress_str = f"[{completed}/{total}]"
                self.console.print(f"  [cyan]{ARROW_RIGHT}[/cyan] {progress_str} {step.description[:55]}...")

                # Execute the step
                result = self._execute_step(step, phase_context)

                # Update step state based on result
                step_state.completed_at = datetime.now().isoformat()
                step_state.files_affected = result.files_affected
                step_state.summary = result.summary

                if result.status == "completed":
                    step_state.status = "completed"
                    self.build_state.set_step_state(step_state)
                    self.build_state.completed_steps.append(step.id)
                    self.build_state.files_created.extend(
                        [f for f in result.files_affected if result.action_taken == "created"]
                    )
                    self.build_state.files_modified.extend(
                        [f for f in result.files_affected if result.action_taken == "modified"]
                    )
                    self.console.print(f"  [green]{CHECK}[/green] {result.summary[:50]}")
                    steps_completed.append(step.id)
                else:
                    step_state.status = "failed"
                    step_state.error = result.error
                    step_state.retry_count += 1
                    self.build_state.set_step_state(step_state)
                    self.build_state.failed_steps.append(step.id)
                    self.build_state.last_error = f"Step {step.id}: {result.error}"
                    self.build_state.status = "paused"  # Paused, not failed - can resume
                    self._save_state(plan_path)

                    self.console.print(f"  [red]{CROSS}[/red] {result.error or 'Failed'}")
                    self.console.print(f"\n[yellow]Build paused at step {step.id}[/yellow]")
                    self.console.print(f"[dim]Run build again to retry from this step[/dim]")

                    return WorkflowResult(
                        success=False,
                        error=f"Step {step.id} failed: {result.error}",
                        steps_completed=steps_completed,
                        data={
                            "paused_at": step.id,
                            "can_resume": True,
                            "completed_steps": len(self.build_state.completed_steps),
                            "total_steps": self.build_state.total_steps,
                        }
                    )

                self._save_state(plan_path)

            # Run tests after phase
            self.console.print(f"\n  [bold]Testing phase {phase_idx + 1}...[/bold]")
            test_result = self._run_phase_tests(plan, phase_idx)
            if not test_result:
                self.console.print(f"  [yellow]{WARNING}[/yellow] Tests had issues (continuing)")

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

    def _resolve_step_dependencies(self, steps: list[BuildStep]) -> list[list[BuildStep]]:
        """
        Sort steps into execution waves based on dependencies.

        Returns list of waves - steps in each wave can run in parallel,
        but waves must execute sequentially.
        """
        if not steps:
            return []

        # Build dependency graph
        step_map = {s.id: s for s in steps}
        completed = set(self.build_state.completed_steps)
        remaining = {s.id for s in steps if s.id not in completed}

        waves: list[list[BuildStep]] = []

        # Keep resolving until all steps are scheduled
        max_iterations = len(steps) + 1
        for _ in range(max_iterations):
            if not remaining:
                break

            # Find steps whose dependencies are all satisfied
            ready = []
            for step_id in list(remaining):
                step = step_map[step_id]
                deps = set(step.dependencies)
                # Dependencies satisfied if they're completed or not in our step list
                if deps.issubset(completed | (set(step_map.keys()) - remaining)):
                    ready.append(step)

            if not ready:
                # Circular dependency or unresolvable - just run remaining sequentially
                for step_id in remaining:
                    waves.append([step_map[step_id]])
                break

            waves.append(ready)
            for step in ready:
                remaining.discard(step.id)
                completed.add(step.id)

        return waves

    def _build_phase_parallel(self, phase: BuildPhase, phase_context: str) -> list[StepResult]:
        """Build steps in a phase with parallelization and dependency resolution."""
        results = []

        from core.symbols import CHECK, CROSS

        # First, resolve dependencies to get execution waves
        if any(s.dependencies for s in phase.steps):
            # Steps have explicit dependencies - resolve them
            waves = self._resolve_step_dependencies(phase.steps)
        elif phase.parallel_groups:
            # Use explicit parallel groups as waves
            waves = []
            for group in phase.parallel_groups:
                group_steps = [s for s in phase.steps if s.id in group]
                if group_steps:
                    waves.append(group_steps)
        else:
            # Default: all steps in single wave (can run in parallel)
            waves = [phase.steps]

        for wave_idx, wave in enumerate(waves):
            # Filter out already completed steps
            pending_steps = [s for s in wave if s.id not in self.build_state.completed_steps]

            if not pending_steps:
                continue

            if len(pending_steps) == 1:
                # Sequential for single step
                step = pending_steps[0]
                result = self._execute_step(step, phase_context)
                results.append(result)
                if result.status == "completed":
                    self.console.print(f"    [green]{CHECK}[/green] {step.id}: {result.summary[:40]}")
                else:
                    self.console.print(f"    [red]{CROSS}[/red] {step.id}: {result.error or 'Failed'}")
            else:
                # Parallel execution within wave
                with ThreadPoolExecutor(max_workers=self.max_parallel) as executor:
                    futures = {
                        executor.submit(self._execute_step, step, phase_context): step
                        for step in pending_steps
                    }

                    for future in as_completed(futures):
                        step = futures[future]
                        try:
                            result = future.result()
                            results.append(result)
                            if result.status == "completed":
                                self.console.print(f"    [green]{CHECK}[/green] {step.id}: {result.summary[:40]}")
                            else:
                                self.console.print(f"    [red]{CROSS}[/red] {step.id}: {result.error or 'Failed'}")
                        except Exception as e:
                            results.append(StepResult(
                                step_id=step.id,
                                status="failed",
                                action_taken="none",
                                target=step.target,
                                summary="",
                                error=str(e)
                            ))
                            self.console.print(f"    [red]{CROSS}[/red] {step.id}: {e}")

        return results

    def _run_complex_build(self, plan: ParsedPlan, plan_path: Path, coordination: dict) -> WorkflowResult:
        """Run coordinated parallel build for complex plans with step-level tracking."""
        from core.symbols import ARROW_RIGHT, CHECK, CROSS

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
                    # Skip completed steps
                    if step.id in self.build_state.completed_steps:
                        self.console.print(f"  [dim]↷ {step.id} (already done)[/dim]")
                        continue

                    # Track step state
                    existing_step_state = self.build_state.get_step_state(step.id)
                    self.build_state.current_step = step.id
                    step_state = StepState(
                        step_id=step.id,
                        status="in_progress",
                        started_at=datetime.now().isoformat(),
                        retry_count=(existing_step_state.retry_count if existing_step_state else 0)
                    )
                    self.build_state.set_step_state(step_state)
                    self._save_state(plan_path)

                    # Display progress
                    completed, total = self.build_state.get_progress()
                    self.console.print(f"  [cyan]{ARROW_RIGHT}[/cyan] [{completed}/{total}] {step.description[:50]}...")

                    result = self._execute_step(step, phase_context)
                    results.append(result)

                    # Update step state
                    step_state.completed_at = datetime.now().isoformat()
                    step_state.files_affected = result.files_affected
                    step_state.summary = result.summary

                    if result.status == "completed":
                        step_state.status = "completed"
                        self.console.print(f"  [green]{CHECK}[/green] Done")
                    else:
                        step_state.status = "failed"
                        step_state.error = result.error
                        step_state.retry_count += 1
                        self.console.print(f"  [red]{CROSS}[/red] {result.error}")

                    self.build_state.set_step_state(step_state)

            # Process results
            for result in results:
                if result.status == "completed":
                    if result.step_id not in self.build_state.completed_steps:
                        self.build_state.completed_steps.append(result.step_id)
                    steps_completed.append(result.step_id)
                else:
                    if result.step_id not in self.build_state.failed_steps:
                        self.build_state.failed_steps.append(result.step_id)

            self._save_state(plan_path)

            # Check for failures - pause build for resume
            failed = [r for r in results if r.status == "failed"]
            if failed:
                self.build_state.status = "paused"
                self.build_state.last_error = f"Batch {batch_id}: {len(failed)} step(s) failed"
                self._save_state(plan_path)

                self.console.print(f"\n[yellow]Build paused at batch {batch_id}[/yellow]")
                self.console.print(f"[dim]Run build again to retry failed steps[/dim]")

                return WorkflowResult(
                    success=False,
                    error=f"Batch {batch_id} had {len(failed)} failures",
                    steps_completed=steps_completed,
                    data={
                        "paused_at": f"batch-{batch_id}",
                        "can_resume": True,
                        "completed_steps": len(self.build_state.completed_steps),
                        "total_steps": self.build_state.total_steps,
                    }
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

        Plans stay in their current location during building. State is tracked
        in a centralized state file. Plans only move to completed/failed when
        fully done.

        Args:
            plan_path_str: Path to the plan file (relative or absolute)
        """
        # Resolve plan path
        plan_path = Path(plan_path_str)
        if not plan_path.is_absolute():
            plan_path = self.project_root / plan_path_str

        if not plan_path.exists():
            # Try in specs directories (pending first, then others)
            for subdir in ["pending", "failed", "completed", ""]:
                test_path = self.specs_dir / subdir / plan_path.name if subdir else self.specs_dir / plan_path.name
                if test_path.exists():
                    plan_path = test_path
                    break

        if not plan_path.exists():
            return WorkflowResult(success=False, error=f"Plan not found: {plan_path}")

        # Use forward slashes for display (Rich console on Windows)
        plan_display = str(plan_path).replace("\\", "/")
        self.console.print(f"[dim]Loading plan: {plan_display}[/dim]")

        # Load or create build state
        existing_state = self._load_state(plan_path)
        if existing_state:
            completed_count = len(existing_state.completed_steps)
            failed_count = len(existing_state.failed_steps)
            total = existing_state.total_steps

            if existing_state.status == "paused":
                self.console.print(f"[yellow]Resuming paused build[/yellow]")
                self.console.print(f"  Progress: {completed_count}/{total} steps completed")
                if failed_count > 0:
                    self.console.print(f"  Failed steps to retry: {failed_count}")
                if existing_state.last_error:
                    self.console.print(f"  Last error: [dim]{existing_state.last_error[:60]}...[/dim]")
            elif completed_count > 0:
                self.console.print(f"[yellow]Resuming build ({completed_count}/{total} steps done)[/yellow]")

            self.build_state = existing_state
            self.build_state.status = "building"
        else:
            self.build_state = BuildState(
                plan_id=plan_path.stem,
                plan_file=str(plan_path),
                status="building",
                started_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            )

        self._save_state(plan_path)

        # Phase 1: Parse the plan
        self.console.print("\n[bold]Phase 1:[/bold] Parsing plan...")
        plan_content = self._load_plan_content(plan_path)

        # Validate plan has actual content (not just headers)
        content_lines = [
            line for line in plan_content.split('\n')
            if line.strip() and not line.startswith('#') and not line.startswith('*') and not line.startswith('>')  and not line.startswith('---')
        ]
        if len(content_lines) < 5:
            self.build_state.status = "failed"
            self.build_state.last_error = "Plan is empty or incomplete"
            self._save_state(plan_path)
            return WorkflowResult(
                success=False,
                error=f"Plan appears to be empty or incomplete. Expected implementation steps but found only {len(content_lines)} content lines. Please re-run the planning workflow to generate a complete plan."
            )

        parser_result = self.run_agent(
            "parser",
            message="Parse this implementation plan and extract structured build steps.",
            context=f"## Plan File: {plan_path.name}\n\n{plan_content[:8000]}"
        )

        # Validate parser response (check for success AND placeholder detection)
        valid, error = self._validate_agent_response("Parser", parser_result)
        if not valid:
            self.build_state.status = "failed"
            self.build_state.last_error = error
            self._save_state(plan_path)
            return WorkflowResult(success=False, error=error)

        parsed_data = self._parse_json_from_response(parser_result.content)

        # Validate parser output structure
        valid, error = self._validate_parsed_structure(parsed_data)
        if not valid:
            self.build_state.status = "failed"
            self.build_state.last_error = error
            self._save_state(plan_path)
            return WorkflowResult(success=False, error=error)

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
        from core.symbols import CHECK
        self.console.print(f"  [green]{CHECK}[/green] parser complete")
        self.console.print(f"  Plan type: [cyan]{plan.plan_type}[/cyan]")
        self.console.print(f"  Phases: [cyan]{len(phases)}[/cyan]")
        self.console.print(f"  Total steps: [cyan]{total_steps}[/cyan]")

        # Store total steps in build state for progress tracking
        self.build_state.total_steps = total_steps
        self._save_state(plan_path)

        # CRITICAL: Fail if no steps were extracted from the plan
        if total_steps == 0:
            self.build_state.status = "failed"
            self.build_state.last_error = "No implementation steps found in plan"
            self._save_state(plan_path)
            return WorkflowResult(
                success=False,
                error=(
                    "Parser could not extract any implementation steps from the plan. "
                    "The plan may be incomplete, empty, or malformed. "
                    "Please re-run the planning workflow to generate a complete plan with actionable steps."
                )
            )

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

        # Handle result - only archive on full completion
        if result.success:
            self.build_state.status = "completed"
            self.build_state.current_step = ""
            self._save_state(plan_path)

            # Archive to completed folder
            final_path = self._archive_plan(plan_path, "completed")
            result.output_file = final_path
            final_display = str(final_path).replace("\\", "/")

            completed, total = self.build_state.get_progress()
            self.console.print(f"\n[green]Build completed successfully![/green]")
            self.console.print(f"  Steps: {completed}/{total}")
            self.console.print(f"  Files created: {len(self.build_state.files_created)}")
            self.console.print(f"  Files modified: {len(self.build_state.files_modified)}")
            self.console.print(f"  Archived to: {final_display}")
        else:
            # Check if this is a pausable failure (can resume) or permanent failure
            is_paused = result.data and result.data.get("can_resume", False)

            if is_paused:
                # Build is paused - state already saved, plan stays in place
                self.console.print(f"\n[yellow]Build paused - can be resumed[/yellow]")
                completed, total = self.build_state.get_progress()
                self.console.print(f"  Progress: {completed}/{total} steps completed")
                self.console.print(f"  State saved to: specs/state/{plan_path.stem}.state.json")
                self.console.print(f"\n[dim]Run 'build {plan_path.name}' again to resume[/dim]")
            else:
                # Permanent failure - archive to failed
                self.build_state.status = "failed"
                self._save_state(plan_path)

                final_path = self._archive_plan(plan_path, "failed")
                final_display = str(final_path).replace("\\", "/")
                self.console.print(f"\n[red]Build failed permanently[/red]")
                self.console.print(f"  Archived to: {final_display}")

        return result


def main():
    """CLI entry point."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m orchestrator.workflows.building <plan-file>")
        print("Example: python -m orchestrator.workflows.building .orchestrator/specs/pending/user-auth.md")
        sys.exit(1)

    plan_path = sys.argv[1]
    project_root = Path.cwd()

    workflow = BuildingWorkflow(project_root=project_root)
    result = workflow.run(plan_path)

    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
