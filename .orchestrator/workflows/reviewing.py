"""
Smart Review Workflow: Reviews completed builds for compliance and quality.

Flow:
1. Load plan and build state
2. Detect tech stack
3. Check plan compliance
4. Run tech-specific expert reviews (parallel)
5. Check universal standards
6. Generate comprehensive report

Features:
- Uses tech-specific experts for targeted reviews
- Loads AI docs for context
- Parallel expert reviews
- Generates actionable reports
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from ..core import Agent, Workflow, WorkflowResult
from ..core.docs_loader import DocsLoader, DocsContext
from ..core.expert_loader import ExpertLoader


@dataclass
class ReviewResult:
    """Result from a single review component."""
    reviewer: str
    category: str
    score: int
    issues: list[dict] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    raw_content: str = ""


@dataclass
class TechStackInfo:
    """Information about detected tech stack."""
    languages: list[str]
    frameworks: list[str]
    tools: list[str]
    recommended_experts: list[str]
    file_mapping: dict[str, list[str]] = field(default_factory=dict)


class ReviewingWorkflow(Workflow):
    """
    Smart review workflow with tech-specific experts.

    Flow:
    1. Compliance Check - Did we build what the plan specified?
    2. Stack Detection - What technologies are used?
    3. Expert Reviews - Tech-specific code reviews (parallel)
    4. Standards Check - Universal best practices
    5. Report Generation - Compile actionable report

    Features:
    - Loads AI docs for context (checks freshness)
    - Uses tech-specific experts
    - Parallel expert reviews
    - Generates comprehensive markdown report
    """

    def __init__(
        self,
        project_root: Path,
        output_dir: Optional[Path] = None,
        max_parallel: int = 3,
        refresh_docs: bool = False,
    ):
        self.project_root = project_root
        self.max_parallel = max_parallel
        self.refresh_docs = refresh_docs

        output_dir = output_dir or project_root / ".specs" / "reviews"
        output_dir.mkdir(parents=True, exist_ok=True)

        super().__init__(name="Smart Review Workflow", output_dir=output_dir)

        # Initialize loaders
        self.docs_loader = DocsLoader(project_root)
        self.expert_loader = ExpertLoader(project_root)

        # Load docs context
        self.docs_context: Optional[DocsContext] = None

        # Load base agents
        self._load_agents()

    def _load_agents(self):
        """Load all agents needed for reviewing."""
        agents = [
            "stack_detector",
            "compliance_checker",
            "standards_checker",
            "report_generator",
        ]
        for agent_name in agents:
            try:
                self.register_agent(Agent.load(agent_name, self.project_root))
            except FileNotFoundError:
                self.console.print(f"[yellow]Warning: Agent '{agent_name}' not found[/yellow]")

    def _load_docs(self) -> DocsContext:
        """Load AI documentation with freshness check."""
        self.console.print("[bold]Loading AI Documentation...[/bold]")

        context = self.docs_loader.load_docs(refresh_stale=self.refresh_docs)

        if context.stale_docs:
            self.console.print(f"  [yellow]⚠ {len(context.stale_docs)} stale docs (older than 2 days)[/yellow]")
            if not self.refresh_docs:
                self.console.print("  [dim]Use --refresh-docs to update[/dim]")

        if context.missing_docs:
            self.console.print(f"  [yellow]⚠ {len(context.missing_docs)} missing docs[/yellow]")

        return context

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

    def _detect_stack(self) -> TechStackInfo:
        """Detect tech stack using stack detector agent."""
        self.console.print("\n[bold]Phase 1:[/bold] Detecting tech stack...")

        # Get codebase context
        context_parts = []

        # Check for package files
        for config_file in ["package.json", "pyproject.toml", "go.mod", "Cargo.toml"]:
            config_path = self.project_root / config_file
            if config_path.exists():
                try:
                    content = config_path.read_text(encoding="utf-8")[:2000]
                    context_parts.append(f"## {config_file}\n```\n{content}\n```")
                except Exception:
                    pass

        # Get file listing
        try:
            files = list(self.project_root.rglob("*"))
            extensions = {}
            for f in files:
                if f.is_file() and not any(p.startswith('.') for p in f.parts):
                    ext = f.suffix.lower()
                    extensions[ext] = extensions.get(ext, 0) + 1

            top_extensions = sorted(extensions.items(), key=lambda x: -x[1])[:10]
            context_parts.append(f"## File Extensions\n{top_extensions}")
        except Exception:
            pass

        context = "\n\n".join(context_parts)

        result = self.run_agent(
            "stack_detector",
            message="Detect all technologies used in this project.",
            context=context
        )

        if result.success:
            data = self._parse_json_from_response(result.content)
            return TechStackInfo(
                languages=[l.get("name", l) if isinstance(l, dict) else l for l in data.get("languages", [])],
                frameworks=[f.get("name", f) if isinstance(f, dict) else f for f in data.get("frameworks", [])],
                tools=[t.get("name", t) if isinstance(t, dict) else t for t in data.get("tools", [])],
                recommended_experts=data.get("recommended_experts", []),
                file_mapping=data.get("file_mapping", {})
            )

        # Fallback to basic detection
        return TechStackInfo(
            languages=self.expert_loader.get_recommended_experts(self.project_root),
            frameworks=[],
            tools=[],
            recommended_experts=[]
        )

    def _check_compliance(self, plan_path: Path) -> ReviewResult:
        """Check if implementation matches the plan."""
        self.console.print("\n[bold]Phase 2:[/bold] Checking plan compliance...")

        # Load plan content
        plan_content = ""
        if plan_path.exists():
            plan_content = plan_path.read_text(encoding="utf-8")

        # Load build state if exists
        state_file = plan_path.parent / f".{plan_path.stem}.state.json"
        build_state = {}
        if state_file.exists():
            try:
                build_state = json.loads(state_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        result = self.run_agent(
            "compliance_checker",
            message="Check if the implementation matches the plan.",
            context=f"""## Original Plan
{plan_content[:5000]}

