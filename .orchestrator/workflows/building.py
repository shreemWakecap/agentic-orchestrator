"""
Smart Building Workflow: Executes implementation plans with parallel sub-agents.

For simple plans: Parser → Builder (per step) → Tester → Goal-Verifier
For complex/master plans: Parser → Coordinator → [Parallel Builders] → Integrator → Tester → Goal-Verifier

Features:
- Incremental building with progress tracking (state in SQLite database)
- Parallel execution of independent steps
- Resume capability after failures
- Automatic status updates in database (pending → completed/failed)
"""
import json
import re
import shutil
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from core import Agent, Workflow, WorkflowResult, get_agent_config
from core.plan_parser import PlanParser, ParseResult
from db import get_plan_repository, get_build_state_repository


@dataclass
class BuildStep:
    """A single build step to execute."""
    id: str
    action: str  # create, modify, delete, run
    target: str
    description: str
    done: str = ""  # Verification criteria for this step
    inputs: list[str] = field(default_factory=list)  # Input files
    dependencies: list[str] = field(default_factory=list)
    complexity: str = "simple"
    parallel_group: Optional[str] = None  # Group name for parallel execution


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
class GoalContext:
    """
    Tracks the GOAL and verification status for goal-oriented building.

    The builder should work until the GOAL is achieved, not just until
    the plan steps are executed.
    """
    goal: str  # What success looks like (from plan's GOAL section)
    original_request: str  # The full user request
    verify_commands: list[str]  # Commands to verify success
    context_notes: list[str] = field(default_factory=list)  # Key context
    goal_achieved: bool = False
    verification_attempts: int = 0
    max_verification_attempts: int = 3
    missing_items: list[str] = field(default_factory=list)  # What's still needed
    completion_percentage: int = 0  # Estimated % complete

    def to_dict(self) -> dict:
        return {
            "goal": self.goal,
            "original_request": self.original_request,
            "verify_commands": self.verify_commands,
            "context_notes": self.context_notes,
            "goal_achieved": self.goal_achieved,
            "verification_attempts": self.verification_attempts,
            "missing_items": self.missing_items,
            "completion_percentage": self.completion_percentage,
        }


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
        Parser → Builder (sequential steps) → Tester → Goal-Verifier

    For complex/master plans:
        Parser → Coordinator → [Parallel Builders] → Integrator → Tester → Goal-Verifier

    Features:
    - Incremental building with progress tracking
    - Resume from failure (state saved in SQLite database)
    - Parallel step execution
    - Goal-oriented verification loop
    """

    def __init__(
        self,
        project_root: Path,
        max_parallel: Optional[int] = None,
    ):
        self.project_root = project_root
        self._config = get_agent_config(project_root)
        self.max_parallel = max_parallel or self._config.parallel.max_sub_features

        # Database repositories
        self._plan_repo = get_plan_repository()
        self._build_state_repo = get_build_state_repository()

        super().__init__(name="Smart Building Workflow")

        # Load all agents
        self._load_agents()

        # Build state
        self.build_state: Optional[BuildState] = None
        self._current_plan_id: Optional[str] = None

        # Async test execution
        self._test_executor: Optional[ThreadPoolExecutor] = None
        self._test_futures: list[Future] = []

    def _load_agents(self):
        """Load all agents needed for building."""
        # Note: parser agent removed - using deterministic core/plan_parser.py
        required = ["builder", "goal-verifier"]
        optional = ["tester", "coordinator", "integrator"]

        for agent_name in required + optional:
            try:
                self.register_agent(Agent.load(agent_name, self.project_root))
            except FileNotFoundError:
                if agent_name in required:
                    self.console.print(f"[yellow]Warning: Agent '{agent_name}' not found[/yellow]")

    def _extract_goal_context(self, plan_content: str) -> GoalContext:
        """
        Extract goal, request, and verification commands from plan content.

        Returns a GoalContext object that tracks what we're trying to achieve.
        """
        # Extract GOAL section
        goal_match = re.search(r'(?:^|\n)##?\s*Goal\s*\n+(.*?)(?=\n##|\n\*\*|$)', plan_content, re.DOTALL | re.IGNORECASE)
        goal = goal_match.group(1).strip() if goal_match else ""

        # Extract original request
        request_match = re.search(r'Request:\s*(.+?)(?:\n|Complexity:)', plan_content, re.DOTALL)
        original_request = request_match.group(1).strip() if request_match else ""

        # Extract VERIFY commands
        verify_match = re.search(r'(?:^|\n)##?\s*Verify\s*\n+(.*?)(?=\n##|$)', plan_content, re.DOTALL | re.IGNORECASE)
        verify_section = verify_match.group(1).strip() if verify_match else ""
        verify_commands = [
            line.strip().lstrip('- ').lstrip('* ')
            for line in verify_section.split('\n')
            if line.strip() and line.strip().startswith(('-', '*'))
        ]

        # Extract CONTEXT notes
        context_match = re.search(r'(?:^|\n)##?\s*Context\s*\n+(.*?)(?=\n##|$)', plan_content, re.DOTALL | re.IGNORECASE)
        context_section = context_match.group(1).strip() if context_match else ""
        context_notes = [
            line.strip().lstrip('- ').lstrip('* ')
            for line in context_section.split('\n')
            if line.strip() and line.strip().startswith(('-', '*'))
        ]

        return GoalContext(
            goal=goal,
            original_request=original_request,
            verify_commands=verify_commands,
            context_notes=context_notes
        )

    def _verify_goal_achieved(self, goal_context: GoalContext) -> tuple[bool, list[str]]:
        """
        Verify if the GOAL has been achieved by analyzing the implementation.

        Uses the goal-verifier agent to check:
        1. Are all files from the request created?
        2. Do they contain the expected functionality?
        3. Do verification commands pass?

        Returns:
            Tuple of (goal_achieved, list_of_missing_items)
        """
        from core.symbols import CHECK, CROSS, WARNING

        self.console.print("\n[bold]Goal Verification:[/bold] Checking if goal is achieved...")

        # Collect all files affected from completed steps
        all_files = set()
        for step_id in self.build_state.completed_steps:
            step_state = self.build_state.step_states.get(step_id)
            if step_state:
                # Handle both StepState objects and dicts
                files = getattr(step_state, 'files_affected', None) or step_state.get('files_affected', [])
                if files:
                    all_files.update(files)

        # Build verification context
        criteria_section = ""
        if goal_context.verify_commands:
            criteria_section = f"""
