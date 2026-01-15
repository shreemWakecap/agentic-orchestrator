"""
Smart Planning Workflow: Analyzes complexity and decomposes large features.

For simple features: Scout → Architect → [Expert Consultation] → Planner → Validator
For complex features: Analyzer → [Expert Consultation] → Decomposer → [Sub-plans] → Synthesizer → Validator

Context Protection:
- Each sub-feature runs in isolated context
- Summarized context passed between agents
- Token budget tracked per agent

Expert Consultation:
- All domain/module experts are consulted during planning
- Expert insights feed into the planner for domain-aware plans
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from core import Agent, Workflow, WorkflowResult, get_agent_config
from core.expert_loader import ExpertLoader, ExpertType
from core.docs_loader import DocsLoader
from core.scout_cache import ScoutCache
from core.checkpoint import CheckpointManager, PlanningCheckpoint


@dataclass
class SubFeaturePlan:
    """Plan for a single sub-feature."""
    id: str
    name: str
    scout_result: str
    architect_result: str
    planner_result: str


@dataclass
class ExpertInsight:
    """Insight from a domain/module expert during planning."""
    expert_name: str
    expert_type: str
    insights: str
    recommendations: list[str] = field(default_factory=list)
    concerns: list[str] = field(default_factory=list)


@dataclass
class AdaptiveConfig:
    """Configuration derived from analyzer for adaptive workflow behavior."""
    complexity: str  # simple, medium, complex, massive
    output_format: str  # minimal, standard, full
    agent_depth: str  # brief, moderate, thorough
    needs_decomposition: bool
    estimated_steps: int
    estimated_files: int
    factors: dict = field(default_factory=dict)

    @classmethod
    def from_analysis(cls, analysis: dict) -> "AdaptiveConfig":
        """Create AdaptiveConfig from analyzer output with sensible fallbacks."""
        return cls(
            complexity=analysis.get("complexity", "simple"),
            output_format=analysis.get("output_format", "standard"),
            agent_depth=analysis.get("agent_depth", "moderate"),
            needs_decomposition=analysis.get("needs_decomposition", False),
            estimated_steps=analysis.get("estimated_steps", 5),
            estimated_files=analysis.get("estimated_files", 3),
            factors=analysis.get("factors", {})
        )

    @classmethod
    def default_simple(cls) -> "AdaptiveConfig":
        """Default config for when analyzer fails - use moderate settings."""
        return cls(
            complexity="simple",
            output_format="standard",
            agent_depth="moderate",
            needs_decomposition=False,
            estimated_steps=5,
            estimated_files=3
        )


class PlanningWorkflow(Workflow):
    """
    Smart planning workflow with complexity analysis and decomposition.

    For simple/medium features:
        Scout → Architect → Planner → Validator

    For complex/massive features:
        Analyzer → Decomposer → [Parallel Sub-Plans] → Synthesizer → Validator

    Each sub-plan runs in isolated context to prevent data loss.
    """

    def _get_context_limits(self, num_sub_features: int = 1) -> tuple[int, int, int]:
        """
        Adaptive context limits based on parallelism.
        More sub-features = smaller per-feature context to manage total tokens.
        Fewer sub-features = richer context per feature.
        """
        # Scale factor: 1.0 for 1 feature, 0.6 for 5+ features
        scale = max(0.6, 1.0 - (num_sub_features - 1) * 0.1)

        ctx = self._config.context_limits
        return (
            max(ctx.minimum, int(ctx.base_codebase * scale)),
            max(ctx.minimum, int(ctx.base_scout * scale)),
            max(ctx.minimum, int(ctx.base_architect * scale)),
        )

    def __init__(
        self,
        project_root: Path,
        output_dir: Optional[Path] = None,
        max_parallel: Optional[int] = None,
    ):
        self.project_root = project_root
        self._config = get_agent_config(project_root)
        self.max_parallel = max_parallel or self._config.parallel.max_sub_features
        # Plans go to pending folder by default
        output_dir = output_dir or project_root / ".orchestrator" / "specs" / "pending"
        output_dir.mkdir(parents=True, exist_ok=True)

        super().__init__(name="Smart Planning Workflow", output_dir=output_dir)

        # Initialize expert loader for domain/module expert consultation
        self.expert_loader = ExpertLoader(project_root)

        # Initialize scout cache for avoiding redundant codebase exploration
        self.scout_cache = ScoutCache(project_root)

        # Initialize checkpoint manager for recovery
        specs_dir = project_root / ".orchestrator" / "specs"
        self.checkpoint_mgr = CheckpointManager(specs_dir)

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

    def _get_docs_context(self) -> str:
        """Load project documentation context."""
        try:
            docs_loader = DocsLoader(self.project_root)
            docs = docs_loader.load_docs()
            if docs and docs.docs:
                return docs.get_context_string(max_chars=4000)
        except Exception:
            pass
        return ""

    def _build_depth_context(self, agent_name: str, depth: str, base_context: str) -> str:
        """
        Build context for an agent.

        Note: Depth instructions have been removed for simplicity.
        All plans now use a single minimal format.
        """
        return base_context

    def _consult_domain_experts(
        self,
        request: str,
        architect_result: str,
        codebase_context: str
    ) -> list[ExpertInsight]:
        """
        Consult ALL domain/module experts for planning insights.

        Runs experts in parallel with ThreadPoolExecutor.
        Each expert receives:
        - The user's request
        - Architecture design from architect agent
        - Codebase context from scout
        - Project documentation

        Returns:
            List of ExpertInsight with recommendations and concerns
        """
        from core.symbols import CHECK, WARNING

        domain_experts = self.expert_loader.get_all_domain_experts()

        if not domain_experts:
            return []

        self.console.print(f"\n[bold]Expert Consultation:[/bold] Consulting {len(domain_experts)} domain expert(s)...")

        # Build context for experts
        docs_context = self._get_docs_context()

        expert_context = f"""## User Request
{request}