## Build State
{json.dumps(build_state, indent=2)[:2000]}"""
        )

        if result.success:
            data = self._parse_json_from_response(result.content)
            return ReviewResult(
                reviewer="compliance_checker",
                category="compliance",
                score=data.get("compliance_score", 0),
                issues=data.get("missing_items", []) + data.get("deviations", []),
                recommendations=[],
                raw_content=result.content
            )

        return ReviewResult(
            reviewer="compliance_checker",
            category="compliance",
            score=0,
            issues=[{"error": result.error}],
            raw_content=""
        )

    def _run_expert_review(
        self,
        expert: Agent,
        tech: str,
        stack_info: TechStackInfo,
        docs_context: str
    ) -> ReviewResult:
        """Run a single expert review."""
        # Get relevant files for this tech
        file_patterns = stack_info.file_mapping.get(tech.lower(), [])

        result = expert.run(
            message=f"Review the {tech} code in this project for best practices and issues.",
            context=f"""## Tech Stack
Languages: {', '.join(stack_info.languages)}
Frameworks: {', '.join(stack_info.frameworks)}

## Relevant Files
{', '.join(file_patterns[:20]) if file_patterns else 'All files with relevant extensions'}

## Documentation
{docs_context[:2000]}"""
        )

        if result.success:
            data = self._parse_json_from_response(result.content)
            return ReviewResult(
                reviewer=expert.name,
                category="tech_expert",
                score=data.get("overall_quality", 0) if isinstance(data.get("overall_quality"), int)
                       else {"good": 85, "needs_work": 60, "poor": 30}.get(data.get("overall_quality", ""), 70),
                issues=data.get("issues", []),
                recommendations=data.get("recommendations", []),
                raw_content=result.content
            )

        return ReviewResult(
            reviewer=expert.name,
            category="tech_expert",
            score=0,
            issues=[{"error": result.error}]
        )

    def _run_expert_reviews(
        self,
        stack_info: TechStackInfo,
        docs_context: str
    ) -> list[ReviewResult]:
        """Run expert reviews in parallel."""
        self.console.print("\n[bold]Phase 3:[/bold] Running expert reviews...")

        # Get needed experts
        needed_techs = stack_info.languages + stack_info.frameworks
        experts = self.expert_loader.get_experts_for_stack(needed_techs)

        if not experts:
            self.console.print("  [yellow]No matching experts found[/yellow]")
            return []

        self.console.print(f"  Running {len(experts)} expert reviews...")
        results = []

        # Run in parallel
        with ThreadPoolExecutor(max_workers=self.max_parallel) as executor:
            futures = {
                executor.submit(
                    self._run_expert_review,
                    expert,
                    expert.name,
                    stack_info,
                    docs_context
                ): expert
                for expert in experts
            }

            for future in as_completed(futures):
                expert = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                    status = "[green]✓[/green]" if result.score >= 70 else "[yellow]⚠[/yellow]"
                    self.console.print(f"  {status} {expert.name}: {result.score}/100")
                except Exception as e:
                    self.console.print(f"  [red]✗[/red] {expert.name}: {e}")

        return results

    def _check_standards(self, stack_info: TechStackInfo) -> ReviewResult:
        """Check universal standards."""
        self.console.print("\n[bold]Phase 4:[/bold] Checking universal standards...")

        result = self.run_agent(
            "standards_checker",
            message="Check this codebase against universal software engineering standards.",
            context=f"""## Tech Stack