## VERIFICATION CRITERIA
{chr(10).join(f'- {cmd}' for cmd in goal_context.verify_commands)}
"""

        files_list = ', '.join(sorted(all_files)) if all_files else 'None'
        verification_prompt = f"""Analyze if the following GOAL has been fully achieved:

## GOAL
{goal_context.goal}

## ORIGINAL REQUEST
{goal_context.original_request}
{criteria_section}
## FILES AFFECTED
{files_list}

## TASK
1. Check if all numbered requirements from the request are implemented
2. Verify the files exist and contain proper implementation (not empty/placeholder)
3. Identify any MISSING items that still need to be done

Respond in this format:
ACHIEVED: yes|no
COMPLETION: [0-100]%
MISSING:
- [item 1 that's missing]
- [item 2 that's missing]
NOTES: [Brief explanation]
"""

        # Use goal-verifier agent for goal verification
        agent_name = "goal-verifier"
        if agent_name not in self.agents:
            self.console.print(f"  [yellow]{WARNING}[/yellow] Goal-verifier agent not available")
            return False, ["Goal-verifier agent not found"]

        result = self.run_agent(
            agent_name,
            message=verification_prompt,
            context=f"Build completed {len(self.build_state.completed_steps)} steps",
            show_progress=False
        )

        if not result.success:
            self.console.print(f"  [yellow]{WARNING}[/yellow] Could not verify goal (agent failed)")
            return False, ["Verification failed - unable to assess"]

        # Parse KEY: VALUE result
        parsed = self._parse_key_value(result.content)
        # Convert yes/no to bool
        achieved_str = str(parsed.get("achieved", "no")).lower()
        goal_achieved = achieved_str in ("yes", "true", "1")
        missing_items = parsed.get("missing", [])
        # Parse completion percentage (strip % if present)
        completion_str = str(parsed.get("completion", "0")).rstrip('%')
        try:
            completion_pct = int(completion_str)
        except ValueError:
            completion_pct = 0
        notes = parsed.get("notes", "")

        goal_context.completion_percentage = completion_pct
        goal_context.missing_items = missing_items

        if goal_achieved:
            self.console.print(f"  [green]{CHECK}[/green] Goal achieved! ({completion_pct}% complete)")
        else:
            self.console.print(f"  [red]{CROSS}[/red] Goal NOT achieved ({completion_pct}% complete)")
            if missing_items:
                self.console.print(f"  Missing items:")
                for item in missing_items[:5]:
                    self.console.print(f"    - {item[:60]}")
            if notes:
                self.console.print(f"  Notes: {notes[:100]}")

        return goal_achieved, missing_items

    def _generate_completion_steps(self, goal_context: GoalContext) -> list[BuildStep]:
        """
        Generate additional steps to complete the goal based on what's missing.

        Uses the planner agent to create steps for missing items.
        """
        if not goal_context.missing_items:
            return []

        from core.symbols import CHECK

        self.console.print("\n[bold]Generating Completion Steps:[/bold]")

        missing_summary = "\n".join(f"- {item}" for item in goal_context.missing_items)

        # Use planner to generate steps for missing items
        planner_prompt = f"""Generate implementation steps for these MISSING items:

## ORIGINAL GOAL
{goal_context.goal}

## ORIGINAL REQUEST
{goal_context.original_request}

## WHAT'S MISSING (must be implemented)
{missing_summary}

## WHAT'S ALREADY DONE
- Completed steps: {len(self.build_state.completed_steps)}
- Files created: {', '.join(self.build_state.files_created[:10]) if self.build_state.files_created else 'None'}

Create steps ONLY for the missing items. Use the standard format:
STEPS:
1. [Title]
   DO: [instruction]
   IN: [inputs]
   OUT: [output file]
   DONE: [verification]
   NEEDS: [dependencies or "none"]
"""

        # Try to load planner agent
        try:
            planner = Agent.load("planner", self.project_root)
            result = planner.run(planner_prompt)
        except Exception as e:
            self.console.print(f"  [yellow]Could not generate completion steps: {e}[/yellow]")
            return []

        if not result.success:
            return []

        # Parse the generated steps
        steps = self._parse_steps_from_content(result.content)
        self.console.print(f"  [green]{CHECK}[/green] Generated {len(steps)} completion step(s)")

        return steps

    def _parse_steps_from_content(self, content: str) -> list[BuildStep]:
        """Parse step definitions from planner output."""
        steps = []

        # Find STEPS section
        steps_match = re.search(r'STEPS?:\s*(.*?)(?:VERIFY:|$)', content, re.DOTALL | re.IGNORECASE)
        if not steps_match:
            return steps

        steps_content = steps_match.group(1)

        # Parse individual steps
        step_pattern = r'(\d+)\.\s*(.+?)(?=\n\d+\.|$)'
        step_matches = re.findall(step_pattern, steps_content, re.DOTALL)

        for i, (num, step_content) in enumerate(step_matches):
            # Extract fields
            do_match = re.search(r'DO:\s*(.+?)(?=\n\s*[A-Z]+:|$)', step_content, re.DOTALL)
            out_match = re.search(r'OUT:\s*(.+?)(?=\n|$)', step_content)

            description = do_match.group(1).strip() if do_match else step_content.split('\n')[0].strip()
            target = out_match.group(1).strip() if out_match else ""

            # Infer action from description
            action = "create"
            desc_lower = description.lower()
            if any(w in desc_lower for w in ["modify", "update", "change", "edit", "refactor"]):
                action = "modify"
            elif any(w in desc_lower for w in ["delete", "remove"]):
                action = "delete"
            elif any(w in desc_lower for w in ["run", "execute", "install"]):
                action = "run"

            steps.append(BuildStep(
                id=f"completion-step-{i+1}",
                action=action,
                target=target,
                description=description,
                complexity="medium"
            ))

        return steps

    def _run_goal_verification_loop(
        self,
        plan: "ParsedPlan",
        goal_context: GoalContext,
        plan_id: str
    ) -> bool:
        """
        Run the goal verification and self-healing loop.

        After all planned steps are executed:
        1. Verify if the goal is achieved
        2. If not, analyze gaps and generate completion steps
        3. Execute completion steps
        4. Repeat until goal achieved or max attempts reached

        Returns:
            True if goal was achieved, False otherwise
        """
        from core.symbols import CHECK, CROSS, WARNING, ARROW_RIGHT

        max_attempts = goal_context.max_verification_attempts

        for attempt in range(1, max_attempts + 1):
            goal_context.verification_attempts = attempt

            self.console.print(f"\n{'='*50}")
            self.console.print(f"[bold]Goal Verification Loop - Attempt {attempt}/{max_attempts}[/bold]")

            # Step 1: Verify goal
            goal_achieved, missing_items = self._verify_goal_achieved(goal_context)

            if goal_achieved:
                goal_context.goal_achieved = True
                return True

            # Step 2: If this is the last attempt, don't try to generate more steps
            if attempt >= max_attempts:
                self.console.print(f"\n[yellow]{WARNING} Max verification attempts reached[/yellow]")
                self.console.print(f"  Goal not fully achieved. Missing items:")
                for item in missing_items[:5]:
                    self.console.print(f"    - {item[:60]}")
                return False

            # Step 3: Generate completion steps
            completion_steps = self._generate_completion_steps(goal_context)

            if not completion_steps:
                self.console.print(f"  [yellow]{WARNING}[/yellow] Could not generate completion steps")
                continue

            # Step 4: Execute completion steps
            self.console.print(f"\n[bold]Executing {len(completion_steps)} Completion Steps:[/bold]")

            phase_context = f"Completing missing items for: {goal_context.goal[:100]}"

            for step in completion_steps:
                # Check if already done
                if step.id in self.build_state.completed_steps:
                    continue

                self.console.print(f"  [cyan]{ARROW_RIGHT}[/cyan] {step.description[:55]}...")

                result = self._execute_step(step, phase_context)

                if result.status == "completed":
                    self.build_state.completed_steps.append(step.id)
                    self.build_state.files_created.extend(
                        [f for f in result.files_affected if result.action_taken == "created"]
                    )
                    self.build_state.files_modified.extend(
                        [f for f in result.files_affected if result.action_taken == "modified"]
                    )
                    self.console.print(f"  [green]{CHECK}[/green] {result.summary[:50]}")
                else:
                    self.console.print(f"  [red]{CROSS}[/red] {result.error or 'Failed'}")

                self._save_state()

        return goal_context.goal_achieved

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
                elif full_path.is_file() and full_path.stat().st_size == 0:
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

    def _check_build_should_stop(self) -> tuple[bool, str]:
        """
        Check if the build should stop due to cancellation or external pause.

        Queries the database to check if the build status has been changed
        to 'cancelled' or 'paused' by an external process (e.g., user action
        through the portal or CLI).

        Returns:
            Tuple of (should_stop, reason) where should_stop is True if the
            build should exit gracefully, and reason is the status that caused it.
        """
        if not self._current_plan_id:
            return False, ""

        # Query the database for current status
        state_data = self._build_state_repo.get(self._current_plan_id)
        if not state_data:
            return False, ""

        db_status = state_data.get('status', '')

        # Check for stop conditions
        if db_status == 'cancelled':
            return True, 'cancelled'
        elif db_status == 'paused':
            # Check if this is an external pause (not set by us during normal operation)
            # If our in-memory status is 'building' but DB shows 'paused', it's external
            if self.build_state and self.build_state.status == 'building':
                return True, 'paused'

        return False, ""

    def _save_state(self, plan_path: Path = None):
        """Save current build state to database."""
        if not self.build_state or not self._current_plan_id:
            return

        self.build_state.updated_at = datetime.now().isoformat()

        # Update build state in database
        self._build_state_repo.update(
            plan_id=self._current_plan_id,
            status=self.build_state.status,
            current_phase=self.build_state.current_phase,
            current_step=self.build_state.current_step,
            total_steps=self.build_state.total_steps,
            completed_steps=self.build_state.completed_steps,
            failed_steps=self.build_state.failed_steps,
            skipped_steps=self.build_state.skipped_steps,
            files_created=self.build_state.files_created,
            files_modified=self.build_state.files_modified,
            last_error=self.build_state.last_error
        )

        # Update individual step states
        for step_id, step_data in self.build_state.step_states.items():
            self._build_state_repo.set_step_state(
                plan_id=self._current_plan_id,
                step_id=step_id,
                status=step_data.get('status', 'pending'),
                started_at=step_data.get('started_at'),
                completed_at=step_data.get('completed_at'),
                retry_count=step_data.get('retry_count', 0),
                error=step_data.get('error'),
                files_affected=step_data.get('files_affected', []),
                summary=step_data.get('summary', '')
            )

    def _load_state(self, plan_id: str) -> Optional[BuildState]:
        """Load existing build state from database."""
        state_data = self._build_state_repo.get(plan_id)
        if not state_data:
            return None

        try:
            # Get step states
            step_states_data = self._build_state_repo.get_step_states(plan_id)
            step_states = {
                s['step_id']: {
                    'step_id': s['step_id'],
                    'status': s['status'],
                    'started_at': s.get('started_at'),
                    'completed_at': s.get('completed_at'),
                    'retry_count': s.get('retry_count', 0),
                    'error': s.get('error'),
                    'files_affected': s.get('files_affected', []),
                    'summary': s.get('summary', '')
                }
                for s in step_states_data
            }

            return BuildState(
                plan_id=plan_id,
                plan_file="",  # Not needed for database-backed state
                status=state_data.get('status', 'pending'),
                started_at=state_data.get('started_at', datetime.now().isoformat()),
                updated_at=state_data.get('updated_at', ''),
                current_phase=state_data.get('current_phase', 0),
                current_step=state_data.get('current_step', ''),
                total_steps=state_data.get('total_steps', 0),
                completed_steps=state_data.get('completed_steps', []),
                failed_steps=state_data.get('failed_steps', []),
                skipped_steps=state_data.get('skipped_steps', []),
                step_states=step_states,
                files_created=state_data.get('files_created', []),
                files_modified=state_data.get('files_modified', []),
                last_error=state_data.get('last_error')
            )
        except Exception as e:
            self.console.print(f"[yellow]Warning: Could not load state: {e}[/yellow]")
            return None

    def _load_plan_content(self, plan_id: str) -> str:
        """
        Load plan content from database.

        Args:
            plan_id: The plan ID to load

        Returns:
            Plan content as a string
        """
        plan_data = self._plan_repo.get_by_id(plan_id)
        if plan_data:
            return plan_data.get('raw_content', '')

        raise ValueError(f"Plan not found in database: {plan_id}")

    def _archive_plan(self, plan_id: str, destination: str):
        """
        Update plan status through aggregate root pattern.

        Plan is the aggregate root - status updates flow through Plan first,
        then cascade to build_states to ensure consistency.

        Args:
            plan_id: The plan ID to update
            destination: Either "completed" or "failed"
        """
        if destination not in ("completed", "failed"):
            raise ValueError(f"Invalid archive destination: {destination}")

        # 1. Update Plan (authoritative source of truth)
        self._plan_repo.update_status(plan_id, destination)

        # 2. Update in-memory state
        if self.build_state:
            self.build_state.status = destination
            # Save full state to persist all fields (current_step, etc.)
            self._save_state()

    def _get_plan_status(self, plan_id: str) -> str:
        """
        Get the current status of a plan from database.

        Returns: pending, building, completed, failed, or unknown
        """
        state = self._load_state(plan_id)
        if state:
            return state.status

        # Check plan table as fallback
        plan_data = self._plan_repo.get_by_id(plan_id)
        if plan_data:
            return plan_data.get('status', 'pending')

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

    def _parse_key_value(self, content: str) -> dict:
        """Parse KEY: VALUE format from agent response."""
        result = {}
        current_key = None
        current_list = []

        for line in content.split('\n'):
            line = line.strip()
            if ':' in line and not line.startswith('-'):
                # Save previous list if any
                if current_key and current_list:
                    result[current_key] = current_list
                    current_list = []
                # New key
                key, value = line.split(':', 1)
                current_key = key.strip().lower().replace(' ', '_')
                value = value.strip()
                if value:
                    result[current_key] = value
            elif line.startswith('-') and current_key:
                current_list.append(line.lstrip('- ').strip())

        # Save final list
        if current_key and current_list:
            result[current_key] = current_list

        return result

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

    def _execute_step(
        self,
        step: BuildStep,
        phase_context: str,
        goal_context: Optional[GoalContext] = None
    ) -> StepResult:
        """Execute a single build step using goal-aware agentic builder."""
        # Check if build should stop (cancelled or externally paused)
        should_stop, stop_reason = self._check_build_should_stop()
        if should_stop:
            return StepResult(
                step_id=step.id,
                status="skipped",
                action_taken="none",
                target=step.target,
                summary=f"Build {stop_reason} - step skipped",
                error=f"Build was {stop_reason} by external request"
            )

        step_context = self._get_relevant_context(step)

        # Build goal-aware context for the builder
        goal_section = ""
        if goal_context and (goal_context.goal or goal_context.original_request):
            goal_section = f"""## GOAL
{goal_context.goal}

## ORIGINAL REQUEST
{goal_context.original_request}

"""

        # Build input files section
        inputs_section = ""
        if step.inputs:
            inputs_section = f"\nIN: {', '.join(step.inputs)}"

        full_context = f"""{goal_section}## Phase Context
{phase_context[:1500]}

## Step Context
{step_context}
"""

        # Builder runs in agentic mode - it can actually write files
        # Pass all step fields including DONE for verification
        result = self.run_agent(
            "builder",
            message=f"""Execute this build step:

STEP: {step.id} - {step.description[:60]}
ACTION: {step.action}
DO: {step.description}{inputs_section}
OUT: {step.target}
DONE: {step.done or 'Verify file exists and contains expected implementation'}

IMPORTANT:
1. Read IN files first to understand patterns
2. Create/modify files using Write/Edit tools
3. After completing, verify the DONE criteria
4. Report VERIFIED: yes|no based on your check""",
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
            # Handle comma-separated targets in OUT field (e.g., "file1.py, file2.py (modified)")
            if step.target:
                targets = []
                for t in step.target.split(','):
                    # Remove parenthetical notes like "(empty initially)" or "(modified)"
                    clean_target = re.sub(r'\s*\([^)]*\)\s*$', '', t.strip())
                    if clean_target:
                        targets.append(clean_target)
                files_affected = targets
            else:
                files_affected = []

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

    def _run_simple_build(self, plan: ParsedPlan, plan_id: str) -> WorkflowResult:
        """
        Run build for simple plans with optional parallel execution.

        If simple_build_parallel is enabled:
            - Flattens all steps across phases
            - Computes execution waves based on dependencies and parallel groups
            - Executes each wave in parallel

        Otherwise:
            - Runs steps sequentially within each phase
        """
        from core.symbols import ARROW_RIGHT, CHECK, CROSS, WARNING

        use_parallel = self._config.parallel.simple_build_parallel
        steps_completed = []

        if use_parallel:
            # Parallel wave-based execution
            return self._run_simple_build_parallel(plan, plan_id)
        else:
            # Sequential execution (original behavior)
            return self._run_simple_build_sequential(plan, plan_id)

    def _run_simple_build_sequential(self, plan: ParsedPlan, plan_id: str) -> WorkflowResult:
        """Run sequential build for simple plans with step-level tracking."""
        from core.symbols import ARROW_RIGHT, CHECK, CROSS, WARNING

        steps_completed = []

        # Extract goal context ONCE at the start for goal-aware building
        goal_context = self._extract_goal_context(plan.raw_content)

        for phase_idx, phase in enumerate(plan.phases):
            self.console.print(f"\n[bold]Phase {phase_idx + 1}/{len(plan.phases)}:[/bold] {phase.name}")

            self.build_state.current_phase = phase_idx
            self._save_state()

            phase_context = f"Building phase: {phase.name}\nDescription: {phase.name}"

            for step in phase.steps:
                # Check if build should stop (cancelled or externally paused)
                should_stop, stop_reason = self._check_build_should_stop()
                if should_stop:
                    # Save state before exiting
                    self.build_state.status = stop_reason
                    self.build_state.last_error = f"Build {stop_reason} by external request"
                    self._save_state()

                    from core.symbols import WARNING
                    self.console.print(f"\n[yellow]{WARNING} Build {stop_reason} - exiting gracefully[/yellow]")

                    return WorkflowResult(
                        success=False,
                        error=f"Build {stop_reason} by external request",
                        steps_completed=steps_completed,
                        data={
                            "stopped_at": step.id,
                            "stop_reason": stop_reason,
                            "can_resume": stop_reason == "paused",
                            "completed_steps": len(self.build_state.completed_steps),
                            "total_steps": self.build_state.total_steps,
                        }
                    )

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
                self._save_state()

                # Display progress
                completed, total = self.build_state.get_progress()
                progress_str = f"[{completed}/{total}]"
                self.console.print(f"  [cyan]{ARROW_RIGHT}[/cyan] {progress_str} {step.description[:55]}...")

                # Execute the step with goal context for goal-aware building
                result = self._execute_step(step, phase_context, goal_context)

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
                    self._save_state()

                    self.console.print(f"  [red]{CROSS}[/red] {result.error or 'Failed'}")

                    # Check if goal is achieved despite step failure
                    self.console.print(f"\n[yellow]Step failed - checking if goal achieved...[/yellow]")
                    goal_context = self._extract_goal_context(plan.raw_content)
                    if goal_context.goal or goal_context.original_request:
                        goal_achieved, _ = self._verify_goal_achieved(goal_context)

                        if goal_achieved:
                            self.console.print(f"\n[green]Goal achieved despite step failure![/green]")
                            # Archive plan - this updates both Plan and build_states atomically
                            self._archive_plan(plan_id, "completed")
                            return WorkflowResult(
                                success=True,
                                steps_completed=steps_completed,
                                data={"goal_achieved": True}
                            )

                    # Goal not achieved - pause for retry
                    self.build_state.status = "paused"
                    self._save_state()

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

                self._save_state()

            # Run tests after phase
            if self._config.parallel.overlap_build_test and phase_idx < len(plan.phases) - 1:
                # Start tests in background, continue to next phase
                self.console.print(f"\n  [dim]Starting async tests for phase {phase_idx + 1}...[/dim]")
                self._start_async_phase_test(plan, phase_idx)
            else:
                # Run tests synchronously (last phase or overlap disabled)
                self.console.print(f"\n  [bold]Testing phase {phase_idx + 1}...[/bold]")
                test_result = self._run_phase_tests(plan, phase_idx)
                if not test_result:
                    self.console.print(f"  [yellow]{WARNING}[/yellow] Tests had issues (continuing)")

        # Wait for any background tests
        if self._test_futures:
            self.console.print("\n[bold]Waiting for background tests...[/bold]")
            test_results = self._wait_for_all_tests()
            failed_count = sum(1 for r in test_results if not r)
            if failed_count > 0:
                self.console.print(f"  [yellow]{WARNING}[/yellow] {failed_count} phase test(s) had issues")

        # GOAL VERIFICATION LOOP: Check if the goal is actually achieved
        # Extract goal context from plan
        goal_context = self._extract_goal_context(plan.raw_content)

        # Only run goal verification if we have a goal and original request
        if goal_context.goal or goal_context.original_request:
            goal_achieved = self._run_goal_verification_loop(plan, goal_context, plan_id)

            if not goal_achieved:
                # Goal not achieved - mark as paused for manual intervention
                self.build_state.status = "paused"
                self.build_state.last_error = f"Goal not fully achieved. Missing: {', '.join(goal_context.missing_items[:3])}"
                self._save_state()

                self.console.print(f"\n[yellow]Build paused - goal not fully achieved[/yellow]")
                self.console.print(f"  Completion: {goal_context.completion_percentage}%")
                self.console.print(f"  Run build again to continue attempting")

                return WorkflowResult(
                    success=False,
                    error="Goal not fully achieved after verification loop",
                    steps_completed=steps_completed,
                    data={
                        "paused_at": "goal_verification",
                        "can_resume": True,
                        "goal_context": goal_context.to_dict(),
                        "completed_steps": len(self.build_state.completed_steps),
                    }
                )

        # Final review
        self.console.print("\n[bold]Final Review...[/bold]")
        review_result = self._run_review(plan)

        return WorkflowResult(
            success=True,
                        steps_completed=steps_completed,
            data={
                "plan_type": "simple",
                "files_created": self.build_state.files_created,
                "files_modified": self.build_state.files_modified,
                "review": review_result,
                "goal_achieved": True
            }
        )

    def _run_simple_build_parallel(self, plan: ParsedPlan, plan_id: str) -> WorkflowResult:
        """
        Run parallel wave-based build for simple plans.

        Flattens all steps, computes waves based on dependencies and parallel groups,
        then executes waves in parallel.
        """
        from core.symbols import ARROW_RIGHT, CHECK, CROSS, WARNING

        steps_completed = []

        # Extract goal context ONCE at the start for goal-aware building
        goal_context = self._extract_goal_context(plan.raw_content)

        # Flatten all steps across phases while preserving phase context
        all_steps: list[tuple[BuildStep, str]] = []  # (step, phase_context)
        for phase in plan.phases:
            phase_context = f"Building phase: {phase.name}\nDescription: {phase.name}"
            for step in phase.steps:
                all_steps.append((step, phase_context))

        # Build step list for wave computation
        steps_only = [s for s, _ in all_steps]
        step_contexts = {s.id: ctx for s, ctx in all_steps}

        # Compute execution waves
        completed_set = set(self.build_state.completed_steps)
        waves = self._compute_parallel_waves(steps_only, completed_set)

        total_waves = len(waves)
        self.console.print(f"\n[bold]Parallel Build:[/bold] {len(steps_only)} steps in {total_waves} waves")

        for wave_idx, wave in enumerate(waves):
            # Check if build should stop (cancelled or externally paused)
            should_stop, stop_reason = self._check_build_should_stop()
            if should_stop:
                # Save state before exiting
                self.build_state.status = stop_reason
                self.build_state.last_error = f"Build {stop_reason} by external request"
                self._save_state()

                self.console.print(f"\n[yellow]{WARNING} Build {stop_reason} - exiting gracefully[/yellow]")

                return WorkflowResult(
                    success=False,
                    error=f"Build {stop_reason} by external request",
                    steps_completed=steps_completed,
                    data={
                        "stopped_at": f"wave-{wave_idx + 1}",
                        "stop_reason": stop_reason,
                        "can_resume": stop_reason == "paused",
                        "completed_steps": len(self.build_state.completed_steps),
                        "total_steps": self.build_state.total_steps,
                    }
                )

            wave_size = len(wave)
            self.console.print(f"\n[bold]Wave {wave_idx + 1}/{total_waves}:[/bold] {wave_size} step(s)")

            # Filter out already completed (may have been completed in a previous run)
            pending_steps = [s for s in wave if s.id not in self.build_state.completed_steps]
            if not pending_steps:
                self.console.print("  [dim](all steps already done)[/dim]")
                continue

            # Mark all steps in wave as in_progress
            for step in pending_steps:
                existing_step_state = self.build_state.get_step_state(step.id)
                step_state = StepState(
                    step_id=step.id,
                    status="in_progress",
                    started_at=datetime.now().isoformat(),
                    retry_count=(existing_step_state.retry_count if existing_step_state else 0)
                )
                self.build_state.set_step_state(step_state)
            self._save_state()

            if wave_size == 1:
                # Single step - run directly with goal context
                step = pending_steps[0]
                phase_context = step_contexts.get(step.id, "")
                self.console.print(f"  [cyan]{ARROW_RIGHT}[/cyan] {step.description[:55]}...")
                result = self._execute_step(step, phase_context, goal_context)
                wave_results = [(step, result)]
            else:
                # Multiple steps - run in parallel with goal context
                self.console.print(f"  [cyan]Running {len(pending_steps)} steps in parallel...[/cyan]")
                # All steps in same wave use first step's context (simplification)
                phase_context = step_contexts.get(pending_steps[0].id, "")
                wave_results = self._execute_wave_parallel(pending_steps, phase_context, plan_id, goal_context)

            # Process wave results
            wave_failed = False
            for step, result in wave_results:
                step_state = self.build_state.get_step_state(step.id) or StepState(
                    step_id=step.id, status="pending"
                )
                step_state.completed_at = datetime.now().isoformat()
                step_state.files_affected = result.files_affected
                step_state.summary = result.summary

                if result.status == "completed":
                    step_state.status = "completed"
                    self.build_state.set_step_state(step_state)
                    if step.id not in self.build_state.completed_steps:
                        self.build_state.completed_steps.append(step.id)
                    self.build_state.files_created.extend(
                        [f for f in result.files_affected if result.action_taken == "created"]
                    )
                    self.build_state.files_modified.extend(
                        [f for f in result.files_affected if result.action_taken == "modified"]
                    )
                    steps_completed.append(step.id)
                else:
                    step_state.status = "failed"
                    step_state.error = result.error
                    step_state.retry_count += 1
                    self.build_state.set_step_state(step_state)
                    if step.id not in self.build_state.failed_steps:
                        self.build_state.failed_steps.append(step.id)
                    wave_failed = True

            self._save_state()

            # If any step in wave failed, check if GOAL is still achieved
            if wave_failed:
                self.console.print(f"\n[yellow]Wave {wave_idx + 1} had failures - checking if goal achieved...[/yellow]")

                # Check if goal is achieved despite failures
                goal_context = self._extract_goal_context(plan.raw_content)
                if goal_context.goal or goal_context.original_request:
                    goal_achieved, _ = self._verify_goal_achieved(goal_context)

                    if goal_achieved:
                        # Goal achieved! Mark as completed despite step failures
                        self.console.print(f"\n[green]Goal achieved despite step failures![/green]")
                        # Archive plan - this updates both Plan and build_states atomically
                        self._archive_plan(plan_id, "completed")
                        return WorkflowResult(
                            success=True,
                            steps_completed=steps_completed,
                            data={
                                "completed_steps": len(self.build_state.completed_steps),
                                "total_steps": self.build_state.total_steps,
                                "goal_achieved": True,
                            }
                        )

                # Goal not achieved - pause for retry
                self.build_state.status = "paused"
                self.build_state.last_error = f"Wave {wave_idx + 1} had failures"
                self._save_state()

                self.console.print(f"[dim]Run build again to retry failed steps[/dim]")

                return WorkflowResult(
                    success=False,
                    error=f"Wave {wave_idx + 1} had failures",
                    steps_completed=steps_completed,
                    data={
                        "paused_at": f"wave-{wave_idx + 1}",
                        "can_resume": True,
                        "completed_steps": len(self.build_state.completed_steps),
                        "total_steps": self.build_state.total_steps,
                    }
                )

        # Run final tests
        self.console.print("\n[bold]Final Testing...[/bold]")
        test_result = self._run_phase_tests(plan, -1)  # -1 for final tests
        if not test_result:
            self.console.print(f"  [yellow]{WARNING}[/yellow] Tests had issues (continuing)")

        # GOAL VERIFICATION LOOP: Check if the goal is actually achieved
        goal_context = self._extract_goal_context(plan.raw_content)

        if goal_context.goal or goal_context.original_request:
            goal_achieved = self._run_goal_verification_loop(plan, goal_context, plan_id)

            if not goal_achieved:
                self.build_state.status = "paused"
                self.build_state.last_error = f"Goal not fully achieved. Missing: {', '.join(goal_context.missing_items[:3])}"
                self._save_state()

                self.console.print(f"\n[yellow]Build paused - goal not fully achieved[/yellow]")
                self.console.print(f"  Completion: {goal_context.completion_percentage}%")

                return WorkflowResult(
                    success=False,
                    error="Goal not fully achieved after verification loop",
                    steps_completed=steps_completed,
                    data={
                        "paused_at": "goal_verification",
                        "can_resume": True,
                        "goal_context": goal_context.to_dict(),
                    }
                )

        # Final review
        self.console.print("\n[bold]Final Review...[/bold]")
        review_result = self._run_review(plan)

        return WorkflowResult(
            success=True,
                        steps_completed=steps_completed,
            data={
                "plan_type": "simple",
                "parallel_waves": total_waves,
                "files_created": self.build_state.files_created,
                "files_modified": self.build_state.files_modified,
                "review": review_result,
                "goal_achieved": True
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

    def _detect_file_conflicts(self, steps: list[BuildStep]) -> dict[str, list[str]]:
        """
        Detect steps that modify the same file - these cannot run in parallel.

        Returns:
            Dict mapping file path -> list of step IDs that touch that file
        """
        file_to_steps: dict[str, list[str]] = {}
        for step in steps:
            if step.target:
                # Normalize path for comparison
                target = step.target.replace("\\", "/")
                if target not in file_to_steps:
                    file_to_steps[target] = []
                file_to_steps[target].append(step.id)
        return {f: sids for f, sids in file_to_steps.items() if len(sids) > 1}

    def _compute_parallel_waves(
        self, steps: list[BuildStep], completed: set[str]
    ) -> list[list[BuildStep]]:
        """
        Convert steps into execution waves based on dependencies and parallel groups.

        Steps in the same wave can run in parallel. Waves execute sequentially.
        File conflicts force steps into separate waves even if dependencies allow parallel.

        Args:
            steps: List of steps to organize
            completed: Set of already completed step IDs

        Returns:
            List of waves, each wave is a list of steps that can run in parallel
        """
        if not steps:
            return []

        # Filter out completed steps
        pending = [s for s in steps if s.id not in completed]
        if not pending:
            return []

        # Detect file conflicts
        conflicts = self._detect_file_conflicts(pending)

        # Build step map and dependency info
        step_map = {s.id: s for s in pending}
        remaining = set(step_map.keys())
        waves: list[list[BuildStep]] = []

        # Track which files have been touched (for conflict resolution)
        files_in_progress: set[str] = set()

        max_iterations = len(pending) + 1
        for _ in range(max_iterations):
            if not remaining:
                break

            # Find steps ready to execute (all dependencies satisfied)
            ready: list[BuildStep] = []
            for step_id in list(remaining):
                step = step_map[step_id]
                deps = set(step.dependencies)

                # Check if dependencies are satisfied
                deps_satisfied = deps.issubset(completed | (set(step_map.keys()) - remaining))
                if not deps_satisfied:
                    continue

                # Check for file conflicts with other ready steps
                target = step.target.replace("\\", "/") if step.target else None
                if target and target in files_in_progress:
                    # This file is being modified by another step in this wave
                    continue

                ready.append(step)
                if target:
                    files_in_progress.add(target)

            if not ready:
                # Circular dependency or all remaining have conflicts - run one at a time
                for step_id in list(remaining):
                    waves.append([step_map[step_id]])
                    remaining.discard(step_id)
                    completed.add(step_id)
                break

            # Group ready steps by parallel_group if set
            # Steps with same parallel_group can run together
            # Steps with different groups or no group run in sub-waves
            if self._config.parallel.simple_build_parallel:
                # Group by parallel_group for smarter batching
                groups: dict[Optional[str], list[BuildStep]] = {}
                for step in ready:
                    pg = step.parallel_group
                    if pg not in groups:
                        groups[pg] = []
                    groups[pg].append(step)

                # Create wave from largest compatible group
                # None group items run individually unless they're the only ones
                if len(groups) == 1:
                    # All same group (or all None) - run together
                    waves.append(ready)
                else:
                    # Multiple groups - prioritize grouped steps
                    for pg, group_steps in sorted(groups.items(), key=lambda x: -len(x[1])):
                        if pg is not None and len(group_steps) > 1:
                            waves.append(group_steps)
                            for s in group_steps:
                                remaining.discard(s.id)
                                completed.add(s.id)
                        else:
                            # Ungrouped or single step - add individually
                            for s in group_steps:
                                waves.append([s])
                                remaining.discard(s.id)
                                completed.add(s.id)
                    continue  # Skip normal remaining handling
            else:
                waves.append(ready)

            for step in ready:
                remaining.discard(step.id)
                completed.add(step.id)

            # Reset files for next wave
            files_in_progress.clear()

        return waves

    def _execute_wave_parallel(
        self,
        steps: list[BuildStep],
        phase_context: str,
        plan_id: str,
        goal_context: Optional[GoalContext] = None
    ) -> list[tuple[BuildStep, StepResult]]:
        """
        Execute multiple steps in parallel using ThreadPoolExecutor.

        Args:
            steps: Steps to execute in parallel
            phase_context: Context string for the current phase
            plan_id: Plan ID for state saving
            goal_context: Optional goal context for goal-aware building

        Returns:
            List of (step, result) tuples in completion order
        """
        from core.symbols import CHECK, CROSS

        max_workers = min(len(steps), self._config.parallel.max_build_workers)
        results: list[tuple[BuildStep, StepResult]] = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all steps with goal context
            futures = {
                executor.submit(self._execute_step, step, phase_context, goal_context): step
                for step in steps
            }

            # Collect results as they complete
            for future in as_completed(futures):
                step = futures[future]
                try:
                    result = future.result()
                    results.append((step, result))

                    if result.status == "completed":
                        self.console.print(f"    [green]{CHECK}[/green] {step.id}: {result.summary[:40]}")
                    else:
                        self.console.print(f"    [red]{CROSS}[/red] {step.id}: {result.error or 'Failed'}")
                except Exception as e:
                    error_result = StepResult(
                        step_id=step.id,
                        status="failed",
                        action_taken="none",
                        target=step.target,
                        summary="",
                        error=str(e)
                    )
                    results.append((step, error_result))
                    self.console.print(f"    [red]{CROSS}[/red] {step.id}: {e}")

        return results

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

    def _run_complex_build(self, plan: ParsedPlan, plan_id: str, coordination: dict) -> WorkflowResult:
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
                    self._save_state()

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

            self._save_state()

            # Check for failures - pause build for resume
            failed = [r for r in results if r.status == "failed"]
            if failed:
                self.build_state.status = "paused"
                self.build_state.last_error = f"Batch {batch_id}: {len(failed)} step(s) failed"
                self._save_state()

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
                        steps_completed=steps_completed,
            data={
                "plan_type": "complex",
                "batches_executed": len(execution_plan),
                "files_created": self.build_state.files_created,
                "files_modified": self.build_state.files_modified,
                "review": review_result
            }
        )

    def _start_async_phase_test(self, plan: ParsedPlan, phase_idx: int) -> Future:
        """
        Start phase test in background, allowing building to continue.

        Args:
            plan: The parsed plan
            phase_idx: The phase index to test

        Returns:
            Future that resolves to test result
        """
        if self._test_executor is None:
            self._test_executor = ThreadPoolExecutor(max_workers=1)

        future = self._test_executor.submit(self._run_phase_tests, plan, phase_idx)
        self._test_futures.append(future)
        return future

    def _wait_for_all_tests(self, timeout: Optional[float] = None) -> list[bool]:
        """
        Wait for all background tests to complete.

        Args:
            timeout: Max wait time in seconds (None = wait forever)

        Returns:
            List of test results (True = passed, False = failed)
        """
        results = []
        for future in self._test_futures:
            try:
                result = future.result(timeout=timeout)
                results.append(result)
            except Exception:
                results.append(False)

        # Clear futures list
        self._test_futures.clear()

        # Cleanup executor if done
        if self._test_executor:
            self._test_executor.shutdown(wait=False)
            self._test_executor = None

        return results

    def _run_phase_tests(self, plan: ParsedPlan, phase_idx: int) -> bool:
        """Run tests after a phase. Skip if tester agent not available."""
        if "tester" not in self.agents:
            return True  # Skip tests if no tester agent

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
        """Run final code review (simplified - goal verification done separately)."""
        # Review step is now simplified - goal verification happens via goal-verifier
        return {
            "status": "completed",
            "files_created": len(self.build_state.files_created),
            "files_modified": len(self.build_state.files_modified),
            "steps_completed": len(self.build_state.completed_steps)
        }

    def execute(self, plan_id: str) -> WorkflowResult:
        """
        Execute the building workflow for a plan.

        Plans are tracked in the database. State is also stored in the database.
        Plan status changes to building during execution and completed/failed when done.

        Args:
            plan_id: The plan ID to build (e.g., "001_add-feature")
        """
        # Store current plan ID for state management
        self._current_plan_id = plan_id

        # Check if plan exists in database
        plan_data = self._plan_repo.get_by_id(plan_id)
        if not plan_data:
            return WorkflowResult(success=False, error=f"Plan not found: {plan_id}")

        self.console.print(f"[dim]Loading plan: {plan_id}[/dim]")

        # Update plan status to building
        self._plan_repo.update_status(plan_id, "building")

        # Load or create build state
        existing_state = self._load_state(plan_id)
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
                plan_id=plan_id,
                plan_file="",
                status="building",
                started_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            )

        self._save_state()

        # Phase 1: Parse the plan using DETERMINISTIC parser (no LLM)
        self.console.print("\n[bold]Phase 1:[/bold] Parsing plan...")
        plan_content = self._load_plan_content(plan_id)

        # Use deterministic regex-based parser (faster, more reliable than LLM)
        parser = PlanParser()
        parse_result = parser.parse(plan_content, plan_id=plan_id)

        if not parse_result.success:
            error_msg = parse_result.error_summary()
            self.build_state.status = "failed"
            self.build_state.last_error = f"Plan parsing failed: {error_msg}"
            self._save_state()
            self._plan_repo.update_status(plan_id, "failed")
            return WorkflowResult(
                success=False,
                error=f"Plan parsing failed: {error_msg}. Please check the plan format."
            )

        # Show warnings if any
        if parse_result.warnings:
            from core.symbols import WARNING
            for warning in parse_result.warnings[:5]:
                self.console.print(f"  [yellow]{WARNING}[/yellow] {warning}")

        # Convert parsed plan to internal format
        parsed_plan = parse_result.plan
        phases = []

        for phase in parsed_plan.phases:
            steps = []
            for step in phase.steps:
                steps.append(BuildStep(
                    id=step.id,
                    action=step.action.value,  # Convert enum to string
                    target=step.target,
                    description=step.description,
                    done=step.done,  # Pass DONE criteria
                    inputs=step.inputs,  # Pass input files
                    dependencies=step.needs,
                    complexity="simple",
                ))

            phases.append(BuildPhase(
                id=phase.id,
                name=phase.name,
                steps=steps,
                can_parallelize=len(steps) > 1,
            ))

        plan = ParsedPlan(
            plan_id=parsed_plan.plan_id,
            plan_type="simple" if len(phases) <= 1 else "complex",
            source_file=Path(plan_id),  # Placeholder for compatibility
            phases=phases,
            validation_commands=parsed_plan.verify,
            raw_content=plan_content
        )

        total_steps = sum(len(p.steps) for p in phases)
        from core.symbols import CHECK
        self.console.print(f"  [green]{CHECK}[/green] parsed (deterministic)")
        self.console.print(f"  Goal: [dim]{parsed_plan.goal[:60]}...[/dim]" if len(parsed_plan.goal) > 60 else f"  Goal: [dim]{parsed_plan.goal}[/dim]")
        self.console.print(f"  Steps: [cyan]{total_steps}[/cyan]")

        # Store total steps in build state for progress tracking
        self.build_state.total_steps = total_steps
        self._save_state()

        # CRITICAL: Fail if no steps were extracted from the plan
        if total_steps == 0:
            self.build_state.status = "failed"
            self.build_state.last_error = "No implementation steps found in plan"
            self._save_state()
            self._plan_repo.update_status(plan_id, "failed")
            return WorkflowResult(
                success=False,
                error=(
                    "Parser could not extract any implementation steps from the plan. "
                    "The plan may be incomplete, empty, or malformed. "
                    "Please re-run the planning workflow to generate a complete plan with actionable steps."
                )
            )

        # WARNING: Check if plan seems suspiciously short (might be incomplete)
        # Extract Request line from plan content to check for numbered requirements
        request_match = re.search(r'Request:\s*(.+?)(?:\n|Complexity:)', plan_content, re.DOTALL)
        if request_match:
            original_request = request_match.group(1).strip()
            # Count numbered items in original request
            numbered_items = len(re.findall(r'\(\d+\)', original_request))
            if numbered_items >= 3 and total_steps < numbered_items - 2:
                from core.symbols import WARNING
                self.console.print(f"\n  [yellow]{WARNING} Warning: Request specified {numbered_items} numbered items but plan only has {total_steps} step(s)[/yellow]")
                self.console.print(f"  [yellow]The plan may be incomplete. Consider re-running the planning workflow.[/yellow]")

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
                result = self._run_complex_build(plan, plan_id, coordination)
            else:
                # Fallback to simple
                self.console.print("[yellow]Coordinator failed, using simple build[/yellow]")
                result = self._run_simple_build(plan, plan_id)
        else:
            # Simple sequential build
            result = self._run_simple_build(plan, plan_id)

        # Handle result - only archive on full completion
        if result.success:
            # Clear current step indicator
            self.build_state.current_step = ""
            # Archive plan - this updates both Plan and build_states atomically
            self._archive_plan(plan_id, "completed")

            completed, total = self.build_state.get_progress()
            self.console.print(f"\n[green]Build completed successfully![/green]")
            self.console.print(f"  Plan ID: {plan_id}")
            self.console.print(f"  Steps: {completed}/{total}")
            self.console.print(f"  Files created: {len(self.build_state.files_created)}")
            self.console.print(f"  Files modified: {len(self.build_state.files_modified)}")
            self.console.print(f"  Status: completed")
        else:
            # Check if this is a pausable failure (can resume) or permanent failure
            is_paused = result.data and result.data.get("can_resume", False)

            if is_paused:
                # Build is paused - state already saved, plan stays in place
                self.console.print(f"\n[yellow]Build paused - can be resumed[/yellow]")
                completed, total = self.build_state.get_progress()
                self.console.print(f"  Progress: {completed}/{total} steps completed")
                self.console.print(f"  State saved to database")
                self.console.print(f"\n[dim]Run 'build {plan_id}' again to resume[/dim]")
            else:
                # Permanent failure - update status in database
                self.build_state.status = "failed"
                self._save_state()

                self._archive_plan(plan_id, "failed")
                self.console.print(f"\n[red]Build failed permanently[/red]")
                self.console.print(f"  Plan status: failed")

        return result


def run(args=None) -> int:
    """Run building action."""
    if not args:
        print("Usage: build <plan-id>")
        return 1

    plan_id = args[0]
    project_root = Path(__file__).parent.parent.parent

    workflow = BuildingWorkflow(project_root=project_root)
    result = workflow.run(plan_id)
    return 0 if result.success else 1


if __name__ == "__main__":
    import sys
    sys.exit(run(sys.argv[1:]))
