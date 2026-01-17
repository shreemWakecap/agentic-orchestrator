"""
Deterministic Plan Parser - No LLM Required.

Parses implementation plans in GOAL/CONTEXT/STEPS/VERIFY format.
Uses regex for parsing and Pydantic for validation.

This replaces the LLM-based parser agent for faster, more reliable parsing.
"""
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# =============================================================================
# Schema Models (Pydantic)
# =============================================================================

class StepAction(str, Enum):
    """Valid step actions."""
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"
    RUN = "run"


class PlanStep(BaseModel):
    """A single implementation step."""
    id: str = Field(description="Step identifier like 'step-1'")
    action: StepAction = Field(description="What type of action: create, modify, delete, run")
    target: str = Field(description="Output file or target of the action")
    description: str = Field(description="What to do (from DO field)")
    done: str = Field(default="", description="How to verify this step (from DONE field)")
    inputs: list[str] = Field(default_factory=list, description="Input files (from IN field)")
    needs: list[str] = Field(default_factory=list, description="Dependencies (step IDs)")

    @field_validator('target')
    @classmethod
    def target_not_empty(cls, v: str) -> str:
        if not v or v.lower() == 'none':
            return ""
        return v.strip()

    @field_validator('description')
    @classmethod
    def description_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Step description (DO) cannot be empty")
        return v.strip()


class PlanPhase(BaseModel):
    """A phase containing steps (for compatibility with existing building.py)."""
    id: str = Field(default="phase-1")
    name: str = Field(default="Implementation")
    steps: list[PlanStep] = Field(default_factory=list)
    can_parallelize: bool = Field(default=False)


class ParsedPlan(BaseModel):
    """Complete parsed plan structure."""
    plan_id: str = Field(description="Kebab-case identifier")
    goal: str = Field(description="What success looks like")
    context: list[str] = Field(default_factory=list, description="Relevant context bullets")
    phases: list[PlanPhase] = Field(default_factory=list)
    verify: list[str] = Field(default_factory=list, description="Verification commands")
    raw_content: str = Field(default="", description="Original plan text")

    @property
    def total_steps(self) -> int:
        return sum(len(p.steps) for p in self.phases)

    @property
    def all_steps(self) -> list[PlanStep]:
        return [s for p in self.phases for s in p.steps]

    @model_validator(mode='after')
    def validate_dependencies(self) -> 'ParsedPlan':
        """Ensure all step dependencies reference valid steps."""
        valid_ids = {s.id for s in self.all_steps}
        for step in self.all_steps:
            for dep in step.needs:
                if dep not in valid_ids:
                    raise ValueError(f"Step {step.id} has invalid dependency: {dep}")
        return self


# =============================================================================
# Parse Errors
# =============================================================================

@dataclass
class ParseError:
    """A parsing error with location info."""
    message: str
    line: Optional[int] = None
    field: Optional[str] = None

    def __str__(self) -> str:
        parts = [self.message]
        if self.line:
            parts.append(f"(line {self.line})")
        if self.field:
            parts.append(f"[{self.field}]")
        return " ".join(parts)


