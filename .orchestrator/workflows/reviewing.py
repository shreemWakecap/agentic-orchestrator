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
from typing import Optional

from core import Agent, Workflow, WorkflowResult, get_agent_config
from core.docs_loader import DocsLoader, DocsContext
from core.expert_loader import ExpertLoader


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


# Python file extensions
PYTHON_EXTENSIONS = [".py"]

# Directories to skip when reading code
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".idea", ".vscode"}


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
        max_parallel: Optional[int] = None,
        refresh_docs: bool = False,
    ):
        self.project_root = project_root
        self._config = get_agent_config(project_root)
        self.max_parallel = max_parallel or self._config.parallel.max_expert_workers
        self.refresh_docs = refresh_docs

        output_dir = output_dir or project_root / ".orchestrator" / "specs" / "reviews"
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

    def _load_plan_content(self, plan_path: Path) -> str:
        """
        Load plan content from either a single file or a folder-based plan.

        For folder-based plans (e.g., 001_feature-name/), reads all .md files
        in sorted order and concatenates them.

        For single-file plans, returns the file content directly.
        """
        if plan_path.is_dir():
            md_files = sorted(plan_path.glob("*.md"))
            if not md_files:
                return ""
            contents = []
            for md_file in md_files:
                file_content = md_file.read_text(encoding="utf-8")
                contents.append(f"<!-- File: {md_file.name} -->\n{file_content}")
            return "\n\n---\n\n".join(contents)
        elif plan_path.exists():
            return plan_path.read_text(encoding="utf-8")
        return ""

    def _load_docs(self) -> DocsContext:
        """Load AI documentation with freshness check."""
        self.console.print("[bold]Loading AI Documentation...[/bold]")

        context = self.docs_loader.load_docs(refresh_stale=self.refresh_docs)

        from core.symbols import WARNING
        if context.stale_docs:
            self.console.print(f"  [yellow]{WARNING} {len(context.stale_docs)} stale docs (older than 2 days)[/yellow]")
            if not self.refresh_docs:
                self.console.print("  [dim]Use --refresh-docs to update[/dim]")

        if context.missing_docs:
            self.console.print(f"  [yellow]{WARNING} {len(context.missing_docs)} missing docs[/yellow]")

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
                languages=[lang.get("name", lang) if isinstance(lang, dict) else lang for lang in data.get("languages", [])],
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

    def _should_skip_path(self, path: Path) -> bool:
        """Check if a path should be skipped (node_modules, .git, etc.)."""
        return any(skip_dir in path.parts for skip_dir in SKIP_DIRS)

    def _get_python_files(self, max_files: int = 15) -> list[Path]:
        """
        Get Python files, prioritizing key modules.

        Args:
            max_files: Maximum number of files to return

        Returns:
            List of .py file paths, prioritized
        """
        all_files: list[tuple[int, Path]] = []  # (priority, path)

        for file_path in self.project_root.glob("**/*.py"):
            if self._should_skip_path(file_path):
                continue
            if not file_path.is_file():
                continue

            # Calculate priority (lower = higher priority)
            priority = 100
            rel_path = str(file_path.relative_to(self.project_root)).lower()

            # Boost key files
            if any(key in rel_path for key in ["main", "app", "__init__", "cli"]):
                priority = 10
            elif any(key in rel_path for key in ["config", "settings"]):
                priority = 20
            elif any(key in rel_path for key in ["core", "api", "model"]):
                priority = 30
            elif any(key in rel_path for key in ["workflow", "service", "util"]):
                priority = 40
            elif "test" in rel_path:
                priority = 80  # Tests lower priority for review

            all_files.append((priority, file_path))

        all_files.sort(key=lambda x: x[0])
        return [f[1] for f in all_files[:max_files]]

    def _read_code_samples(
        self,
        tech: str,
        stack_info: TechStackInfo,
        max_chars: int = 12000
    ) -> str:
        """
        Read actual Python code samples for expert review.

        Args:
            tech: Technology (currently only python)
            stack_info: Stack info with file mappings
            max_chars: Maximum total characters to read

        Returns:
            Formatted code samples with file paths
        """
        # Get files from stack detection or discover them
        file_patterns = stack_info.file_mapping.get("python", [])
        if file_patterns:
            files = []
            for pattern in file_patterns[:20]:
                path = self.project_root / pattern
                if path.exists() and path.is_file():
                    files.append(path)
        else:
            files = self._get_python_files()

        if not files:
            return "No code files found for this technology."

        # Read files up to max_chars
        code_sections = []
        total_chars = 0
        files_read = 0
        max_per_file = max_chars // min(len(files), 5)  # Distribute budget

        for file_path in files:
            if total_chars >= max_chars:
                break

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                rel_path = file_path.relative_to(self.project_root)

                # Truncate large files intelligently
                if len(content) > max_per_file:
                    # For large files, take beginning and look for key sections
                    content = self._smart_truncate_code(content, max_per_file)

                section = f"### {rel_path}\n```{file_path.suffix[1:]}\n{content}\n```"

                if total_chars + len(section) <= max_chars:
                    code_sections.append(section)
                    total_chars += len(section)
                    files_read += 1
                elif files_read == 0:
                    # At least include one file, even if truncated
                    remaining = max_chars - total_chars - 100
                    truncated_content = content[:remaining]
                    section = f"### {rel_path}\n```{file_path.suffix[1:]}\n{truncated_content}\n[...truncated...]\n```"
                    code_sections.append(section)
                    files_read += 1
                    break

            except Exception as e:
                self.console.print(f"  [dim]Could not read {file_path}: {e}[/dim]")
                continue

        if not code_sections:
            return "Could not read any code files."

        header = f"## Code Samples ({files_read} files)\n\n"
        return header + "\n\n".join(code_sections)

    def _smart_truncate_code(self, content: str, max_chars: int) -> str:
        """
        Truncate Python code preserving imports and definitions.
        """
        if len(content) <= max_chars:
            return content

        lines = content.split('\n')

        # Keep imports at the top
        beginning_budget = max_chars // 3
        beginning = []
        chars = 0
        for line in lines:
            if chars + len(line) > beginning_budget:
                break
            beginning.append(line)
            chars += len(line) + 1

        # Find class/function definitions
        important_lines = []
        for i, line in enumerate(lines[len(beginning):], len(beginning)):
            stripped = line.strip()
            if stripped.startswith(("class ", "def ", "async def ", "@")):
                context_end = min(i + 5, len(lines))
                important_lines.extend(lines[i:context_end])
                important_lines.append("    # ...")

        result_lines = beginning
        remaining = max_chars - chars - 50
        if remaining > 0 and important_lines:
            important_text = '\n'.join(important_lines)[:remaining]
            result_lines.append("\n# ... (truncated) ...\n")
            result_lines.append(important_text)

        return '\n'.join(result_lines)

    def _check_compliance(self, plan_path: Path) -> ReviewResult:
        """Check if implementation matches the plan."""
        self.console.print("\n[bold]Phase 2:[/bold] Checking plan compliance...")

        # Load plan content (supports both file and folder-based plans)
        plan_content = self._load_plan_content(plan_path)

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
        docs_context: DocsContext
    ) -> ReviewResult:
        """
        Run a single expert review with actual code and tech-specific docs.

        Key improvements over original:
        1. Reads actual code files instead of just listing file names
        2. Filters documentation to tech-relevant content
        3. Provides much larger context budget (20k chars vs 2k)
        """
        # Read actual code samples for this technology
        code_samples = self._read_code_samples(tech, stack_info, max_chars=12000)

        # Get tech-specific documentation (not generic truncated docs)
        tech_docs = docs_context.get_docs_for_tech(tech, max_chars=6000)

        # Build comprehensive context for the expert
        context = f"""## Tech Stack Overview
Languages: {', '.join(stack_info.languages)}
Frameworks: {', '.join(stack_info.frameworks)}
Tools: {', '.join(stack_info.tools)}

{code_samples}

## Relevant Documentation
{tech_docs if tech_docs else 'No specific documentation available for this technology.'}"""

        result = expert.run(
            message=f"""Review the Python code for best practices and issues.

Focus on:
1. Python best practices (PEP8, type hints, idioms)
2. Potential bugs or error-prone patterns
3. Security concerns
4. Performance considerations
5. Maintainability

Provide specific feedback with file locations.""",
            context=context
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
        docs_context: DocsContext
    ) -> list[ReviewResult]:
        """
        Run expert reviews in parallel with real code and tech-specific docs.

        Each expert receives:
        - Actual code samples (not just file names)
        - Documentation filtered to their technology
        - A comprehensive prompt for thorough review
        """
        self.console.print("\n[bold]Phase 3:[/bold] Running expert reviews...")

        # Get needed experts
        needed_techs = stack_info.languages + stack_info.frameworks
        experts = self.expert_loader.get_experts_for_stack(needed_techs)

        if not experts:
            self.console.print("  [yellow]No matching experts found[/yellow]")
            return []

        self.console.print(f"  Running {len(experts)} expert reviews with code analysis...")
        results = []

        # Run in parallel
        with ThreadPoolExecutor(max_workers=self.max_parallel) as executor:
            futures = {
                executor.submit(
                    self._run_expert_review,
                    expert,
                    expert.name,
                    stack_info,
                    docs_context  # Now passing DocsContext object, not string
                ): expert
                for expert in experts
            }

            from core.symbols import CHECK, WARNING, CROSS
            for future in as_completed(futures):
                expert = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                    status = f"[green]{CHECK}[/green]" if result.score >= 70 else f"[yellow]{WARNING}[/yellow]"
                    self.console.print(f"  {status} {expert.name}: {result.score}/100")
                except Exception as e:
                    self.console.print(f"  [red]{CROSS}[/red] {expert.name}: {e}")

        return results

    def _check_standards(self, stack_info: TechStackInfo) -> ReviewResult:
        """Check universal standards with actual Python code samples."""
        self.console.print("\n[bold]Phase 4:[/bold] Checking universal standards...")

        # Read Python code samples
        code_samples = self._read_code_samples("python", stack_info, max_chars=8000)

        result = self.run_agent(
            "standards_checker",
            message="""Check this Python codebase against software engineering standards.

Evaluate:
1. Code organization and structure
2. Error handling patterns
3. Security practices
4. Documentation and type hints
5. Testing patterns
6. Dependency management""",
            context=f"""## Tech Stack
Languages: {', '.join(stack_info.languages)}
Frameworks: {', '.join(stack_info.frameworks)}

## Python Code Samples
{code_samples[:10000]}"""
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
            completed_path = self.project_root / ".orchestrator" / "specs" / "completed" / plan_path.name
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

        # Phase 3: Expert reviews (now with actual code reading!)
        expert_results = self._run_expert_reviews(stack_info, self.docs_context)
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
        print("Example: python -m orchestrator.workflows.reviewing .orchestrator/specs/completed/user-auth.md")
        sys.exit(1)

    plan_path = sys.argv[1]
    project_root = Path.cwd()

    refresh = "--refresh-docs" in sys.argv

    workflow = ReviewingWorkflow(project_root=project_root, refresh_docs=refresh)
    result = workflow.run(plan_path)

    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
