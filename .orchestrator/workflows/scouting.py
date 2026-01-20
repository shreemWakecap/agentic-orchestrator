"""
Scouting Workflow.

Analyzes the codebase to build persistent knowledge.

Flow:
    Manual Trigger → Scout Agent → knowledge/codebase.json

The scout agent:
1. Explores the codebase structure
2. Detects technologies and frameworks
3. Identifies architecture patterns
4. Discovers business domains
5. Captures naming conventions

Post-scan:
- Saves knowledge to knowledge/codebase.json
- Identifies missing experts
- Optionally triggers expert auto-generation
"""
import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from core import Agent, Workflow, WorkflowResult, get_agent_config
from core.knowledge_store import (
    KnowledgeStore,
    CodebaseKnowledge,
    ProjectInfo,
    TechnologiesInfo,
    TechInfo,
    ArchitectureInfo,
    ModuleInfo,
    DomainInfo,
    PatternInfo,
    ScanMeta,
)


class ScoutingWorkflow(Workflow):
    """
    Scouting workflow for codebase analysis.

    Runs the scout agent to analyze the codebase and populate
    the knowledge store with architecture, domains, and patterns.
    """

    def __init__(
        self,
        project_root: Path,
        scan_type: str = "full",  # full or quick
        generate_experts: bool = False,
    ):
        self.project_root = project_root
        self.scan_type = scan_type
        self.generate_experts = generate_experts
        self._config = get_agent_config(project_root)

        # Knowledge store
        self.knowledge_store = KnowledgeStore(project_root)

        # Output dir for any artifacts
        output_dir = project_root / ".orchestrator" / "knowledge"
        output_dir.mkdir(parents=True, exist_ok=True)

        super().__init__(name="Scouting Workflow", output_dir=output_dir)

        # Load the scout agent
        self._load_agents()

    def _load_agents(self):
        """Load required agents."""
        try:
            self.register_agent(Agent.load("scout", self.project_root))
        except FileNotFoundError:
            self.console.print("[red]Error: scout agent not found[/red]")
            raise

    def _get_quick_context(self) -> str:
        """Get minimal context for quick scan."""
        parts = []

        # Top-level directories
        try:
            dirs = [d.name for d in self.project_root.iterdir()
                    if d.is_dir() and not d.name.startswith(".")][:10]
            if dirs:
                parts.append(f"Directories: {', '.join(sorted(dirs))}")
        except Exception:
            pass

        # Config files
        config_files = [
            "package.json", "pyproject.toml", "Cargo.toml",
            "go.mod", "requirements.txt", "tsconfig.json"
        ]
        found = [f for f in config_files if (self.project_root / f).exists()]
        if found:
            parts.append(f"Config files: {', '.join(found)}")

        return "\n".join(parts)

    def execute(self, request: str) -> WorkflowResult:
        """
        Execute the scouting workflow.

        Args:
            request: Request string (unused, required by base class interface)

        Returns:
            WorkflowResult with the knowledge store populated
        """
        from core.symbols import CHECK, CROSS, ARROW_RIGHT, SPARKLES

        self.console.print(f"\n[bold]Scouting codebase[/bold] ({self.scan_type} scan)")

        # Start timing
        scan_id = str(uuid.uuid4())[:8]
        started_at = datetime.now()

        # Build scout prompt based on scan type
        if self.scan_type == "quick":
            context = self._get_quick_context()
            scout_prompt = f"""Perform a quick analysis of this codebase:

{context}

Focus on:
- Primary language and key frameworks
- Top-level architecture (module structure)
- Main entry points

Output the JSON with at least: project, technologies, architecture.entry_points
Skip detailed domain analysis for quick scan.
"""
        else:
            scout_prompt = """Perform a thorough analysis of this codebase.

Follow all 5 phases:
1. STRUCTURE - Map directories and identify project type
2. TECHNOLOGY - Detect languages, frameworks, tools with confidence
3. ARCHITECTURE - Identify pattern and module dependencies
4. DOMAINS - Find business concepts (auth, payments, etc.)
5. PATTERNS - Capture naming and conventions

Output complete JSON with all sections populated.
Explore deeply - read actual files, don't just guess from names.
"""

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

        # Extract JSON from response
        knowledge_data = self._extract_json(result.content)

        if not knowledge_data:
            self.console.print(f"  [red]{CROSS}[/red] No valid JSON found in scout response")
            return WorkflowResult(
                success=False,
                error="Scout did not produce valid JSON"
            )

        # Convert to CodebaseKnowledge
        knowledge = self._parse_knowledge(knowledge_data)

        # Save to knowledge store
        if not self.knowledge_store.save(knowledge):
            self.console.print(f"  [red]{CROSS}[/red] Failed to save knowledge")
            return WorkflowResult(
                success=False,
                error="Failed to save knowledge store"
            )

        # Calculate statistics
        completed_at = datetime.now()
        duration = (completed_at - started_at).total_seconds()
        files_scanned = knowledge.statistics.get("total_files", 0)

        # Save scan metadata
        meta = ScanMeta(
            scan_id=scan_id,
            started_at=started_at.isoformat(),
            completed_at=completed_at.isoformat(),
            duration_seconds=duration,
            files_scanned=files_scanned,
            scan_type=self.scan_type,
            trigger="manual",
            experts_generated=[],
        )

        # Find missing experts
        missing_experts = []
        if self.generate_experts:
            missing_experts = self._find_and_generate_experts(knowledge)
            meta.experts_generated = missing_experts

        self.knowledge_store.save_meta(meta)

        # Print summary
        self.console.print(f"\n[green]{CHECK}[/green] Scouting complete!")
        self.console.print(f"  [dim]Duration: {duration:.1f}s | Files: {files_scanned}[/dim]")

        if knowledge.project.name:
            self.console.print(f"  Project: [cyan]{knowledge.project.name}[/cyan] ({knowledge.project.type})")

        if knowledge.technologies.languages:
            langs = ", ".join(t.name for t in knowledge.technologies.languages)
            self.console.print(f"  Languages: [cyan]{langs}[/cyan]")

        if knowledge.technologies.frameworks:
            fws = ", ".join(t.name for t in knowledge.technologies.frameworks)
            self.console.print(f"  Frameworks: [cyan]{fws}[/cyan]")

        if knowledge.domains:
            domains = ", ".join(d.name for d in knowledge.domains)
            self.console.print(f"  Domains: [cyan]{domains}[/cyan]")

        if knowledge.architecture.pattern != "unknown":
            self.console.print(f"  Architecture: [cyan]{knowledge.architecture.pattern}[/cyan]")

        if missing_experts:
            self.console.print(f"\n[yellow]{SPARKLES}[/yellow] Generated experts: {', '.join(missing_experts)}")

        return WorkflowResult(
            success=True,
            output_file=self.knowledge_store.codebase_file,
            data={
                "scan_id": scan_id,
                "duration": duration,
                "files_scanned": files_scanned,
                "domains_found": len(knowledge.domains),
                "experts_generated": missing_experts,
            }
        )

    def _extract_json(self, response: str) -> Optional[dict]:
        """Extract JSON from scout response."""
        # Look for OUTPUT_JSON: marker
        json_match = re.search(
            r"OUTPUT_JSON:\s*(\{.*\})",
            response,
            re.DOTALL
        )
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find JSON in code block
        code_match = re.search(
            r"```(?:json)?\s*(\{.*?\})\s*```",
            response,
            re.DOTALL
        )
        if code_match:
            try:
                return json.loads(code_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find raw JSON
        brace_match = re.search(r"(\{[\s\S]*\})", response)
        if brace_match:
            try:
                return json.loads(brace_match.group(1))
            except json.JSONDecodeError:
                pass

        return None

    def _parse_knowledge(self, data: dict) -> CodebaseKnowledge:
        """Parse JSON data into CodebaseKnowledge."""
        project_data = data.get("project", {})
        tech_data = data.get("technologies", {})
        arch_data = data.get("architecture", {})
        pattern_data = data.get("patterns", {})

        # Parse technologies
        languages = [
            TechInfo(
                name=t.get("name", ""),
                confidence=t.get("confidence", 0.0),
                version=t.get("version"),
            )
            for t in tech_data.get("languages", [])
        ]

        frameworks = [
            TechInfo(
                name=t.get("name", ""),
                confidence=t.get("confidence", 0.0),
                entry_point=t.get("entry_point"),
            )
            for t in tech_data.get("frameworks", [])
        ]

        tools = [
            TechInfo(
                name=t.get("name", ""),
                confidence=t.get("confidence", 0.0),
                config_file=t.get("config_file"),
            )
            for t in tech_data.get("tools", [])
        ]

        # Parse modules
        modules = [
            ModuleInfo(
                name=m.get("name", ""),
                path=m.get("path", ""),
                purpose=m.get("purpose", ""),
                depends_on=m.get("depends_on", []),
            )
            for m in arch_data.get("modules", [])
        ]

        # Parse domains
        domains = [
            DomainInfo(
                name=d.get("name", ""),
                keywords=d.get("keywords", []),
                files=d.get("files", []),
                models=d.get("models", []),
                routes=d.get("routes", []),
            )
            for d in data.get("domains", [])
        ]

        return CodebaseKnowledge(
            project=ProjectInfo(
                name=project_data.get("name", ""),
                type=project_data.get("type", "unknown"),
                primary_language=project_data.get("primary_language", ""),
            ),
            technologies=TechnologiesInfo(
                languages=languages,
                frameworks=frameworks,
                tools=tools,
            ),
            architecture=ArchitectureInfo(
                pattern=arch_data.get("pattern", "unknown"),
                modules=modules,
                entry_points=arch_data.get("entry_points", []),
            ),
            domains=domains,
            patterns=PatternInfo(
                naming=pattern_data.get("naming", {}),
                structure=pattern_data.get("structure", {}),
                conventions=pattern_data.get("conventions", []),
            ),
            statistics=data.get("statistics", {}),
        )

    def _find_and_generate_experts(self, knowledge: CodebaseKnowledge) -> list[str]:
        """Find and generate missing experts based on knowledge."""
        generated = []

        try:
            from core.expert_loader import ExpertLoader, ExpertType

            loader = ExpertLoader(self.project_root)
            existing = [e.name.lower() for e in loader.discover_experts()]

            # Check for missing tech experts
            all_techs = (
                [t.name for t in knowledge.technologies.languages] +
                [t.name for t in knowledge.technologies.frameworks]
            )

            for tech in all_techs:
                if tech.lower() not in existing:
                    self.console.print(f"  [dim]Creating expert for: {tech}[/dim]")
                    if loader.create_expert(tech, expert_type=ExpertType.TECH):
                        generated.append(tech)

            # Check for domain experts
            for domain in knowledge.domains:
                domain_name = f"{domain.name}-domain"
                if domain_name.lower() not in existing and domain.name.lower() not in existing:
                    self.console.print(f"  [dim]Creating domain expert: {domain.name}[/dim]")
                    if loader.create_expert(
                        domain.name,
                        expert_type=ExpertType.DOMAIN,
                        domain_keywords=domain.keywords,
                    ):
                        generated.append(domain.name)

        except Exception as e:
            self.console.print(f"  [yellow]Warning: Expert generation failed: {e}[/yellow]")

        return generated


def run(args=None) -> int:
    """Run scouting action from CLI."""
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Scout the codebase")
    parser.add_argument(
        "--file", "-f",
        type=str,
        metavar="PATH",
        help="Scout a single file instead of the entire codebase"
    )
    parser.add_argument(
        "--quick", "-q",
        action="store_true",
        help="Quick scan (structure and tech only) - ignored when --file is used"
    )
    parser.add_argument(
        "--generate-experts", "-g",
        action="store_true",
        help="Auto-generate missing experts after scan - ignored when --file is used"
    )

    parsed = parser.parse_args(args or [])
    project_root = Path(__file__).parent.parent.parent

    # File-specific scouting mode
    if parsed.file:
        from rich.console import Console
        console = Console()

        # Resolve file path to absolute
        file_path = Path(parsed.file)
        if not file_path.is_absolute():
            file_path = (project_root / file_path).resolve()
        else:
            file_path = file_path.resolve()

        # Validate file exists
        if not file_path.exists():
            console.print(f"[red]Error:[/red] File does not exist: {file_path}")
            return 1

        # Validate it's a file (not directory)
        if not file_path.is_file():
            console.print(f"[red]Error:[/red] Path is not a file: {file_path}")
            return 1

        # Validate file is readable
        try:
            with open(file_path, "rb") as f:
                f.read(1)
        except PermissionError:
            console.print(f"[red]Error:[/red] Permission denied: {file_path}")
            return 1
        except Exception as e:
            console.print(f"[red]Error:[/red] Cannot read file: {file_path} - {e}")
            return 1

        # Import and run FileScoutingWorkflow
        from workflows.file_scouting import FileScoutingWorkflow

        workflow = FileScoutingWorkflow(project_root=project_root)
        result = workflow.run(str(file_path))

        # Print file-specific summary
        if result.success and result.data:
            console.print("\n[bold]File Knowledge Summary:[/bold]")
            console.print(f"  Language: [cyan]{result.data.get('language', 'unknown')}[/cyan]")
            console.print(f"  Lines: [cyan]{result.data.get('line_count', 0)}[/cyan]")
            console.print(f"  Classes: [cyan]{result.data.get('classes_count', 0)}[/cyan]")
            console.print(f"  Functions: [cyan]{result.data.get('functions_count', 0)}[/cyan]")
            console.print(f"  Imports: [cyan]{result.data.get('imports_count', 0)}[/cyan]")
            console.print(f"  Dependencies: [cyan]{result.data.get('dependencies_count', 0)}[/cyan]")

        return 0 if result.success else 1

    # Bulk scouting mode (default)
    scan_type = "quick" if parsed.quick else "full"

    workflow = ScoutingWorkflow(
        project_root=project_root,
        scan_type=scan_type,
        generate_experts=parsed.generate_experts,
    )

    result = workflow.run("")

    return 0 if result.success else 1


if __name__ == "__main__":
    import sys
    sys.exit(run(sys.argv[1:]))