@dataclass
class ParseResult:
    """Result of parsing a plan."""
    success: bool
    plan: Optional[ParsedPlan] = None
    errors: list[ParseError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error_summary(self) -> str:
        return "; ".join(str(e) for e in self.errors)


# =============================================================================
# Deterministic Parser
# =============================================================================

class PlanParser:
    """
    Deterministic parser for implementation plans.

    Expected format:
    ```
    GOAL: [one sentence]

    CONTEXT:
    - [bullet 1]
    - [bullet 2]

    STEPS:
    1. [Title with action verb]
       ACTION: create|modify|delete|run
       DO: [instruction]
       IN: [input files or "none"]
       OUT: [output file]
       DONE: [verification]
       NEEDS: [step numbers or "none"]

    VERIFY:
    - [verification command]
    ```
    """

    # Action verb mappings
    ACTION_VERBS = {
        "create": StepAction.CREATE,
        "add": StepAction.CREATE,
        "write": StepAction.CREATE,
        "implement": StepAction.CREATE,
        "generate": StepAction.CREATE,
        "modify": StepAction.MODIFY,
        "update": StepAction.MODIFY,
        "change": StepAction.MODIFY,
        "edit": StepAction.MODIFY,
        "refactor": StepAction.MODIFY,
        "fix": StepAction.MODIFY,
        "delete": StepAction.DELETE,
        "remove": StepAction.DELETE,
        "run": StepAction.RUN,
        "execute": StepAction.RUN,
        "install": StepAction.RUN,
        "configure": StepAction.MODIFY,
    }

    def __init__(self):
        self.errors: list[ParseError] = []
        self.warnings: list[str] = []

    def parse(self, content: str, plan_id: Optional[str] = None) -> ParseResult:
        """
        Parse plan content into structured format.

        Args:
            content: Raw plan text
            plan_id: Optional plan identifier (derived from filename if not provided)

        Returns:
            ParseResult with parsed plan or errors
        """
        self.errors = []
        self.warnings = []

        if not content or not content.strip():
            return ParseResult(
                success=False,
                errors=[ParseError("Plan content is empty")]
            )

        # Extract sections
        goal = self._extract_goal(content)
        context = self._extract_context(content)
        steps = self._extract_steps(content)
        verify = self._extract_verify(content)

        # Derive plan_id if not provided
        if not plan_id:
            plan_id = self._derive_plan_id(goal)

        # Check for critical errors
        if not goal:
            self.errors.append(ParseError("Missing GOAL section", field="GOAL"))

        if not steps:
            self.errors.append(ParseError("No valid steps found", field="STEPS"))

        if self.errors:
            return ParseResult(
                success=False,
                errors=self.errors,
                warnings=self.warnings
            )

        # Build the plan
        try:
            plan = ParsedPlan(
                plan_id=plan_id,
                goal=goal,
                context=context,
                phases=[PlanPhase(steps=steps)],
                verify=verify,
                raw_content=content
            )

            return ParseResult(
                success=True,
                plan=plan,
                warnings=self.warnings
            )

        except ValueError as e:
            return ParseResult(
                success=False,
                errors=[ParseError(str(e))],
                warnings=self.warnings
            )

    def parse_file(self, path: Path) -> ParseResult:
        """Parse a plan file."""
        if not path.exists():
            return ParseResult(
                success=False,
                errors=[ParseError(f"File not found: {path}")]
            )

        content = path.read_text(encoding="utf-8")
        plan_id = path.stem  # Use filename as plan_id

        return self.parse(content, plan_id)

    def _extract_goal(self, content: str) -> str:
        """Extract GOAL section."""
        # Try GOAL: format first
        match = re.search(
            r'(?:^|\n)GOAL:\s*(.+?)(?=\n\n|\nCONTEXT:|\nSTEPS:|\n##|\Z)',
            content,
            re.DOTALL | re.IGNORECASE
        )
        if match:
            return match.group(1).strip()

        # Try ## Goal header format
        match = re.search(
            r'(?:^|\n)##?\s*Goal\s*\n+(.+?)(?=\n##|\n\n\n|\Z)',
            content,
            re.DOTALL | re.IGNORECASE
        )
        if match:
            return match.group(1).strip()

        return ""

    def _extract_context(self, content: str) -> list[str]:
        """Extract CONTEXT bullets."""
        # Try CONTEXT: format
        match = re.search(
            r'(?:^|\n)CONTEXT:\s*\n((?:\s*-\s*.+\n?)+)',
            content,
            re.IGNORECASE
        )
        if match:
            return self._parse_bullets(match.group(1))

        # Try ## Context header
        match = re.search(
            r'(?:^|\n)##?\s*Context\s*\n+((?:\s*-\s*.+\n?)+)',
            content,
            re.IGNORECASE
        )
        if match:
            return self._parse_bullets(match.group(1))

        return []

    def _extract_steps(self, content: str) -> list[PlanStep]:
        """Extract and parse all steps."""
        # Find STEPS section
        steps_match = re.search(
            r'(?:^|\n)(?:STEPS:|##?\s*Steps?)\s*\n(.*?)(?=\n(?:VERIFY:|##?\s*Verify)|\Z)',
            content,
            re.DOTALL | re.IGNORECASE
        )

        if not steps_match:
            return []

        steps_content = steps_match.group(1)
        steps: list[PlanStep] = []

        # Pattern for individual steps
        # Matches: 1. Title\n   fields...
        step_pattern = re.compile(
            r'(\d+)\.\s*(.+?)(?=\n\s*(?:ACTION:|DO:|$))',
            re.DOTALL
        )

        # Find all step starts
        step_starts = list(re.finditer(r'(?:^|\n)(\d+)\.\s*', steps_content))

        for i, match in enumerate(step_starts):
            step_num = match.group(1)
            start = match.end()

            # Find end of this step (start of next step or end of content)
            if i + 1 < len(step_starts):
                end = step_starts[i + 1].start()
            else:
                end = len(steps_content)

            step_text = steps_content[start:end]
            step = self._parse_single_step(step_num, step_text)

            if step:
                steps.append(step)

        return steps

    def _parse_single_step(self, step_num: str, text: str) -> Optional[PlanStep]:
        """Parse a single step from its text block."""
        # Get title (first line or up to first field)
        title_match = re.match(r'(.+?)(?=\n\s*(?:ACTION:|DO:)|$)', text, re.DOTALL)
        title = title_match.group(1).strip() if title_match else ""

        # Extract fields
        action_str = self._extract_field(text, "ACTION") or ""
        do = self._extract_field(text, "DO") or ""
        inp = self._extract_field(text, "IN") or "none"
        out = self._extract_field(text, "OUT") or ""
        done = self._extract_field(text, "DONE") or ""
        needs_str = self._extract_field(text, "NEEDS") or "none"

        # If DO is empty, use title as description
        if not do and title:
            do = title

        # Determine action
        action = self._infer_action(action_str, title)

        # Parse inputs
        inputs = self._parse_file_list(inp)

        # Parse dependencies
        needs = self._parse_needs(needs_str)

        # Validate minimum requirements
        if not do:
            self.warnings.append(f"Step {step_num}: Missing DO instruction")
            return None

        if not out and action in (StepAction.CREATE, StepAction.MODIFY):
            self.warnings.append(f"Step {step_num}: Missing OUT (target file)")

        if not done:
            self.warnings.append(f"Step {step_num}: Missing DONE (verification)")

        try:
            return PlanStep(
                id=f"step-{step_num}",
                action=action,
                target=out,
                description=do,
                done=done,
                inputs=inputs,
                needs=needs
            )
        except ValueError as e:
            self.errors.append(ParseError(f"Step {step_num}: {e}", field="STEP"))
            return None

    def _extract_field(self, text: str, field_name: str) -> Optional[str]:
        """Extract a field value like 'DO: value here'."""
        pattern = rf'{field_name}:\s*(.+?)(?=\n\s*(?:ACTION:|DO:|IN:|OUT:|DONE:|NEEDS:)|\n\n|\Z)'
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    def _infer_action(self, action_str: str, title: str) -> StepAction:
        """Infer action from explicit ACTION field or title verb."""
        # Check explicit ACTION field first
        if action_str:
            action_lower = action_str.lower().strip()
            if action_lower in [a.value for a in StepAction]:
                return StepAction(action_lower)

        # Infer from title
        title_lower = title.lower()
        for verb, action in self.ACTION_VERBS.items():
            if title_lower.startswith(verb):
                return action

        # Default to create
        return StepAction.CREATE

    def _parse_file_list(self, text: str) -> list[str]:
        """Parse comma-separated file list."""
        if not text or text.lower().strip() == "none":
            return []

        files = []
        for part in text.split(","):
            # Remove parenthetical notes like "(modified)"
            clean = re.sub(r'\s*\([^)]*\)\s*', '', part.strip())
            if clean and clean.lower() != "none":
                files.append(clean)

        return files

    def _parse_needs(self, text: str) -> list[str]:
        """Parse NEEDS field into step IDs."""
        if not text or text.lower().strip() == "none":
            return []

        needs = []
        # Match step numbers like "1", "2", "step-1", "1, 3, 5"
        for match in re.finditer(r'(?:step-)?(\d+)', text, re.IGNORECASE):
            needs.append(f"step-{match.group(1)}")

        return needs

    def _parse_bullets(self, text: str) -> list[str]:
        """Parse bullet list."""
        bullets = []
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('-') or line.startswith('*'):
                bullets.append(line.lstrip('-* ').strip())
        return bullets

    def _extract_verify(self, content: str) -> list[str]:
        """Extract VERIFY section."""
        # Try VERIFY: format
        match = re.search(
            r'(?:^|\n)VERIFY:\s*\n((?:\s*-\s*.+\n?)+)',
            content,
            re.IGNORECASE
        )
        if match:
            return self._parse_bullets(match.group(1))

        # Try ## Verify header
        match = re.search(
            r'(?:^|\n)##?\s*Verify\s*\n+((?:\s*-\s*.+\n?)+)',
            content,
            re.IGNORECASE
        )
        if match:
            return self._parse_bullets(match.group(1))

        return []

    def _derive_plan_id(self, goal: str) -> str:
        """Derive kebab-case plan ID from goal."""
        if not goal:
            return "unknown-plan"

        # Take first few meaningful words
        words = re.sub(r'[^\w\s]', '', goal.lower()).split()
        stop_words = {'a', 'an', 'the', 'to', 'for', 'with', 'and', 'or', 'in', 'on'}
        words = [w for w in words if w not in stop_words][:4]

        return '-'.join(words) if words else "unknown-plan"


# =============================================================================
# Convenience Functions
# =============================================================================

def parse_plan(content: str, plan_id: Optional[str] = None) -> ParseResult:
    """Parse plan content. Convenience function."""
    parser = PlanParser()
    return parser.parse(content, plan_id)


def parse_plan_file(path: Path) -> ParseResult:
    """Parse a plan file. Convenience function."""
    parser = PlanParser()
    return parser.parse_file(path)


def validate_plan_coverage(request: str, plan: ParsedPlan) -> tuple[bool, str]:
    """
    Validate that plan covers all numbered requirements in the request.

    Args:
        request: Original user request
        plan: Parsed plan

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Count numbered requirements in request: (1), (2) or 1), 2) or 1., 2.
    patterns = [
        r'\(\d+\)',           # (1), (2)
        r'(?:^|\s)\d+\)',     # 1), 2)
        r'(?:^|\n)\s*\d+\.',  # 1., 2.
    ]

    max_count = 0
    for pattern in patterns:
        matches = re.findall(pattern, request)
        max_count = max(max_count, len(matches))

    if max_count == 0:
        return True, ""  # No numbered requirements

    # Allow some flexibility (combining steps)
    min_acceptable = max(1, max_count - 2)

    if plan.total_steps < min_acceptable:
        return False, (
            f"Plan has {plan.total_steps} step(s) but request has {max_count} "
            f"numbered requirements. Expected at least {min_acceptable} steps."
        )

    return True, ""
