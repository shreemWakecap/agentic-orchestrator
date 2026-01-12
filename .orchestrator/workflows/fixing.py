"""
Fixing Workflow: Automatically resolves issues found during code review.

Flow:
1. Load review report
2. Gather codebase context
3. Run fixer agent to generate fix instructions
4. Apply fixes using builder agent
5. Verify fixes were applied
6. Generate fix report

Features:
- Parses review reports to extract issues
- Prioritizes fixes by severity
- Uses builder agent to actually apply fixes
- Supports resume capability
- Dry-run mode for previewing fixes
"""
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from core import Agent, Workflow, WorkflowResult


@dataclass
class FixInstruction:
    """A single fix instruction from the fixer agent."""
    id: str
    issue_reference: str
    severity: str  # critical, high, medium, low
    category: str
    file_path: str
    fix_type: str  # modify, create, delete
    description: str
    instructions: str
    code_hint: str = ""
    validation: str = ""


@dataclass
class FixResult:
    """Result of applying a single fix."""
    fix_id: str
    success: bool
    action_taken: str
    files_affected: list[str] = field(default_factory=list)
    summary: str = ""
    error: Optional[str] = None


@dataclass
class FixState:
    """Track fixing progress for resume capability."""
    review_path: str
    started_at: str
    status: str  # pending, in_progress, completed, failed
    fixes_planned: list[dict] = field(default_factory=list)
    fixes_completed: list[str] = field(default_factory=list)
    fixes_failed: list[str] = field(default_factory=list)
    fix_results: dict[str, dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "review_path": self.review_path,
            "started_at": self.started_at,
            "status": self.status,
            "fixes_planned": self.fixes_planned,
            "fixes_completed": self.fixes_completed,
            "fixes_failed": self.fixes_failed,
            "fix_results": self.fix_results,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FixState":
        return cls(**data)

    def save(self, path: Path):
        """Save state to file."""
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> Optional["FixState"]:
        """Load state from file if it exists."""
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return cls.from_dict(data)
            except Exception:
                return None
        return None


# Severity ordering for prioritization
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


class FixingWorkflow(Workflow):
    """
    Workflow to automatically fix issues from review reports.

    Flow:
    1. Load review report and parse issues
    2. Gather codebase context
    3. Run fixer agent to generate fix instructions
    4. Apply fixes using builder agent (in severity order)
    5. Verify each fix
    6. Generate fix report

    Features:
    - Resume capability via state persistence
    - Dry-run mode (analyze but don't apply)
    - Severity-based prioritization
    - Min-severity filtering
    """

    def __init__(
        self,
        project_root: Path,
        output_dir: Optional[Path] = None,
        min_severity: str = "low",
        dry_run: bool = False,
    ):
        self.project_root = project_root
        self.min_severity = min_severity
        self.dry_run = dry_run
        self.specs_dir = project_root / ".orchestrator" / "specs"

        output_dir = output_dir or self.specs_dir / "fixes"
        output_dir.mkdir(parents=True, exist_ok=True)

        super().__init__(name="Fixing Workflow", output_dir=output_dir)

        # Load agents
        self._load_agents()

        # State tracking
        self.fix_state: Optional[FixState] = None

    def _load_agents(self):
        """Load fixer and builder agents."""
        agents = ["fixer", "builder"]
        for agent_name in agents:
            try:
                self.register_agent(Agent.load(agent_name, self.project_root))
            except FileNotFoundError:
                self.console.print(f"[yellow]Warning: Agent '{agent_name}' not found[/yellow]")

    def _get_state_file(self, review_path: Path) -> Path:
        """Get state file path for a review."""
        return self.output_dir / f".{review_path.stem}.fix.state.json"

    def _save_state(self, review_path: Path):
        """Save current fix state."""
        if self.fix_state:
            state_file = self._get_state_file(review_path)
            self.fix_state.save(state_file)

    def _load_state(self, review_path: Path) -> Optional[FixState]:
        """Load existing fix state if available."""
        state_file = self._get_state_file(review_path)
        return FixState.load(state_file)

    def _load_review_report(self, review_path: Path) -> dict:
        """Load and parse review report."""
        content = review_path.read_text(encoding="utf-8")

        return {
            "content": content,
            "path": str(review_path),
            "plan_reference": self._extract_plan_reference(content),
        }

    def _extract_plan_reference(self, content: str) -> Optional[str]:
        """Extract the original plan reference from review report."""
        # Look for patterns like "Review Report: plan-name" or "Plan: plan-name"
        patterns = [
            r"Review Report:\s*([^\n]+)",
            r"Plan:\s*([^\n]+)",
            r"review-([^-]+)-\d+",
        ]

        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(1).strip()

        return None

    def _get_codebase_context(self, max_chars: int = 6000) -> str:
        """Gather relevant codebase context for the fixer agent."""
        context_parts = []

        # Get Python files listing
        py_files = list(self.project_root.glob("**/*.py"))
        py_files = [f for f in py_files if not any(
            skip in f.parts for skip in [".git", ".venv", "venv", "__pycache__", ".pytest_cache"]
        )]

        if py_files:
            file_list = "\n".join([str(f.relative_to(self.project_root)) for f in py_files[:30]])
            context_parts.append(f"## Python Files\n```\n{file_list}\n```")

        # Get directory structure
        dirs = set()
        for f in py_files[:50]:
            rel = f.relative_to(self.project_root)
            if len(rel.parts) > 1:
                dirs.add(str(rel.parent))

        if dirs:
            context_parts.append(f"## Directories\n{', '.join(sorted(dirs)[:20])}")

        # Read key files (config, main entry points)
        key_patterns = ["**/main.py", "**/app.py", "**/cli.py", "pyproject.toml"]
        for pattern in key_patterns:
            files = list(self.project_root.glob(pattern))
            for f in files[:2]:
                if f.exists() and f.stat().st_size < 5000:
                    try:
                        content = f.read_text(encoding="utf-8")[:2000]
                        rel_path = f.relative_to(self.project_root)
                        context_parts.append(f"## {rel_path}\n```python\n{content}\n```")
                    except Exception:
                        pass

        result = "\n\n".join(context_parts)
        return result[:max_chars]

    def _parse_json_from_response(self, response: str) -> dict:
        """Extract JSON from agent response."""
        # Try to find JSON in code blocks
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try direct JSON parse
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try to find JSON object in response
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        return {}

    def _run_fixer_agent(self, review_data: dict, codebase_context: str) -> tuple[list[FixInstruction], list[dict]]:
        """Run fixer agent to generate fix instructions."""
        message = """Analyze this review report and generate fix instructions for each actionable issue.

Focus on:
1. Critical and high severity issues first
2. Issues with clear file locations
3. Specific, actionable fixes

Output valid JSON with fixes array and unfixable array."""

        context = f"""## Review Report
{review_data['content'][:8000]}

## Codebase Context
{codebase_context}"""

        result = self.run_agent("fixer", message, context=context)

        if not result.success:
            self.console.print(f"[red]Fixer agent failed: {result.error}[/red]")
            return [], []

        parsed = self._parse_json_from_response(result.content)

        # Parse fixes
        fixes = []
        for fix_data in parsed.get("fixes", []):
            try:
                fix = FixInstruction(
                    id=fix_data.get("id", f"fix_{len(fixes)+1}"),
                    issue_reference=fix_data.get("issue_reference", ""),
                    severity=fix_data.get("severity", "medium"),
                    category=fix_data.get("category", "quality"),
                    file_path=fix_data.get("file_path", ""),
                    fix_type=fix_data.get("fix_type", "modify"),
                    description=fix_data.get("description", ""),
                    instructions=fix_data.get("instructions", ""),
                    code_hint=fix_data.get("code_hint", ""),
                    validation=fix_data.get("validation", ""),
                )
                fixes.append(fix)
            except Exception as e:
                self.console.print(f"[yellow]Warning: Could not parse fix: {e}[/yellow]")

        unfixable = parsed.get("unfixable", [])

        return fixes, unfixable

    def _should_apply_fix(self, fix: FixInstruction) -> bool:
        """Check if fix should be applied based on severity filter."""
        fix_order = SEVERITY_ORDER.get(fix.severity, 3)
        min_order = SEVERITY_ORDER.get(self.min_severity, 3)
        return fix_order <= min_order

    def _apply_fix(self, fix: FixInstruction) -> FixResult:
        """Apply a single fix using builder agent."""
        if self.dry_run:
            return FixResult(
                fix_id=fix.id,
                success=True,
                action_taken="dry_run",
                summary=f"Would {fix.fix_type} {fix.file_path}: {fix.description}"
            )

        message = f"""Apply this fix to the codebase:

**File:** {fix.file_path}
**Action:** {fix.fix_type}
**Description:** {fix.description}

## Instructions
{fix.instructions}

## Code Hint
```
{fix.code_hint if fix.code_hint else 'No code hint provided'}
```

IMPORTANT: Actually {fix.fix_type} the file using Write/Edit tools. Do not just describe - execute the change."""

        context = f"""Fix ID: {fix.id}
Category: {fix.category}
Severity: {fix.severity}
Original Issue: {fix.issue_reference}"""

        result = self.run_agent("builder", message, context=context, show_progress=False)

        if not result.success:
            return FixResult(
                fix_id=fix.id,
                success=False,
                action_taken="failed",
                error=result.error
            )

        # Determine what was done
        files_affected = []
        action = fix.fix_type

        if result.files_created:
            files_affected.extend(result.files_created)
            action = "created"
        if result.files_modified:
            files_affected.extend(result.files_modified)
            action = "modified"

        if not files_affected:
            files_affected = [fix.file_path] if fix.file_path else []

        return FixResult(
            fix_id=fix.id,
            success=True,
            action_taken=action,
            files_affected=files_affected,
            summary=result.content[:200] if result.content else f"Applied fix to {fix.file_path}"
        )

    def _verify_fix(self, fix: FixInstruction, result: FixResult) -> bool:
        """Verify the fix was applied correctly."""
        if not result.success:
            return False

        # Check file exists for creates
        if fix.fix_type == "create" and fix.file_path:
            target = self.project_root / fix.file_path
            if not target.exists():
                self.console.print(f"  [yellow]Warning: Expected file not found: {fix.file_path}[/yellow]")
                return False

        # Check file was modified
        if fix.fix_type == "modify" and result.files_affected:
            # Files were reported as modified
            return True

        return True

    def _generate_fix_report(
        self,
        review_path: Path,
        fixes: list[FixInstruction],
        results: list[FixResult],
        unfixable: list[dict]
    ) -> str:
        """Generate comprehensive fix report."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        # Calculate stats
        total = len(fixes)
        applied = len(successful)
        failed_count = len(failed)
        skipped = total - applied - failed_count

        status = "SUCCESS" if failed_count == 0 and applied > 0 else (
            "PARTIAL" if applied > 0 else "FAILED"
        )

        report_lines = [
            f"# Fix Report: {review_path.stem}",
            f"",
            f"> Generated: {timestamp}",
            f"> Status: **{status}**",
            f"> Mode: {'Dry Run' if self.dry_run else 'Applied'}",
            f"",
            f"## Summary",
            f"",
            f"| Metric | Count |",
            f"|--------|-------|",
            f"| Total Issues | {total} |",
            f"| Fixes Applied | {applied} |",
            f"| Fixes Failed | {failed_count} |",
            f"| Skipped (severity) | {skipped} |",
            f"| Unfixable | {len(unfixable)} |",
            f"",
        ]

        # Applied fixes
        if successful:
            report_lines.append("## Applied Fixes")
            report_lines.append("")
            for r in successful:
                fix = next((f for f in fixes if f.id == r.fix_id), None)
                if fix:
                    report_lines.append(f"### {r.fix_id}: {fix.description[:60]}")
                    report_lines.append(f"")
                    report_lines.append(f"- **Severity:** {fix.severity}")
                    report_lines.append(f"- **File:** `{fix.file_path}`")
                    report_lines.append(f"- **Action:** {r.action_taken}")
                    if r.files_affected:
                        report_lines.append(f"- **Files:** {', '.join(r.files_affected)}")
                    report_lines.append(f"- **Summary:** {r.summary}")
                    report_lines.append("")

        # Failed fixes
        if failed:
            report_lines.append("## Failed Fixes")
            report_lines.append("")
            for r in failed:
                fix = next((f for f in fixes if f.id == r.fix_id), None)
                if fix:
                    report_lines.append(f"### {r.fix_id}: {fix.description[:60]}")
                    report_lines.append(f"")
                    report_lines.append(f"- **Severity:** {fix.severity}")
                    report_lines.append(f"- **File:** `{fix.file_path}`")
                    report_lines.append(f"- **Error:** {r.error}")
                    report_lines.append("")

        # Unfixable issues
        if unfixable:
            report_lines.append("## Unfixable Issues")
            report_lines.append("")
            report_lines.append("These issues require manual intervention:")
            report_lines.append("")
            for item in unfixable:
                report_lines.append(f"- **{item.get('issue', 'Unknown')}**")
                report_lines.append(f"  - Reason: {item.get('reason', 'N/A')}")
                if item.get('suggestion'):
                    report_lines.append(f"  - Suggestion: {item.get('suggestion')}")
            report_lines.append("")

        report_lines.append("---")
        report_lines.append("*Generated by SDLC Orchestrator Fixing Workflow*")

        return "\n".join(report_lines)

    def execute(self, review_path_str: str) -> WorkflowResult:
        """
        Execute the fixing workflow for a review report.

        Args:
            review_path_str: Path to the review report file
        """
        # Resolve review path
        review_path = Path(review_path_str)
        if not review_path.is_absolute():
            review_path = self.project_root / review_path_str

        # Try to find in reviews folder
        if not review_path.exists():
            reviews_path = self.specs_dir / "reviews" / review_path.name
            if reviews_path.exists():
                review_path = reviews_path

        if not review_path.exists():
            return WorkflowResult(success=False, error=f"Review report not found: {review_path}")

        self.console.print(f"[dim]Fixing issues from: {review_path}[/dim]")

        if self.dry_run:
            self.console.print("[yellow]DRY RUN MODE - No changes will be applied[/yellow]")

        steps_completed = []

        # Check for existing state (resume capability)
        existing_state = self._load_state(review_path)
        if existing_state and existing_state.fixes_completed:
            self.console.print(f"[yellow]Resuming fix ({len(existing_state.fixes_completed)} already done)[/yellow]")
            self.fix_state = existing_state
            self.fix_state.status = "in_progress"
        else:
            self.fix_state = FixState(
                review_path=str(review_path),
                started_at=datetime.now().isoformat(),
                status="in_progress"
            )

        # Phase 1: Load review report
        self.console.print("\n[bold]Phase 1:[/bold] Loading review report...")
        review_data = self._load_review_report(review_path)
        self.console.print(f"  Plan reference: [cyan]{review_data['plan_reference'] or 'Unknown'}[/cyan]")
        steps_completed.append("review_loaded")

        # Phase 2: Gather codebase context
        self.console.print("\n[bold]Phase 2:[/bold] Gathering codebase context...")
        codebase_context = self._get_codebase_context()
        steps_completed.append("context_gathered")

        # Phase 3: Run fixer agent
        self.console.print("\n[bold]Phase 3:[/bold] Analyzing issues...")
        fixes, unfixable = self._run_fixer_agent(review_data, codebase_context)

        if not fixes:
            self.console.print("  [yellow]No fixable issues found[/yellow]")
            return WorkflowResult(
                success=True,
                output_file=None,
                steps_completed=steps_completed,
                data={"fixes_applied": 0, "unfixable": len(unfixable)}
            )

        # Sort by severity
        fixes.sort(key=lambda f: SEVERITY_ORDER.get(f.severity, 3))

        self.console.print(f"  Found [cyan]{len(fixes)}[/cyan] fixable issues")
        self.console.print(f"  Unfixable: [yellow]{len(unfixable)}[/yellow]")

        # Show breakdown by severity
        by_severity = {}
        for f in fixes:
            by_severity[f.severity] = by_severity.get(f.severity, 0) + 1
        for sev, count in sorted(by_severity.items(), key=lambda x: SEVERITY_ORDER.get(x[0], 3)):
            self.console.print(f"    {sev}: {count}")

        self.fix_state.fixes_planned = [
            {"id": f.id, "severity": f.severity, "description": f.description}
            for f in fixes
        ]
        self._save_state(review_path)
        steps_completed.append("issues_analyzed")

        # Phase 4: Apply fixes
        self.console.print(f"\n[bold]Phase 4:[/bold] Applying {len(fixes)} fixes...")
        fix_results = []

        for fix in fixes:
            # Check cancellation
            self._check_cancellation()

            # Skip already completed
            if fix.id in self.fix_state.fixes_completed:
                self.console.print(f"  [dim]↷ {fix.id} (already done)[/dim]")
                continue

            # Check severity filter
            if not self._should_apply_fix(fix):
                self.console.print(f"  [dim]↷ {fix.id} (below min-severity)[/dim]")
                continue

            # Apply the fix
            sev_color = {
                "critical": "red",
                "high": "yellow",
                "medium": "cyan",
                "low": "dim"
            }.get(fix.severity, "white")

            self.console.print(f"  [{sev_color}]{fix.severity}[/{sev_color}] {fix.description[:50]}...")

            result = self._apply_fix(fix)
            fix_results.append(result)

            # Update state
            self.fix_state.fix_results[fix.id] = {
                "success": result.success,
                "action": result.action_taken,
                "files": result.files_affected,
                "summary": result.summary,
                "error": result.error
            }

            from core.symbols import CHECK, CROSS, QUESTION
            if result.success:
                self.fix_state.fixes_completed.append(fix.id)
                verified = self._verify_fix(fix, result)
                status = f"[green]{CHECK}[/green]" if verified else f"[yellow]{QUESTION}[/yellow]"
                self.console.print(f"    {status} {result.summary[:40]}")
            else:
                self.fix_state.fixes_failed.append(fix.id)
                self.console.print(f"    [red]{CROSS}[/red] {result.error}")

            self._save_state(review_path)

        steps_completed.append("fixes_applied")

        # Phase 5: Generate report
        self.console.print("\n[bold]Phase 5:[/bold] Generating fix report...")
        report = self._generate_fix_report(review_path, fixes, fix_results, unfixable)

        report_filename = f"fix-{review_path.stem}-{datetime.now().strftime('%Y%m%d-%H%M')}.md"
        output_path = self.save_output(report_filename, report)
        steps_completed.append("report_generated")

        # Update state
        successful = [r for r in fix_results if r.success]
        failed = [r for r in fix_results if not r.success]

        self.fix_state.status = "completed" if not failed else "partial"
        self._save_state(review_path)

        return WorkflowResult(
            success=len(failed) == 0,
            output_file=output_path,
            steps_completed=steps_completed,
            data={
                "fixes_applied": len(successful),
                "fixes_failed": len(failed),
                "unfixable": len(unfixable),
                "dry_run": self.dry_run,
                "files_modified": list(set(
                    f for r in successful for f in r.files_affected
                ))
            }
        )


def main():
    """CLI entry point."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m orchestrator.workflows.fixing <review-file> [options]")
        print("Example: python -m orchestrator.workflows.fixing .orchestrator/specs/reviews/review-auth-20240115.md")
        print("\nOptions:")
        print("  --dry-run         Show fixes without applying")
        print("  --min-severity    Minimum severity to fix (critical|high|medium|low)")
        sys.exit(1)

    review_path = sys.argv[1]
    project_root = Path.cwd()

    # Parse options
    dry_run = "--dry-run" in sys.argv
    min_severity = "low"
    for i, arg in enumerate(sys.argv):
        if arg == "--min-severity" and i + 1 < len(sys.argv):
            min_severity = sys.argv[i + 1]

    workflow = FixingWorkflow(
        project_root=project_root,
        dry_run=dry_run,
        min_severity=min_severity
    )
    result = workflow.run(review_path)

    if result.success:
        print(f"\nFixes applied: {result.data.get('fixes_applied', 0)}")
        print(f"Report: {result.output_file}")

    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