## Architecture Design
{architect_result}

## Codebase Context
{codebase_context}
"""
        if docs_context:
            expert_context += f"\n## Project Documentation\n{docs_context}"

        expert_prompt = """Based on the user request and architecture design, provide planning insights from your domain expertise.

Respond in this JSON format:
```json
{
    "insights": "Your analysis of how this request relates to your domain",
    "recommendations": ["Specific recommendation 1", "Specific recommendation 2"],
    "concerns": ["Potential concern or risk 1", "Potential concern or risk 2"]
}
```

Focus on:
- Domain-specific patterns and best practices
- Potential pitfalls or anti-patterns to avoid
- Security or performance considerations in your domain
- Integration points with other parts of the system
"""

        insights: list[ExpertInsight] = []

        def consult_expert(expert) -> Optional[ExpertInsight]:
            """Consult a single expert."""
            try:
                result = expert.run(expert_prompt, context=expert_context)
                if result.success and result.content:
                    # Parse JSON response
                    parsed = self._parse_json_from_response(result.content)
                    return ExpertInsight(
                        expert_name=expert.name,
                        expert_type=getattr(expert, 'expert_type', 'domain'),
                        insights=parsed.get("insights", result.content),
                        recommendations=parsed.get("recommendations", []),
                        concerns=parsed.get("concerns", [])
                    )
            except Exception as e:
                self.console.print(f"  [yellow]{WARNING}[/yellow] {expert.name}: {e}")
            return None

        # Run expert consultations in parallel with timeout
        max_expert_workers = self._config.parallel.max_expert_workers
        expert_timeout = self._config.timeouts.expert_consultation
        with ThreadPoolExecutor(max_workers=max_expert_workers) as executor:
            futures = {
                executor.submit(consult_expert, expert): expert
                for expert in domain_experts
            }

            for future in as_completed(futures, timeout=expert_timeout + 10):
                expert = futures[future]
                try:
                    # Also timeout individual results in case as_completed doesn't catch it
                    insight = future.result(timeout=expert_timeout)
                    if insight:
                        insights.append(insight)
                        self.console.print(f"  [green]{CHECK}[/green] {expert.name}")
                except TimeoutError:
                    self.console.print(f"  [yellow]{WARNING}[/yellow] {expert.name}: Timed out after {expert_timeout}s")
                except Exception as e:
                    self.console.print(f"  [yellow]{WARNING}[/yellow] {expert.name}: {e}")

        return insights

    def _compile_expert_insights(self, insights: list[ExpertInsight]) -> str:
        """Compile expert insights into context string for planner."""
        if not insights:
            return ""

        sections = ["## Domain Expert Insights\n"]

        for insight in insights:
            sections.append(f"### {insight.expert_name} ({insight.expert_type})\n")
            sections.append(insight.insights)

            if insight.recommendations:
                sections.append("\n**Recommendations:**")
                for rec in insight.recommendations:
                    sections.append(f"- {rec}")

            if insight.concerns:
                sections.append("\n**Concerns:**")
                for concern in insight.concerns:
                    sections.append(f"- {concern}")

            sections.append("")

        return "\n".join(sections)

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
            # Agent already retried and couldn't get good output - fail the workflow
            return False, (
                f"{agent_name} returned a placeholder response after retries. "
                f"Details: {result.error}"
            )

        return True, ""

    def _get_next_plan_number(self) -> int:
        """
        Get the next sequential plan number.

        Scans the output directory for existing plan folders with numeric prefixes
        (e.g., 001_feature-name) and returns the next number in sequence.
        """
        max_num = 0
        if self.output_dir.exists():
            for item in self.output_dir.iterdir():
                if item.is_dir():
                    # Match pattern: NNN_name or NNN-name
                    match = re.match(r'^(\d+)[_-]', item.name)
                    if match:
                        num = int(match.group(1))
                        max_num = max(max_num, num)
        return max_num + 1

    def _generate_plan_dirname(self, request: str, prefix: str = "") -> str:
        """
        Generate a kebab-case directory name with sequential prefix.

        Args:
            request: The user's request
            prefix: Optional prefix like "master-" for complex plans

        Returns:
            Directory name like "001_user-authentication" or "002_master-oauth-system"
        """
        plan_num = self._get_next_plan_number()
        words = re.sub(r'[^\w\s]', '', request.lower()).split()
        stop_words = {'a', 'an', 'the', 'to', 'for', 'with', 'and', 'or', 'in', 'on', 'add', 'create', 'implement'}
        words = [w for w in words if w not in stop_words][:5]
        name_part = '-'.join(words)
        if prefix:
            name_part = f"{prefix}{name_part}"
        return f"{plan_num:03d}_{name_part}"

    def _save_plan_folder(self, dirname: str, files: dict[str, str]) -> Path:
        """
        Save plan as a folder with multiple files.

        Args:
            dirname: Directory name (e.g., "001_user-authentication")
            files: Dict mapping filename to content (e.g., {"00_overview.md": "..."})

        Returns:
            Path to the created plan directory
        """
        plan_dir = self.output_dir / dirname
        plan_dir.mkdir(parents=True, exist_ok=True)

        for filename, content in files.items():
            file_path = plan_dir / filename
            file_path.write_text(content, encoding="utf-8")

        return plan_dir

    def _generate_filename(self, request: str) -> str:
        """Generate a kebab-case filename. DEPRECATED: Use _generate_plan_dirname instead."""
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

    def _run_simple_planning(
        self,
        request: str,
        codebase_context: str,
        adaptive: Optional[AdaptiveConfig] = None
    ) -> WorkflowResult:
        """
        Run simple 4-agent planning for non-complex features.

        Args:
            request: User's feature request
            codebase_context: Basic codebase context
            adaptive: Optional AdaptiveConfig for depth-aware processing
        """
        steps_completed = []

        # Use default config if not provided (backward compatibility)
        if adaptive is None:
            adaptive = AdaptiveConfig.default_simple()

        depth = adaptive.agent_depth
        request_hash = self.checkpoint_mgr.compute_request_hash(request)

        # Check for existing checkpoint to resume from
        existing_checkpoint = self.checkpoint_mgr.load(request)
        if existing_checkpoint and existing_checkpoint.phase != "completed":
            from core.symbols import WARNING
            self.console.print(f"[yellow]{WARNING} Found checkpoint at phase: {existing_checkpoint.phase}[/yellow]")
            self.console.print("  Resuming from last successful phase...")

        # Check for cached scout result
        self.console.print("[bold]Phase 1:[/bold] Scouting codebase...")
        cached_scout = self.scout_cache.get(request)
        if cached_scout:
            from core.symbols import CHECK
            self.console.print(f"  [green]{CHECK}[/green] Using cached scout result")
            scout_content = cached_scout
        else:
            scout_context = self._build_depth_context("scout", depth, codebase_context)
            scout_result = self.run_agent(
                "scout",
                message=f"User request: {request}\n\nGather context about this codebase.",
                context=scout_context
            )
            valid, error = self._validate_agent_response("Scout", scout_result)
            if not valid:
                return WorkflowResult(success=False, error=error)
            scout_content = scout_result.content
            # Cache the result
            self.scout_cache.set(request, scout_content)
        steps_completed.append("scout")

        # Save checkpoint after scout
        self.checkpoint_mgr.save(PlanningCheckpoint(
            request=request,
            request_hash=request_hash,
            phase="scout",
            complexity=adaptive.complexity,
            scout_result=scout_content
        ))

        # Architect with depth-aware context
        self.console.print("\n[bold]Phase 2:[/bold] Designing architecture...")
        architect_base_context = f"## Codebase Context\n\n{scout_content}"
        architect_context = self._build_depth_context("architect", depth, architect_base_context)
        architect_result = self.run_agent(
            "architect",
            message=f"User request: {request}\n\nDesign the architecture.",
            context=architect_context
        )
        valid, error = self._validate_agent_response("Architect", architect_result)
        if not valid:
            return WorkflowResult(success=False, error=error)
        steps_completed.append("architect")

        # Save checkpoint after architect
        self.checkpoint_mgr.save(PlanningCheckpoint(
            request=request,
            request_hash=request_hash,
            phase="architect",
            complexity=adaptive.complexity,
            scout_result=scout_content,
            architect_result=architect_result.content
        ))

        # Expert Consultation - skip for brief depth to save time
        expert_insights = []
        expert_context = ""
        if depth != "brief":
            expert_insights = self._consult_domain_experts(
                request=request,
                architect_result=architect_result.content,
                codebase_context=scout_content
            )
            expert_context = self._compile_expert_insights(expert_insights)
            if expert_insights:
                steps_completed.append(f"expert_consultation ({len(expert_insights)})")
        else:
            self.console.print("\n[dim]Skipping expert consultation (brief mode)[/dim]")

        # Planner with depth-aware context
        self.console.print("\n[bold]Phase 3:[/bold] Creating implementation plan...")
        planner_base_context = f"## Context\n\n{scout_content}\n\n## Architecture\n\n{architect_result.content}"
        if expert_context:
            planner_base_context += f"\n\n{expert_context}"
        planner_context = self._build_depth_context("planner", depth, planner_base_context)

        planner_result = self.run_agent(
            "planner",
            message=f"User request: {request}\n\nCreate detailed implementation steps.",
            context=planner_context
        )
        valid, error = self._validate_agent_response("Planner", planner_result)
        if not valid:
            return WorkflowResult(success=False, error=error)
        steps_completed.append("planner")

        # Save checkpoint after planner
        self.checkpoint_mgr.save(PlanningCheckpoint(
            request=request,
            request_hash=request_hash,
            phase="planner",
            complexity=adaptive.complexity,
            scout_result=scout_content,
            architect_result=architect_result.content,
            planner_result=planner_result.content
        ))

        # Validator with depth-aware context
        self.console.print("\n[bold]Phase 4:[/bold] Validating plan...")
        validator_base_context = f"## Plan\n\n{planner_result.content}"
        validator_context = self._build_depth_context("validator", depth, validator_base_context)
        validator_result = self.run_agent(
            "validator",
            message=f"Validate this implementation plan for: {request}",
            context=validator_context
        )
        valid, error = self._validate_agent_response("Validator", validator_result)
        if not valid:
            return WorkflowResult(success=False, error=error)

        # VALIDATION GATE: Check if plan actually passed validation
        validation_data = self._parse_json_from_response(validator_result.content)
        validation_status = validation_data.get("status", "unknown")
        validation_score = validation_data.get("score", 0)

        if validation_status != "approved" or validation_score < 70:
            blocking_issues = validation_data.get("blocking_issues", [])
            issue_summary = "; ".join(
                issue.get("issue", "unknown")[:60]
                for issue in blocking_issues[:3]
            ) if blocking_issues else "Plan did not meet quality threshold"

            from core.symbols import CROSS
            self.console.print(f"\n[red]{CROSS} Plan validation failed[/red]")
            self.console.print(f"  Status: {validation_status}, Score: {validation_score}/100")
            if blocking_issues:
                self.console.print("  Issues:")
                for issue in blocking_issues[:5]:
                    step = issue.get("step", "?")
                    issue_text = issue.get("issue", "Unknown issue")
                    self.console.print(f"    - Step {step}: {issue_text[:70]}")

            return WorkflowResult(
                success=False,
                error=f"Plan validation failed (score {validation_score}): {issue_summary}",
                data={"validation": validation_data}
            )

        steps_completed.append("validator")

        # Compile as single plan.md file
        plan_files = self._compile_single_plan(
            request=request,
            scout=scout_content,
            architect=architect_result.content,
            planner=planner_result.content,
            validator=validator_result.content,
            expert_insights=expert_insights,
            adaptive=adaptive
        )

        dirname = self._generate_plan_dirname(request)
        output_path = self._save_plan_folder(dirname, plan_files)

        # Clear checkpoint on success
        self.checkpoint_mgr.clear(request)

        return WorkflowResult(
            success=True,
            output_file=output_path,
            steps_completed=steps_completed,
            data={
                "complexity": adaptive.complexity,
                "output_format": adaptive.output_format,
                "agent_depth": adaptive.agent_depth,
                "validation_score": validation_score
            }
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
        valid, error = self._validate_agent_response("Scout", scout_result)
        if not valid:
            raise ValueError(f"Sub-feature '{sf_name}': {error}")

        # Architect for this sub-feature
        scout_for_architect = self._smart_truncate(scout_result.content, scout_limit)
        architect_result = self.run_agent(
            "architect",
            message=f"Sub-feature: {sf_name}\n\n{sf_description}\n\nDesign the approach.",
            context=f"## Scout Context\n\n{scout_for_architect}",
            show_progress=False
        )
        valid, error = self._validate_agent_response("Architect", architect_result)
        if not valid:
            raise ValueError(f"Sub-feature '{sf_name}': {error}")

        # Planner for this sub-feature
        scout_for_planner = self._smart_truncate(scout_result.content, architect_limit)
        arch_for_planner = self._smart_truncate(architect_result.content, architect_limit)
        planner_result = self.run_agent(
            "planner",
            message=f"Sub-feature: {sf_name}\n\n{sf_description}\n\nCreate implementation steps.",
            context=f"## Context\n\n{scout_for_planner}\n\n## Architecture\n\n{arch_for_planner}",
            show_progress=False
        )
        valid, error = self._validate_agent_response("Planner", planner_result)
        if not valid:
            raise ValueError(f"Sub-feature '{sf_name}': {error}")

        return SubFeaturePlan(
            id=sf_id,
            name=sf_name,
            scout_result=scout_result.content,
            architect_result=architect_result.content,
            planner_result=planner_result.content
        )

    def _run_complex_planning(
        self,
        request: str,
        codebase_context: str,
        analysis: dict,
        adaptive: Optional[AdaptiveConfig] = None
    ) -> WorkflowResult:
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
        from core.symbols import CHECK, WARNING
        # Check for both failure AND placeholder responses
        valid, _ = self._validate_agent_response("Global Scout", global_scout)
        if valid:
            cached_scout_result = global_scout.content
            steps_completed.append("global_scout")
            self.console.print(f"  [green]{CHECK}[/green] Global scout cached")
        else:
            cached_scout_result = None
            self.console.print(f"  [yellow]{WARNING}[/yellow] Global scout failed or returned placeholder, sub-features will scout independently")

        # Phase 2b: Expert Consultation (for complex features)
        # Run a preliminary architect to get high-level design for expert consultation
        self.console.print("\n[bold]Phase 2b:[/bold] Preliminary architecture for expert consultation...")
        prelim_architect = self.run_agent(
            "architect",
            message=f"User request: {request}\n\nProvide high-level architectural overview for a complex multi-feature implementation.",
            context=f"## Analysis\n\n{json.dumps(analysis, indent=2)}\n\n## Codebase Context\n\n{cached_scout_result or codebase_context}"
        )
        # Check for both failure AND placeholder responses
        valid, _ = self._validate_agent_response("Prelim Architect", prelim_architect)
        if valid:
            prelim_arch_result = prelim_architect.content
            steps_completed.append("prelim_architect")
        else:
            prelim_arch_result = ""
            self.console.print(f"  [yellow]{WARNING}[/yellow] Preliminary architect returned placeholder, continuing without")

        # Consult domain experts
        expert_insights = self._consult_domain_experts(
            request=request,
            architect_result=prelim_arch_result,
            codebase_context=cached_scout_result or codebase_context
        )
        expert_context = self._compile_expert_insights(expert_insights)
        if expert_insights:
            steps_completed.append(f"expert_consultation ({len(expert_insights)})")

        # Phase 2c: Decompose
        self.console.print("\n[bold]Phase 2c:[/bold] Decomposing into sub-features...")
        decomposer_context = f"## Analysis\n\n{json.dumps(analysis, indent=2)}\n\n## Codebase\n\n{codebase_context}"
        if cached_scout_result:
            scout_summary = self._smart_truncate(cached_scout_result, self._config.context_limits.base_scout)
            decomposer_context += f"\n\n## Scout Insights\n\n{scout_summary}"
        if expert_context:
            decomposer_context += f"\n\n{expert_context}"

        decomposer_result = self.run_agent(
            "decomposer",
            message=f"Original request: {request}\n\nBreak this into independent sub-features for parallel planning.",
            context=decomposer_context
        )
        valid, error = self._validate_agent_response("Decomposer", decomposer_result)
        if not valid:
            return WorkflowResult(success=False, error=error)
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

        # Track failures for reporting
        failed_sub_features: list[tuple[str, str]] = []  # (name, error)

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

                from core.symbols import CHECK, CROSS
                for future in as_completed(futures):
                    sf = futures[future]
                    sf_name = sf.get('name', 'Unknown')
                    try:
                        plan = future.result()
                        sub_plans.append(plan)
                        self.console.print(f"  [green]{CHECK}[/green] {plan.name}")
                    except Exception as e:
                        error_msg = str(e)
                        failed_sub_features.append((sf_name, error_msg))
                        self.console.print(f"  [red]{CROSS}[/red] {sf_name}: {error_msg}")
        else:
            # Sequential planning (with cached scout)
            from core.symbols import CHECK, CROSS
            for sf in sub_features:
                sf_name = sf.get('name', 'Unknown')
                self.console.print(f"  Planning: {sf_name}...")
                try:
                    plan = self._plan_sub_feature(sf, codebase_context, cached_scout_result, num_features)
                    sub_plans.append(plan)
                    self.console.print(f"  [green]{CHECK}[/green] {plan.name}")
                except Exception as e:
                    error_msg = str(e)
                    failed_sub_features.append((sf_name, error_msg))
                    self.console.print(f"  [red]{CROSS}[/red] {sf_name}: {error_msg}")

        # Check if too many sub-features failed
        if failed_sub_features:
            failure_rate = len(failed_sub_features) / len(sub_features)
            if failure_rate > 0.5:
                # More than half failed - abort
                failed_names = [f[0] for f in failed_sub_features]
                return WorkflowResult(
                    success=False,
                    error=f"Too many sub-features failed ({len(failed_sub_features)}/{len(sub_features)}): {', '.join(failed_names)}",
                    data={"failed_sub_features": failed_sub_features}
                )
            elif not sub_plans:
                # All failed
                return WorkflowResult(
                    success=False,
                    error=f"All {len(sub_features)} sub-features failed to plan",
                    data={"failed_sub_features": failed_sub_features}
                )
            else:
                # Some failed but we have enough to continue
                self.console.print(f"\n  [yellow]Warning: {len(failed_sub_features)} sub-feature(s) failed, continuing with {len(sub_plans)}[/yellow]")

        steps_completed.append(f"sub_plans ({len(sub_plans)})")

        # Synthesize
        self.console.print("\n[bold]Phase 4:[/bold] Synthesizing master plan...")

        sub_plans_text = "\n\n---\n\n".join([
            f"## Sub-Feature: {sp.name}\n\n### Architecture\n{sp.architect_result}\n\n### Implementation\n{sp.planner_result}"
            for sp in sub_plans
        ])

        synthesizer_context = f"## Sub-Feature Plans\n\n{sub_plans_text}"
        if expert_context:
            synthesizer_context += f"\n\n{expert_context}"

        synthesizer_result = self.run_agent(
            "synthesizer",
            message=f"Original request: {request}\n\nCombine these sub-feature plans into a master plan.",
            context=synthesizer_context
        )
        valid, error = self._validate_agent_response("Synthesizer", synthesizer_result)
        if not valid:
            return WorkflowResult(success=False, error=error)
        steps_completed.append("synthesizer")

        # Validate
        self.console.print("\n[bold]Phase 5:[/bold] Validating master plan...")
        validator_result = self.run_agent(
            "validator",
            message=f"Validate this master implementation plan for: {request}",
            context=f"## Master Plan\n\n{synthesizer_result.content}"
        )
        valid, error = self._validate_agent_response("Validator", validator_result)
        if not valid:
            return WorkflowResult(success=False, error=error)

        # VALIDATION GATE: Check if master plan actually passed validation
        validation_data = self._parse_json_from_response(validator_result.content)
        validation_status = validation_data.get("status", "unknown")
        validation_score = validation_data.get("score", 0)

        if validation_status != "approved" or validation_score < 70:
            blocking_issues = validation_data.get("blocking_issues", [])
            issue_summary = "; ".join(
                issue.get("issue", "unknown")[:60]
                for issue in blocking_issues[:3]
            ) if blocking_issues else "Master plan did not meet quality threshold"

            from core.symbols import CROSS
            self.console.print(f"\n[red]{CROSS} Master plan validation failed[/red]")
            self.console.print(f"  Status: {validation_status}, Score: {validation_score}/100")

            return WorkflowResult(
                success=False,
                error=f"Master plan validation failed (score {validation_score}): {issue_summary}",
                data={"validation": validation_data}
            )

        steps_completed.append("validator")

        # Save master plan as folder with multiple files
        plan_files = self._compile_master_plan(
            request=request,
            analysis=analysis,
            decomposition=decomposition,
            sub_plans=sub_plans,
            synthesis=synthesizer_result.content,
            validation=validator_result.content,
            expert_insights=expert_insights
        )

        dirname = self._generate_plan_dirname(request, prefix="master-")
        output_path = self._save_plan_folder(dirname, plan_files)

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
        """
        Execute the smart planning workflow.

        Args:
            request: The user's feature request
        """
        codebase_context = self._get_codebase_context()

        # Phase 1: Analyze complexity
        self.console.print("[bold]Phase 1:[/bold] Analyzing complexity...")
        analyzer_result = self.run_agent(
            "analyzer",
            message=f"Analyze this feature request: {request}",
            context=codebase_context
        )

        # Parse analysis and create adaptive config
        if analyzer_result.success:
            analysis = self._parse_json_from_response(analyzer_result.content)
            adaptive = AdaptiveConfig.from_analysis(analysis)
        else:
            self.console.print("[yellow]Analyzer failed, using default config[/yellow]")
            adaptive = AdaptiveConfig.default_simple()
            analysis = {}

        # Display adaptive configuration
        self.console.print(f"  Complexity: [cyan]{adaptive.complexity}[/cyan]")
        self.console.print(f"  Output format: [cyan]{adaptive.output_format}[/cyan]")
        self.console.print(f"  Agent depth: [cyan]{adaptive.agent_depth}[/cyan]")
        self.console.print(f"  Decomposition needed: [cyan]{adaptive.needs_decomposition}[/cyan]")

        if adaptive.needs_decomposition and adaptive.complexity in ["complex", "massive"]:
            return self._run_complex_planning(request, codebase_context, analysis, adaptive)
        else:
            return self._run_simple_planning(request, codebase_context, adaptive)

    def _compile_single_plan(
        self,
        request: str,
        scout: str,
        architect: str,
        planner: str,
        validator: str,
        expert_insights: Optional[list[ExpertInsight]],
        adaptive: AdaptiveConfig
    ) -> dict[str, str]:
        """
        Compile plan as a single minimal file.

        The planner output is already in the new format (GOAL/CONTEXT/STEPS/VERIFY).
        We just need to add the header and clean it up.
        """
        # Extract GOAL from planner output
        goal_match = re.search(r'GOAL:\s*(.+?)(?=\n\n|\nCONTEXT:)', planner, re.DOTALL)
        goal = goal_match.group(1).strip() if goal_match else request[:100]

        # Extract CONTEXT bullets from planner (or fall back to scout summary)
        context_match = re.search(r'CONTEXT:\s*((?:- .+\n?)+)', planner)
        if context_match:
            context_section = context_match.group(1).strip()
        else:
            # Create context from scout output (first 5 meaningful lines)
            scout_lines = [l.strip() for l in scout.split('\n') if l.strip() and not l.startswith('#')]
            context_section = '\n'.join(f"- {l[:80]}" for l in scout_lines[:5])

        # Extract STEPS section from planner
        steps_match = re.search(r'STEPS:\s*((?:\d+\..+?(?=\n\d+\.|\nVERIFY:|\Z))+)', planner, re.DOTALL)
        if steps_match:
            steps_section = steps_match.group(1).strip()
        else:
            # Fallback: use planner content as-is (for backward compatibility)
            steps_section = planner

        # Extract VERIFY section from planner
        verify_match = re.search(r'VERIFY:\s*((?:- .+\n?)+)', planner)
        if verify_match:
            verify_section = verify_match.group(1).strip()
        else:
            # Create verify from validator output
            verify_section = "- Run tests to verify implementation"

        # Build the minimal plan
        content = f"""# Plan: {request[:100]}

