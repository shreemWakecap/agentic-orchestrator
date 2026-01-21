"""
Unified Scout Workflow.

A simplified, always-useful knowledge engine that:
- Auto-detects what to do (full vs incremental scan)
- Uses git diff or file timestamps to detect changes
- Scans only what's new/modified since last scan
- Aggregates results into existing knowledge (don't replace)

Flow:
    scout() -> auto-detects what to do:
      - First run: Full analysis
      - Subsequent: Incremental (only changed files)
      - Depth adapts: Quick for unchanged, deep for new/changed
"""
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from core import Agent, Workflow, WorkflowResult, get_agent_config
from core.knowledge_store import (
    KnowledgeStore,
    CodebaseKnowledge,
    TechInfo,
    ModuleInfo,
    DomainInfo,
    CodingRule,
    ProjectInfo,
    TechnologiesInfo,
    ArchitectureInfo,
    PatternInfo,
)
from db import get_knowledge_repository


class UnifiedScoutWorkflow(Workflow):
    """
    Unified scout workflow that auto-detects scan mode.

    - First run or forced full: Complete codebase analysis
    - Subsequent runs: Incremental scan of changed files only
    - Always extracts coding rules from patterns discovered
    """

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self._config = get_agent_config(project_root)

        super().__init__(name="Unified Scout Workflow")

        # Knowledge systems
        self.knowledge_store = KnowledgeStore(project_root)
        self._knowledge_repo = get_knowledge_repository()

        # Load the scout agent
        self._load_agents()

    def _load_agents(self):
        """Load required agents."""
        try:
            self.register_agent(Agent.load("scout", self.project_root))
        except FileNotFoundError:
            self.console.print("[red]Error: scout agent not found[/red]")
            raise

    def _get_git_state(self) -> dict:
        """Get current git state (commit hash, branch)."""
        git_state = {
            "commit_hash": None,
            "branch": None,
        }

        try:
            # Get current commit hash
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                git_state["commit_hash"] = result.stdout.strip()

            # Get current branch
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                git_state["branch"] = result.stdout.strip()
        except Exception as e:
            self.console.print(f"  [dim]Warning: Could not get git state: {e}[/dim]")

        return git_state

    def _get_changed_files_since_commit(self, commit_hash: str) -> list[str]:
        """Get list of files changed since a specific commit."""
        changed_files = []

        try:
            # Get changed files
            result = subprocess.run(
                ["git", "diff", "--name-only", commit_hash, "HEAD"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                changed_files = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]

            # Also get untracked files
            result = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                untracked = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
                changed_files.extend(untracked)
        except Exception as e:
            self.console.print(f"  [dim]Warning: Could not get changed files: {e}[/dim]")

        return list(set(changed_files))

    def _count_commits_since(self, commit_hash: str) -> int:
        """Count commits since a specific commit."""
        try:
            result = subprocess.run(
                ["git", "rev-list", "--count", f"{commit_hash}..HEAD"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return int(result.stdout.strip())
        except Exception:
            pass
        return 0

    def _should_do_full_scan(
        self,
        force_full: bool = False,
        target_paths: Optional[list[str]] = None
    ) -> tuple[bool, str]:
        """
        Determine if a full scan is needed.

        Returns:
            (should_full_scan, reason)
        """
        if force_full:
            return True, "Full scan requested"

        if target_paths:
            return False, f"Targeted scan of {len(target_paths)} paths"

        # Check if knowledge exists
        if not self.knowledge_store.exists():
            return True, "No existing knowledge found"

        # Get last scan metadata
        last_scan = self._knowledge_repo.get_scan_metadata()
        if not last_scan:
            return True, "No previous scan metadata"

        # Check if we have git state from last scan
        last_commit = last_scan.get("git_commit_hash")
        if not last_commit:
            return True, "No git commit hash from previous scan"

        # Get current git state
        current_state = self._get_git_state()
        current_commit = current_state.get("commit_hash")

        if not current_commit:
            return True, "Cannot determine current git state"

        # If same commit, no scan needed
        if last_commit == current_commit:
            return False, "No changes since last scan"

        # Check how many commits behind
        commits_behind = self._count_commits_since(last_commit)
        if commits_behind > 50:
            return True, f"{commits_behind} commits since last scan (threshold: 50)"

        # Get changed files
        changed_files = self._get_changed_files_since_commit(last_commit)

        # Filter to only source files (exclude generated/deps)
        source_files = [
            f for f in changed_files
            if not any(skip in f for skip in [
                'node_modules', '.venv', 'venv', '__pycache__',
                'dist', 'build', '.git', '.orchestrator'
            ])
        ]

        if len(source_files) > 100:
            return True, f"{len(source_files)} files changed (threshold: 100)"

        return False, f"Incremental scan: {len(source_files)} files changed"

    def _filter_source_paths(self, paths: list[str]) -> list[str]:
        """Filter paths to only include relevant source files."""
        excluded_patterns = [
            'node_modules', '.venv', 'venv', '__pycache__',
            'dist', 'build', '.git', '.orchestrator',
            'bin', 'obj', '.vs', '.idea', 'packages'
        ]

        filtered = []
        for path in paths:
            if not any(pattern in path for pattern in excluded_patterns):
                filtered.append(path)

        return filtered

    def execute(
        self,
        force_full: bool = False,
        target_paths: Optional[list[str]] = None,
        trigger: str = "manual"
    ) -> WorkflowResult:
        """
        Execute the unified scout workflow.

        Args:
            force_full: Force a full scan even if incremental would work
            target_paths: Specific paths to scan (for targeted scans)
            trigger: What triggered this scan (manual, auto, post_build)

        Returns:
            WorkflowResult with scan results
        """
        from core.symbols import CHECK, CROSS, ARROW_RIGHT

        self.console.print(f"\n[bold]Scout:[/bold] Analyzing codebase...")

        # Determine scan mode
        should_full, reason = self._should_do_full_scan(force_full, target_paths)

        self.console.print(f"  [dim]Mode: {'Full' if should_full else 'Incremental'} ({reason})[/dim]")
        self.console.print(f"  [dim]Trigger: {trigger}[/dim]")

        # Get current git state
        git_state = self._get_git_state()

        # Determine what to scan
        paths_to_scan = []
        if target_paths:
            paths_to_scan = self._filter_source_paths(target_paths)
        elif not should_full:
            # Get changed files for incremental scan
            last_scan = self._knowledge_repo.get_scan_metadata()
            last_commit = last_scan.get("git_commit_hash") if last_scan else None
            if last_commit:
                changed_files = self._get_changed_files_since_commit(last_commit)
                paths_to_scan = self._filter_source_paths(changed_files)

        # Build scout prompt based on mode
        if should_full:
            scout_prompt = self._build_full_scan_prompt()
        else:
            scout_prompt = self._build_incremental_scan_prompt(paths_to_scan)

        # Run scout agent
        self.console.print(f"\n[cyan]{ARROW_RIGHT}[/cyan] Running scout agent...")

        result = self.run_agent(
            "scout",
            message=scout_prompt,
            show_progress=True
        )

        if not result.success:
            self.console.print(f"  [red]{CROSS}[/red] Scout failed: {result.error}")
            return WorkflowResult(
                success=False,
                error=f"Scout failed: {result.error}"
            )

        # Parse and store results
        knowledge_data = self._parse_scout_output(result.content)

        if not knowledge_data:
            self.console.print(f"  [yellow]Warning: Could not parse scout output[/yellow]")
            return WorkflowResult(
                success=False,
                error="Could not parse scout output"
            )

        # Merge with existing knowledge if incremental
        if not should_full and self.knowledge_store.exists():
            knowledge_data = self._merge_knowledge(knowledge_data)

        # Save to knowledge store
        self._save_knowledge(knowledge_data, git_state, paths_to_scan, trigger)

        # Report results
        stats = knowledge_data.get("statistics", {})
        coding_rules = knowledge_data.get("coding_rules", [])

        self.console.print(f"\n[green]{CHECK}[/green] Scout completed!")
        self.console.print(f"  Files scanned: [cyan]{stats.get('total_files', 'N/A')}[/cyan]")
        self.console.print(f"  Domains found: [cyan]{len(knowledge_data.get('domains', []))}[/cyan]")
        self.console.print(f"  Coding rules: [cyan]{len(coding_rules)}[/cyan]")

        return WorkflowResult(
            success=True,
            data={
                "mode": "full" if should_full else "incremental",
                "files_scanned": stats.get("total_files", 0),
                "domains": len(knowledge_data.get("domains", [])),
                "coding_rules": len(coding_rules),
                "git_commit": git_state.get("commit_hash"),
            }
        )

    def _build_full_scan_prompt(self) -> str:
        """Build prompt for full codebase scan."""
        return """Perform a FULL analysis of this codebase.

Analyze:
1. Project structure and type
2. Technologies (languages, frameworks, tools)
3. Architecture patterns and modules
4. Business domains
5. Coding conventions and patterns
6. **CODING RULES** - Extract explicit and implicit rules

For CODING RULES, identify:
- Naming conventions (files, classes, functions, variables)
- Code organization patterns (where things go)
- Import/export patterns
- Error handling patterns
- Testing patterns
- Documentation patterns

Output the standard JSON format with an additional "coding_rules" section:

```json
{
  "project": {...},
  "technologies": {...},
  "architecture": {...},
  "domains": [...],
  "patterns": {...},
  "statistics": {...},
  "coding_rules": [
    {
      "id": "naming-001",
      "category": "naming",
      "rule": "Use snake_case for Python file names",
      "severity": "warning",
      "examples": ["user_service.py (good)", "UserService.py (bad)"],
      "source_files": ["src/services/user_service.py"],
      "confidence": 0.9
    }
  ]
}
```

Categories for coding rules: naming, structure, patterns, security, testing, documentation
Severity levels: info, warning, error"""

    def _build_incremental_scan_prompt(self, changed_paths: list[str]) -> str:
        """Build prompt for incremental scan of changed files."""
        paths_list = "\n".join(f"- {p}" for p in changed_paths[:50])
        if len(changed_paths) > 50:
            paths_list += f"\n... and {len(changed_paths) - 50} more files"

        return f"""Perform an INCREMENTAL analysis of recently changed files.

Changed files to analyze:
{paths_list}

Focus on:
1. What changed in these files
2. Any new patterns or conventions
3. New domains or modules introduced
4. Any coding rule violations or new rules to add

Output the standard JSON format, but ONLY include information relevant to the changed files.
Include any new "coding_rules" discovered from the changes.

Note: This will be merged with existing knowledge, so only include NEW or CHANGED information."""

    def _parse_scout_output(self, output: str) -> Optional[dict]:
        """Parse JSON output from scout agent."""
        # Look for OUTPUT_JSON marker
        json_match = re.search(r'OUTPUT_JSON:\s*```json\s*(.+?)\s*```', output, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find any JSON block
        json_blocks = re.findall(r'```(?:json)?\s*(\{.+?\})\s*```', output, re.DOTALL)
        for block in json_blocks:
            try:
                data = json.loads(block)
                if "project" in data or "technologies" in data:
                    return data
            except json.JSONDecodeError:
                continue

        # Try to parse the entire output as JSON
        try:
            # Find the outermost JSON object
            start = output.find('{')
            end = output.rfind('}') + 1
            if start != -1 and end > start:
                return json.loads(output[start:end])
        except json.JSONDecodeError:
            pass

        return None

    def _merge_knowledge(self, new_data: dict) -> dict:
        """Merge new knowledge with existing knowledge."""
        existing = self.knowledge_store.load()
        if not existing:
            return new_data

        # Convert existing to dict for merging
        existing_dict = existing.to_dict() if hasattr(existing, 'to_dict') else {}

        # Merge technologies (add new, update confidence for existing)
        for tech_type in ['languages', 'frameworks', 'tools']:
            existing_techs = {t.get('name'): t for t in existing_dict.get('technologies', {}).get(tech_type, [])}
            new_techs = new_data.get('technologies', {}).get(tech_type, [])

            for new_tech in new_techs:
                name = new_tech.get('name')
                if name in existing_techs:
                    # Update confidence to max
                    existing_techs[name]['confidence'] = max(
                        existing_techs[name].get('confidence', 0),
                        new_tech.get('confidence', 0)
                    )
                else:
                    existing_techs[name] = new_tech

            if 'technologies' not in new_data:
                new_data['technologies'] = {}
            new_data['technologies'][tech_type] = list(existing_techs.values())

        # Merge domains (add new, merge files for existing)
        existing_domains = {d.get('name'): d for d in existing_dict.get('domains', [])}
        new_domains = new_data.get('domains', [])

        for new_domain in new_domains:
            name = new_domain.get('name')
            if name in existing_domains:
                # Merge files and keywords
                existing_files = set(existing_domains[name].get('files', []))
                existing_files.update(new_domain.get('files', []))
                existing_domains[name]['files'] = list(existing_files)

                existing_keywords = set(existing_domains[name].get('keywords', []))
                existing_keywords.update(new_domain.get('keywords', []))
                existing_domains[name]['keywords'] = list(existing_keywords)
            else:
                existing_domains[name] = new_domain

        new_data['domains'] = list(existing_domains.values())

        # Merge coding rules (add new, don't duplicate)
        existing_rules = {r.get('id'): r for r in existing_dict.get('coding_rules', [])}
        new_rules = new_data.get('coding_rules', [])

        for new_rule in new_rules:
            rule_id = new_rule.get('id')
            if rule_id not in existing_rules:
                existing_rules[rule_id] = new_rule
            else:
                # Update confidence to max
                existing_rules[rule_id]['confidence'] = max(
                    existing_rules[rule_id].get('confidence', 0),
                    new_rule.get('confidence', 0)
                )

        new_data['coding_rules'] = list(existing_rules.values())

        return new_data

    def _save_knowledge(
        self,
        data: dict,
        git_state: dict,
        scanned_paths: list[str],
        trigger: str
    ):
        """Save knowledge to store and database."""
        # Build CodebaseKnowledge object
        project_data = data.get('project', {})
        technologies_data = data.get('technologies', {})
        architecture_data = data.get('architecture', {})
        domains_data = data.get('domains', [])
        patterns_data = data.get('patterns', {})
        statistics = data.get('statistics', {})
        coding_rules_data = data.get('coding_rules', [])

        # Build technology lists
        languages = [
            TechInfo(
                name=t.get('name', ''),
                confidence=t.get('confidence', 0.5),
                version=t.get('version')
            )
            for t in technologies_data.get('languages', [])
        ]

        frameworks = [
            TechInfo(
                name=t.get('name', ''),
                confidence=t.get('confidence', 0.5),
                version=t.get('version')
            )
            for t in technologies_data.get('frameworks', [])
        ]

        tools = [
            TechInfo(
                name=t.get('name', ''),
                confidence=t.get('confidence', 0.5),
                version=t.get('version')
            )
            for t in technologies_data.get('tools', [])
        ]

        # Build modules
        modules = [
            ModuleInfo(
                name=m.get('name', ''),
                path=m.get('path', ''),
                purpose=m.get('purpose', ''),
                depends_on=m.get('depends_on', [])
            )
            for m in architecture_data.get('modules', [])
        ]

        # Build domains
        domains = [
            DomainInfo(
                name=d.get('name', ''),
                keywords=d.get('keywords', []),
                files=d.get('files', []),
                models=d.get('models', []),
                routes=d.get('routes', [])
            )
            for d in domains_data
        ]

        # Build coding rules
        coding_rules = [
            CodingRule(
                id=r.get('id', f"rule-{i}"),
                category=r.get('category', 'general'),
                rule=r.get('rule', ''),
                severity=r.get('severity', 'info'),
                examples=r.get('examples', []),
                source_files=r.get('source_files', []),
                confidence=r.get('confidence', 0.5)
            )
            for i, r in enumerate(coding_rules_data)
        ]

        # Create knowledge object using proper dataclass structure
        knowledge = CodebaseKnowledge(
            version="1.0",
            last_updated=datetime.now().isoformat(),
            project=ProjectInfo(
                name=project_data.get('name', ''),
                type=project_data.get('type', ''),
                primary_language=project_data.get('primary_language', '')
            ),
            technologies=TechnologiesInfo(
                languages=languages,
                frameworks=frameworks,
                tools=tools
            ),
            architecture=ArchitectureInfo(
                pattern=architecture_data.get('pattern', ''),
                modules=modules,
                entry_points=architecture_data.get('entry_points', [])
            ),
            domains=domains,
            patterns=PatternInfo(
                naming=patterns_data.get('naming', {}),
                structure=patterns_data.get('structure', {}),
                conventions=patterns_data.get('conventions', [])
            ),
            statistics=statistics,
            coding_rules=coding_rules
        )

        # Save to knowledge store
        self.knowledge_store.save(knowledge)

        # Save scan metadata to database
        self._knowledge_repo.save_scan_metadata({
            "git_commit_hash": git_state.get("commit_hash"),
            "git_branch": git_state.get("branch"),
            "scanned_paths": scanned_paths,
            "trigger": trigger,
            "scan_time": datetime.now().isoformat(),
            "mode": "full" if not scanned_paths else "incremental"
        })

        # Save coding rules to database
        for rule in coding_rules:
            self._knowledge_repo.save_coding_rule(rule)


def run(args=None) -> int:
    """Run unified scout from CLI."""
    project_root = Path(__file__).parent.parent.parent

    # Parse arguments
    force_full = args and "--full" in args
    target_paths = None

    if args:
        # Filter out flags to get paths
        paths = [a for a in args if not a.startswith("--")]
        if paths:
            target_paths = paths

    workflow = UnifiedScoutWorkflow(project_root=project_root)
    result = workflow.run(
        force_full=force_full,
        target_paths=target_paths,
        trigger="manual"
    )

    return 0 if result.success else 1


if __name__ == "__main__":
    import sys
    sys.exit(run(sys.argv[1:]))
