"""
Smart Planning Workflow: Analyzes complexity and decomposes large features.

For simple features: Scout → Architect → Planner → Validator
For complex features: Analyzer → Decomposer → [Sub-plans] → Synthesizer → Validator

Context Protection:
- Each sub-feature runs in isolated context
- Summarized context passed between agents
- Token budget tracked per agent
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..core import Agent, Workflow, WorkflowResult


@dataclass
class SubFeaturePlan:
    """Plan for a single sub-feature."""
    id: str
    name: str
    scout_result: str
    architect_result: str
    planner_result: str


class PlanningWorkflow(Workflow):
    """
    Smart planning workflow with complexity analysis and decomposition.

    For simple/medium features:
        Scout → Architect → Planner → Validator

    For complex/massive features:
        Analyzer → Decomposer → [Parallel Sub-Plans] → Synthesizer → Validator

    Each sub-plan runs in isolated context to prevent data loss.
    """

    # Context size limits - base values (scaled by _get_context_limits)
    BASE_CODEBASE_LIMIT = 4000   # For sub-feature codebase overview
    BASE_SCOUT_LIMIT = 3500      # For scout results in sub-features
    BASE_ARCHITECT_LIMIT = 2500  # For architect results
    MIN_CONTEXT_LIMIT = 1500     # Floor to ensure meaningful context

    def _get_context_limits(self, num_sub_features: int = 1) -> tuple[int, int, int]:
        """
        Adaptive context limits based on parallelism.
        More sub-features = smaller per-feature context to manage total tokens.
        Fewer sub-features = richer context per feature.
        """
        # Scale factor: 1.0 for 1 feature, 0.6 for 5+ features
        scale = max(0.6, 1.0 - (num_sub_features - 1) * 0.1)

        return (
            max(self.MIN_CONTEXT_LIMIT, int(self.BASE_CODEBASE_LIMIT * scale)),
            max(self.MIN_CONTEXT_LIMIT, int(self.BASE_SCOUT_LIMIT * scale)),
            max(self.MIN_CONTEXT_LIMIT, int(self.BASE_ARCHITECT_LIMIT * scale)),
        )

    def __init__(
        self,
        project_root: Path,
        output_dir: Optional[Path] = None,
        max_parallel: int = 3,  # Max parallel sub-agents
    ):
        self.project_root = project_root
        self.max_parallel = max_parallel
        # Plans go to pending folder by default
        output_dir = output_dir or project_root / ".specs" / "pending"
        output_dir.mkdir(parents=True, exist_ok=True)

        super().__init__(name="Smart Planning Workflow", output_dir=output_dir)

        # Load all agents from .claude/agents/
        self._load_agents()

    def _load_agents(self):
        """Load all agents from .claude/agents/"""
        agents = ["analyzer", "decomposer", "scout", "architect", "planner", "validator", "synthesizer"]
        for agent_name in agents:
            try:
                self.register_agent(Agent.load(agent_name, self.project_root))
            except FileNotFoundError:
                self.console.print(f"[yellow]Warning: Agent '{agent_name}' not found[/yellow]")

    def _get_codebase_context(self) -> str:
        """Gather basic codebase context."""
        context_parts = []

        try:
            items = list(self.project_root.iterdir())
            dirs = [i.name for i in items if i.is_dir() and not i.name.startswith('.')]
            files = [i.name for i in items if i.is_file() and not i.name.startswith('.')]

            context_parts.append("## Project Structure")
            context_parts.append(f"Directories: {', '.join(sorted(dirs)[:20])}")
            context_parts.append(f"Root files: {', '.join(sorted(files)[:20])}")
        except Exception:
            pass

        config_files = ["package.json", "pyproject.toml", "Cargo.toml", "go.mod", "requirements.txt"]
        found_configs = [f for f in config_files if (self.project_root / f).exists()]
        if found_configs:
            context_parts.append(f"\nConfig files: {', '.join(found_configs)}")

        return "\n".join(context_parts)

    def _smart_truncate(self, text: str, limit: int, preserve_start: int = 0) -> str:
        """
        Intelligently truncate text while preserving structure.

        - If text fits within limit, return as-is
        - Otherwise, preserve beginning (structure) and add truncation marker
        - preserve_start: minimum chars to always keep from start
        """
        if len(text) <= limit:
            return text

        # Ensure we keep at least some meaningful content
        preserve = max(preserve_start, limit // 3)
        truncated = text[:limit - 50]  # Leave room for marker

        # Try to break at a newline for cleaner output
        last_newline = truncated.rfind('\n', preserve, len(truncated))
        if last_newline > preserve:
            truncated = truncated[:last_newline]

        return truncated + f"\n\n... [truncated {len(text) - len(truncated)} chars]"

    def _generate_filename(self, request: str) -> str:
        """Generate a kebab-case filename."""
        words = re.sub(r'[^\w\s]', '', request.lower()).split()
        stop_words = {'a', 'an', 'the', 'to', 'for', 'with', 'and', 'or', 'in', 'on', 'add', 'create', 'implement'}
        words = [w for w in words if w not in stop_words][:5]
        return '-'.join(words) + '.md'

    def _parse_json_from_response(self, response: str) -> dict:
        """Extract JSON from agent response."""
        # Try to find JSON block
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try parsing whole response as JSON
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {}

    def _run_simple_planning(self, request: str, codebase_context: str) -> WorkflowResult:
        """Run simple 4-agent planning for non-complex features."""
        steps_completed = []

        # Scout
        self.console.print("[bold]Phase 1:[/bold] Scouting codebase...")
        scout_result = self.run_agent(
            "scout",
            message=f"User request: {request}\n\nGather context about this codebase.",
            context=codebase_context
        )
        if not scout_result.success:
            return WorkflowResult(success=False, error=f"Scout failed: {scout_result.error}")
        steps_completed.append("scout")

        # Architect
        self.console.print("\n[bold]Phase 2:[/bold] Designing architecture...")
        architect_result = self.run_agent(
            "architect",
            message=f"User request: {request}\n\nDesign the architecture.",
            context=f"## Codebase Context\n\n{scout_result.content}"
        )
        if not architect_result.success:
            return WorkflowResult(success=False, error=f"Architect failed: {architect_result.error}")
        steps_completed.append("architect")

        # Planner
        self.console.print("\n[bold]Phase 3:[/bold] Creating implementation plan...")
        planner_result = self.run_agent(
            "planner",
            message=f"User request: {request}\n\nCreate detailed implementation steps.",
            context=f"## Context\n\n{scout_result.content}\n\n## Architecture\n\n{architect_result.content}"
        )
        if not planner_result.success:
            return WorkflowResult(success=False, error=f"Planner failed: {planner_result.error}")
        steps_completed.append("planner")

        # Validator
        self.console.print("\n[bold]Phase 4:[/bold] Validating plan...")
        validator_result = self.run_agent(
            "validator",
            message=f"Validate this implementation plan for: {request}",
            context=f"## Plan\n\n{planner_result.content}"
        )
        if not validator_result.success:
            return WorkflowResult(success=False, error=f"Validator failed: {validator_result.error}")
        steps_completed.append("validator")

        # Compile and save
        final_plan = self._compile_simple_plan(
            request=request,
            scout=scout_result.content,
            architect=architect_result.content,
            planner=planner_result.content,
            validator=validator_result.content
        )

        filename = self._generate_filename(request)
        output_path = self.save_output(filename, final_plan)

        return WorkflowResult(
            success=True,
            output_file=output_path,
            steps_completed=steps_completed
        )

    def _plan_sub_feature(
        self,
        sub_feature: dict,
        codebase_context: str,
        cached_scout: Optional[str] = None,
        num_sub_features: int = 1
    ) -> SubFeaturePlan:
        """
        Plan a single sub-feature in isolated context.
        Each sub-feature gets minimal, summarized context.

        Args:
            sub_feature: Feature definition from decomposer
            codebase_context: Basic codebase structure
            cached_scout: Optional pre-computed global scout result to avoid redundant exploration
            num_sub_features: Total number of sub-features (for adaptive context sizing)
        """
        sf_id = sub_feature.get("id", "unknown")
        sf_name = sub_feature.get("name", "Unknown Feature")
        sf_description = sub_feature.get("description", "")
        sf_context = sub_feature.get("context_summary", "")

        # Get adaptive limits based on parallelism
        codebase_limit, scout_limit, architect_limit = self._get_context_limits(num_sub_features)

        # Build focused context for this sub-feature
        codebase_summary = self._smart_truncate(
            codebase_context,
            codebase_limit,
            preserve_start=500  # Keep directory structure
        )

        focused_context = f"""## Sub-Feature Context