Languages: {', '.join(stack_info.languages)}
Frameworks: {', '.join(stack_info.frameworks)}
Tools: {', '.join(stack_info.tools)}"""
        )

        if result.success:
            data = self._parse_json_from_response(result.content)
            return ReviewResult(
                reviewer="standards_checker",
                category="standards",
                score=data.get("overall_score", 0),
                issues=data.get("critical_issues", []),
                recommendations=data.get("recommendations", []),
                raw_content=result.content
            )

        return ReviewResult(
            reviewer="standards_checker",
            category="standards",
            score=0,
            issues=[{"error": result.error}]
        )

    def _generate_report(
        self,
        plan_path: Path,
        compliance_result: ReviewResult,
        expert_results: list[ReviewResult],
        standards_result: ReviewResult
    ) -> str:
        """Generate comprehensive review report."""
        self.console.print("\n[bold]Phase 5:[/bold] Generating report...")

        # Compile all results
        all_results = {
            "compliance": {
                "score": compliance_result.score,
                "issues": compliance_result.issues
            },
            "expert_reviews": [
                {
                    "expert": r.reviewer,
                    "score": r.score,
                    "issues": r.issues,
                    "recommendations": r.recommendations
                }
                for r in expert_results
            ],
            "standards": {
                "score": standards_result.score,
                "issues": standards_result.issues,
                "recommendations": standards_result.recommendations
            }
        }

        result = self.run_agent(
            "report_generator",
            message=f"Generate a comprehensive review report for: {plan_path.stem}",
            context=json.dumps(all_results, indent=2)[:8000]
        )

        if result.success:
            return result.content

        # Fallback: generate basic report
        return self._generate_basic_report(plan_path, compliance_result, expert_results, standards_result)

    def _generate_basic_report(
        self,
        plan_path: Path,
        compliance: ReviewResult,
        experts: list[ReviewResult],
        standards: ReviewResult
    ) -> str:
        """Generate basic report as fallback."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Calculate overall score
        scores = [compliance.score, standards.score] + [e.score for e in experts]
        overall = sum(scores) / len(scores) if scores else 0

        status = "PASS" if overall >= 80 else ("NEEDS_WORK" if overall >= 60 else "FAIL")

        return f"""# Review Report: {plan_path.stem}

> Generated: {timestamp}
> Status: **{status}**

## Executive Summary

| Metric | Score |
|--------|-------|
| Overall | {overall:.0f}/100 |
| Compliance | {compliance.score}/100 |
| Standards | {standards.score}/100 |
| Expert Avg | {sum(e.score for e in experts) / len(experts) if experts else 0:.0f}/100 |

## Compliance Check

Score: {compliance.score}/100

Issues: {len(compliance.issues)}

## Expert Reviews

{chr(10).join(f"- **{e.reviewer}**: {e.score}/100 ({len(e.issues)} issues)" for e in experts)}

## Standards Check

Score: {standards.score}/100

## Recommendations

{chr(10).join(f"- {r}" for r in standards.recommendations[:10])}

---
*Generated by SDLC Orchestrator Review Workflow*
"""

    def execute(self, plan_path_str: str) -> WorkflowResult:
        """
        Execute the review workflow for a completed plan.

        Args:
            plan_path_str: Path to the completed plan file
        """
        # Resolve plan path
        plan_path = Path(plan_path_str)
        if not plan_path.is_absolute():
            plan_path = self.project_root / plan_path_str

        # Try to find in completed folder
        if not plan_path.exists():
            completed_path = self.project_root / ".specs" / "completed" / plan_path.name
            if completed_path.exists():
                plan_path = completed_path

        if not plan_path.exists():
            return WorkflowResult(success=False, error=f"Plan not found: {plan_path}")

        self.console.print(f"[dim]Reviewing: {plan_path}[/dim]")

        steps_completed = []

        # Load AI docs
        self.docs_context = self._load_docs()
        docs_context_str = self.docs_context.get_context_string()
        steps_completed.append("docs_loaded")

        # Phase 1: Detect stack
        stack_info = self._detect_stack()
        self.console.print(f"  Languages: [cyan]{', '.join(stack_info.languages)}[/cyan]")
        self.console.print(f"  Frameworks: [cyan]{', '.join(stack_info.frameworks)}[/cyan]")
        steps_completed.append("stack_detected")

        # Phase 2: Check compliance
        compliance_result = self._check_compliance(plan_path)
        self.console.print(f"  Compliance: [cyan]{compliance_result.score}%[/cyan]")
        steps_completed.append("compliance_checked")

        # Phase 3: Expert reviews
        expert_results = self._run_expert_reviews(stack_info, docs_context_str)
        steps_completed.append("expert_reviews")

        # Phase 4: Standards check
        standards_result = self._check_standards(stack_info)
        self.console.print(f"  Standards: [cyan]{standards_result.score}/100[/cyan]")
        steps_completed.append("standards_checked")

        # Phase 5: Generate report
        report = self._generate_report(plan_path, compliance_result, expert_results, standards_result)
        steps_completed.append("report_generated")

        # Save report
        report_filename = f"review-{plan_path.stem}-{datetime.now().strftime('%Y%m%d-%H%M')}.md"
        output_path = self.save_output(report_filename, report)

        # Calculate overall score
        scores = [compliance_result.score, standards_result.score] + [e.score for e in expert_results]
        overall_score = sum(scores) / len(scores) if scores else 0

        return WorkflowResult(
            success=True,
            output_file=output_path,
            steps_completed=steps_completed,
            data={
                "overall_score": overall_score,
                "compliance_score": compliance_result.score,
                "standards_score": standards_result.score,
                "expert_scores": {e.reviewer: e.score for e in expert_results},
                "stack": {
                    "languages": stack_info.languages,
                    "frameworks": stack_info.frameworks
                },
                "docs_status": {
                    "loaded": len(self.docs_context.docs),
                    "stale": len(self.docs_context.stale_docs)
                }
            }
        )


def main():
    """CLI entry point."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m orchestrator.workflows.reviewing <plan-file>")
        print("Example: python -m orchestrator.workflows.reviewing .specs/completed/user-auth.md")
        sys.exit(1)

    plan_path = sys.argv[1]
    project_root = Path.cwd()

    refresh = "--refresh-docs" in sys.argv

    workflow = ReviewingWorkflow(project_root=project_root, refresh_docs=refresh)
    result = workflow.run(plan_path)

    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