Request: {request}
Complexity: {adaptive.complexity}

## Goal

{goal}

## Context

{context_section}

## Steps

{steps_section}

## Verify

{verify_section}
"""

        return {"plan.md": content}

    def _compile_master_plan(
        self,
        request: str,
        analysis: dict,
        decomposition: dict,
        sub_plans: list[SubFeaturePlan],
        synthesis: str,
        validation: str,
        expert_insights: Optional[list[ExpertInsight]] = None
    ) -> dict[str, str]:
        """
        Compile master plan as a SINGLE minimal file.

        The synthesis output should already be in GOAL/CONTEXT/STEPS/VERIFY format.
        We produce one plan.md file, not multiple files.
        """
        complexity = analysis.get("complexity", "complex")

        # Extract GOAL from synthesis output
        goal_match = re.search(r'GOAL:\s*(.+?)(?=\n\n|\nCONTEXT:)', synthesis, re.DOTALL)
        goal = goal_match.group(1).strip() if goal_match else request[:100]

        # Extract CONTEXT from synthesis
        context_match = re.search(r'CONTEXT:\s*((?:- .+\n?)+)', synthesis)
        if context_match:
            context_section = context_match.group(1).strip()
        else:
            # Build context from sub-features
            context_lines = [f"- {sp.name}: {sp.id}" for sp in sub_plans[:5]]
            context_section = '\n'.join(context_lines)

        # Extract STEPS from synthesis
        steps_match = re.search(r'STEPS:\s*((?:\d+\..+?(?=\n\d+\.|\nVERIFY:|\Z))+)', synthesis, re.DOTALL)
        if steps_match:
            steps_section = steps_match.group(1).strip()
        else:
            steps_section = synthesis

        # Extract VERIFY from synthesis
        verify_match = re.search(r'VERIFY:\s*((?:- .+\n?)+)', synthesis)
        if verify_match:
            verify_section = verify_match.group(1).strip()
        else:
            verify_section = "- Run full test suite\n- Verify all sub-features integrate correctly"

        content = f"""# Plan: {request[:100]}

Request: {request}
Complexity: {complexity}

## Goal

{goal}

## Context

{context_section}

## Steps

{steps_section}

## Verify

{verify_section}
"""
        return {"plan.md": content}

    def _slugify(self, text: str) -> str:
        """Convert text to kebab-case slug for filenames."""
        slug = re.sub(r'[^\w\s-]', '', text.lower())
        slug = re.sub(r'[-\s]+', '-', slug).strip('-')
        return slug[:30]  # Limit length


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