**Feature:** {sf_name}
**Description:** {sf_description}

**Relevant Context:**
{sf_context}

**Codebase Overview:**
{codebase_summary}
"""

        # If we have cached global scout results, include them to avoid redundant exploration
        if cached_scout:
            cached_summary = self._smart_truncate(cached_scout, scout_limit)
            focused_context += f"""
**Global Codebase Insights (from initial scout):**
{cached_summary}
"""

        # Scout for this sub-feature (now does targeted exploration, not full codebase scan)
        scout_result = self.run_agent(
            "scout",
            message=f"Sub-feature: {sf_name}\n\n{sf_description}\n\nGather relevant context for THIS specific feature.",
            context=focused_context,
            show_progress=False
        )

        # Architect for this sub-feature
        scout_for_architect = self._smart_truncate(scout_result.content, scout_limit)
        architect_result = self.run_agent(
            "architect",
            message=f"Sub-feature: {sf_name}\n\n{sf_description}\n\nDesign the approach.",
            context=f"## Scout Context\n\n{scout_for_architect}",
            show_progress=False
        )

        # Planner for this sub-feature
        scout_for_planner = self._smart_truncate(scout_result.content, architect_limit)
        arch_for_planner = self._smart_truncate(architect_result.content, architect_limit)
        planner_result = self.run_agent(
            "planner",
            message=f"Sub-feature: {sf_name}\n\n{sf_description}\n\nCreate implementation steps.",
            context=f"## Context\n\n{scout_for_planner}\n\n## Architecture\n\n{arch_for_planner}",
            show_progress=False
        )

        return SubFeaturePlan(
            id=sf_id,
            name=sf_name,
            scout_result=scout_result.content,
            architect_result=architect_result.content,
            planner_result=planner_result.content
        )

    def _run_complex_planning(self, request: str, codebase_context: str, analysis: dict) -> WorkflowResult:
        """Run decomposed planning for complex features."""
        steps_completed = []

        # Phase 2a: Run global scout ONCE to cache common codebase context
        # This avoids redundant full-codebase exploration in each sub-feature
        self.console.print("\n[bold]Phase 2a:[/bold] Global codebase scouting...")
        global_scout = self.run_agent(
            "scout",
            message=f"User request: {request}\n\nGather comprehensive context about this codebase for multi-feature planning.",
            context=codebase_context
        )
        cached_scout_result = global_scout.content if global_scout.success else None
        if global_scout.success:
            steps_completed.append("global_scout")
            self.console.print("  [green]✓[/green] Global scout cached")
        else:
            self.console.print("  [yellow]⚠[/yellow] Global scout failed, sub-features will scout independently")

        # Phase 2b: Decompose
        self.console.print("\n[bold]Phase 2b:[/bold] Decomposing into sub-features...")
        decomposer_context = f"## Analysis\n\n{json.dumps(analysis, indent=2)}\n\n## Codebase\n\n{codebase_context}"
        if cached_scout_result:
            scout_summary = self._smart_truncate(cached_scout_result, self.BASE_SCOUT_LIMIT)
            decomposer_context += f"\n\n## Scout Insights\n\n{scout_summary}"

        decomposer_result = self.run_agent(
            "decomposer",
            message=f"Original request: {request}\n\nBreak this into independent sub-features for parallel planning.",
            context=decomposer_context
        )
        if not decomposer_result.success:
            return WorkflowResult(success=False, error=f"Decomposer failed: {decomposer_result.error}")
        steps_completed.append("decomposer")

        decomposition = self._parse_json_from_response(decomposer_result.content)
        sub_features = decomposition.get("sub_features", [])

        if not sub_features:
            self.console.print("[yellow]No sub-features found, falling back to simple planning[/yellow]")
            return self._run_simple_planning(request, codebase_context)

        # Phase 3: Plan each sub-feature (with cached scout context)
        self.console.print(f"\n[bold]Phase 3:[/bold] Planning {len(sub_features)} sub-features...")
        sub_plans: list[SubFeaturePlan] = []

        strategy = analysis.get("strategy", "decompose_sequential")

        num_features = len(sub_features)
        codebase_limit, scout_limit, _ = self._get_context_limits(num_features)
        self.console.print(f"  Context limits: codebase={codebase_limit}, scout={scout_limit} (scaled for {num_features} features)")

        if strategy == "decompose_parallel" and num_features > 1:
            # Parallel planning with isolated contexts (but shared cached scout)
            self.console.print(f"  Running up to {self.max_parallel} in parallel...")

            with ThreadPoolExecutor(max_workers=self.max_parallel) as executor:
                futures = {
                    executor.submit(
                        self._plan_sub_feature, sf, codebase_context, cached_scout_result, num_features
                    ): sf
                    for sf in sub_features
                }

                for future in as_completed(futures):
                    sf = futures[future]
                    try:
                        plan = future.result()
                        sub_plans.append(plan)
                        self.console.print(f"  [green]✓[/green] {plan.name}")
                    except Exception as e:
                        self.console.print(f"  [red]✗[/red] {sf.get('name', 'Unknown')}: {e}")
        else:
            # Sequential planning (with cached scout)
            for sf in sub_features:
                self.console.print(f"  Planning: {sf.get('name', 'Unknown')}...")
                plan = self._plan_sub_feature(sf, codebase_context, cached_scout_result, num_features)
                sub_plans.append(plan)
                self.console.print(f"  [green]✓[/green] {plan.name}")

        steps_completed.append(f"sub_plans ({len(sub_plans)})")

        # Synthesize
        self.console.print("\n[bold]Phase 4:[/bold] Synthesizing master plan...")

        sub_plans_text = "\n\n---\n\n".join([
            f"## Sub-Feature: {sp.name}\n\n### Architecture\n{sp.architect_result}\n\n### Implementation\n{sp.planner_result}"
            for sp in sub_plans
        ])

        synthesizer_result = self.run_agent(
            "synthesizer",
            message=f"Original request: {request}\n\nCombine these sub-feature plans into a master plan.",
            context=f"## Sub-Feature Plans\n\n{sub_plans_text}"
        )
        if not synthesizer_result.success:
            return WorkflowResult(success=False, error=f"Synthesizer failed: {synthesizer_result.error}")
        steps_completed.append("synthesizer")

        # Validate
        self.console.print("\n[bold]Phase 5:[/bold] Validating master plan...")
        validator_result = self.run_agent(
            "validator",
            message=f"Validate this master implementation plan for: {request}",
            context=f"## Master Plan\n\n{synthesizer_result.content}"
        )
        if not validator_result.success:
            return WorkflowResult(success=False, error=f"Validator failed: {validator_result.error}")
        steps_completed.append("validator")

        # Save master plan
        final_plan = self._compile_master_plan(
            request=request,
            analysis=analysis,
            decomposition=decomposition,
            sub_plans=sub_plans,
            synthesis=synthesizer_result.content,
            validation=validator_result.content
        )

        filename = "master-" + self._generate_filename(request)
        output_path = self.save_output(filename, final_plan)

        return WorkflowResult(
            success=True,
            output_file=output_path,
            steps_completed=steps_completed,
            data={
                "complexity": analysis.get("complexity"),
                "sub_features": len(sub_plans),
                "strategy": strategy
            }
        )

    def execute(self, request: str) -> WorkflowResult:
        """Execute the smart planning workflow."""

        codebase_context = self._get_codebase_context()

        # Phase 1: Analyze complexity
        self.console.print("[bold]Phase 1:[/bold] Analyzing complexity...")
        analyzer_result = self.run_agent(
            "analyzer",
            message=f"Analyze this feature request: {request}",
            context=codebase_context
        )

        if not analyzer_result.success:
            self.console.print("[yellow]Analyzer failed, using simple planning[/yellow]")
            return self._run_simple_planning(request, codebase_context)

        analysis = self._parse_json_from_response(analyzer_result.content)
        complexity = analysis.get("complexity", "simple")
        needs_decomposition = analysis.get("needs_decomposition", False)

        self.console.print(f"  Complexity: [cyan]{complexity}[/cyan]")
        self.console.print(f"  Decomposition needed: [cyan]{needs_decomposition}[/cyan]")

        if needs_decomposition and complexity in ["complex", "massive"]:
            return self._run_complex_planning(request, codebase_context, analysis)
        else:
            return self._run_simple_planning(request, codebase_context)

    def _compile_simple_plan(self, request: str, scout: str, architect: str, planner: str, validator: str) -> str:
        """Compile simple plan."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        return f"""# Plan: {request}

> Generated on {timestamp}
> Complexity: Simple/Medium (single-pass planning)

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
"""

    def _compile_master_plan(
        self,
        request: str,
        analysis: dict,
        decomposition: dict,
        sub_plans: list[SubFeaturePlan],
        synthesis: str,
        validation: str
    ) -> str:
        """Compile master plan from decomposed planning."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        complexity = analysis.get("complexity", "complex")

        sub_features_summary = "\n".join([
            f"- **{sp.name}** ({sp.id})"
            for sp in sub_plans
        ])

        return f"""# Master Plan: {request}

> Generated on {timestamp}
> Complexity: {complexity.upper()} (decomposed planning)
> Sub-features: {len(sub_plans)}

## Overview

**Request:** {request}

### Analysis
- Complexity: {complexity}
- Strategy: {analysis.get('strategy', 'decompose_sequential')}
- Estimated steps: {analysis.get('estimated_steps', 'N/A')}

### Sub-Features Planned
{sub_features_summary}

---

## Master Implementation Plan

{synthesis}

---

## Validation

{validation}

---

## Execution Notes

1. Follow the phases in order
2. Parallelize where indicated
3. Run validation commands after each phase
4. Integration testing after all features complete
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
