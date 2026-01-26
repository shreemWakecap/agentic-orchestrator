"""
Smart Scouting Workflow: Multi-phase, user-guided codebase analysis.

Phases:
    1. Criteria Collection - Get user input on focus, depth, areas
    2. Domain Detection - Scan project structure
    3. User Approval - Review and select domains to scan
    4. Layered Exploration - Scout each domain with depth layers
    5. Synthesis - Aggregate knowledge and generate experts

Usage:
    workflow = SmartScoutingWorkflow(project_root)
    result = workflow.run()
"""
import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm

from core import Agent, Workflow, WorkflowResult, get_agent_config
from core.domain_scanner import DomainScanner, detect_project_domains
from core.knowledge_store import (
    KnowledgeStore,
    ScanCriteria,
    DetectedDomain,
    ApprovedDomain,
    SmartScanSession,
    LayeredKnowledge,
    SolutionOverview,
    TechStackInfo,
    DomainDetails,
    DeepTechnicalInfo,
    TechInfo,
    RiskInfo,
    RuleInfo,
)


class SmartScoutingWorkflow(Workflow):
    """
    Multi-phase scouting workflow with user guidance.

    Builds layered knowledge incrementally:
    - Layer 1: Solution Overview
    - Layer 2: Technology Stack
    - Layer 3: Domain Details
    - Layer 4: Deep Technical (patterns, risks, rules)
    """

    def __init__(
        self,
        project_root: Path,
        interactive: bool = True,
        criteria: Optional[ScanCriteria] = None,
    ):
        self.project_root = project_root
        self.interactive = interactive
        self.criteria = criteria
        self._config = get_agent_config(project_root)

        # Components
        self.domain_scanner = DomainScanner(project_root)
        self.knowledge_store = KnowledgeStore(project_root)
        self.console = Console()

        # Session tracking
        self.session = SmartScanSession(
            session_id=str(uuid.uuid4())[:8],
            started_at=datetime.now().isoformat(),
            status="pending",
        )

        # Output directory
        output_dir = project_root / ".orchestrator" / "knowledge"
        output_dir.mkdir(parents=True, exist_ok=True)

        super().__init__(name="Smart Scout", output_dir=output_dir)

        # Load agents
        self._load_agents()

    def _load_agents(self):
        """Load required agents for each layer."""
        agent_names = [
            "scout-overview",   # Layer 1
            "scout-techstack",  # Layer 2
            "scout-domain",     # Layer 3
            "scout-deep",       # Layer 4
            "scout",            # Legacy fallback
        ]

        for name in agent_names:
            try:
                self.register_agent(Agent.load(name, self.project_root))
            except ValueError:
                pass  # Agent not available, will use fallback

    def _extract_json(self, response: str) -> Optional[dict]:
        """Extract JSON from agent response."""
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

    def _has_agent(self, name: str) -> bool:
        """Check if an agent is loaded."""
        return name in self._agents

    def execute(self, request: str = "") -> WorkflowResult:
        """Execute the multi-phase scouting workflow."""
        from core.symbols import CHECK, CROSS, ARROW_RIGHT, SPARKLES

        self.console.print(Panel.fit(
            "[bold cyan]Smart Scout[/bold cyan]\n"
            "Technology-agnostic, layered knowledge builder",
            border_style="cyan"
        ))

        try:
            # Phase 1: Criteria Collection
            self.session.current_phase = 1
            self.session.status = "in_progress"

            if self.criteria:
                # Use provided criteria
                self.session.criteria = self.criteria
            elif self.interactive:
                # Collect from user
                self.session.criteria = self._phase1_collect_criteria()
            else:
                # Use defaults
                self.session.criteria = ScanCriteria(
                    focus="overview",
                    areas=["backend", "frontend"],
                    depth="standard",
                )

            self.console.print(f"\n[green]{CHECK}[/green] Phase 1: Criteria collected")

            # Phase 2: Domain Detection
            self.session.current_phase = 2
            self.console.print(f"\n[cyan]{ARROW_RIGHT}[/cyan] Phase 2: Detecting domains...")

            self.session.detected_domains = self._phase2_detect_domains()

            if not self.session.detected_domains:
                return WorkflowResult(
                    success=False,
                    error="No domains detected in project"
                )

            self.console.print(f"[green]{CHECK}[/green] Detected {len(self.session.detected_domains)} domains")

            # Phase 3: User Approval
            self.session.current_phase = 3

            if self.interactive:
                self.session.approved_domains = self._phase3_user_approval()
            else:
                # Auto-approve code domains
                self.session.approved_domains = [
                    ApprovedDomain(
                        path=d.path,
                        name=d.name,
                        scan_depth=self.session.criteria.depth,
                        priority=i,
                    )
                    for i, d in enumerate(self.session.detected_domains)
                    if d.classification == "code"
                ]

            if not self.session.approved_domains:
                return WorkflowResult(
                    success=False,
                    error="No domains selected for scanning"
                )

            self.console.print(f"[green]{CHECK}[/green] Phase 3: {len(self.session.approved_domains)} domains approved")

            # Phase 4: Layered Exploration
            self.session.current_phase = 4
            self.console.print(f"\n[cyan]{ARROW_RIGHT}[/cyan] Phase 4: Layered exploration...")

            self._phase4_layered_exploration()

            self.console.print(f"[green]{CHECK}[/green] Phase 4: Exploration complete")

            # Phase 5: Synthesis
            self.session.current_phase = 5
            self.console.print(f"\n[cyan]{ARROW_RIGHT}[/cyan] Phase 5: Synthesizing knowledge...")

            self._phase5_synthesis()

            self.session.completed_at = datetime.now().isoformat()
            self.session.status = "completed"

            self.console.print(f"\n[green]{CHECK}[/green] [bold]Smart Scout complete![/bold]")

            # Print summary
            self._print_summary()

            return WorkflowResult(
                success=True,
                output_file=self.output_dir / "session.json",
                data={
                    "session_id": self.session.session_id,
                    "domains_scanned": len(self.session.approved_domains),
                    "experts_generated": self.session.experts_generated,
                    "rules_extracted": len(self.session.rules_extracted),
                }
            )

        except KeyboardInterrupt:
            self.session.status = "cancelled"
            self.console.print("\n[yellow]Scan cancelled by user[/yellow]")
            return WorkflowResult(success=False, error="Cancelled by user")

        except Exception as e:
            self.session.status = "failed"
            self.console.print(f"\n[red]{CROSS}[/red] Error: {e}")
            return WorkflowResult(success=False, error=str(e))

    # --- Phase 1: Criteria Collection ---

    def _phase1_collect_criteria(self) -> ScanCriteria:
        """Collect scan criteria from user interactively."""
        self.console.print("\n[bold]Phase 1: Configure your scan[/bold]\n")

        # Focus selection
        self.console.print("What is your focus for this scan?")
        self.console.print("  1. Full solution overview (recommended for first scan)")
        self.console.print("  2. Specific domains only")
        self.console.print("  3. Deep technical audit")
        self.console.print("  4. Architecture review")

        focus_choice = Prompt.ask(
            "Select",
            choices=["1", "2", "3", "4"],
            default="1"
        )

        focus_map = {"1": "overview", "2": "domains", "3": "audit", "4": "architecture"}
        focus = focus_map[focus_choice]

        # Areas of interest
        self.console.print("\nSelect areas of interest:")
        areas = []
        area_options = [
            ("backend", "Backend services"),
            ("frontend", "Frontend/UI"),
            ("infra", "Infrastructure/DevOps"),
            ("data", "Database/Data layer"),
            ("testing", "Testing"),
        ]

        for key, label in area_options:
            if Confirm.ask(f"  Include {label}?", default=True):
                areas.append(key)

        if not areas:
            areas = ["backend", "frontend"]  # Default

        # Scan depth
        self.console.print("\nScan depth:")
        self.console.print("  1. Quick - Structure + tech detection only")
        self.console.print("  2. Standard - + Domain analysis")
        self.console.print("  3. Deep - + Patterns, risks, rules")

        depth_choice = Prompt.ask(
            "Select",
            choices=["1", "2", "3"],
            default="2"
        )

        depth_map = {"1": "quick", "2": "standard", "3": "deep"}
        depth = depth_map[depth_choice]

        # Specific paths (optional)
        specific_paths = []
        if Confirm.ask("\nWant to specify particular paths?", default=False):
            paths_input = Prompt.ask("Enter paths (comma-separated)")
            specific_paths = [p.strip() for p in paths_input.split(",") if p.strip()]

        return ScanCriteria(
            focus=focus,
            areas=areas,
            depth=depth,
            specific_paths=specific_paths,
        )

    # --- Phase 2: Domain Detection ---

    def _phase2_detect_domains(self) -> list[DetectedDomain]:
        """Detect domains in the project."""
        return self.domain_scanner.detect_domains()

    # --- Phase 3: User Approval ---

    def _phase3_user_approval(self) -> list[ApprovedDomain]:
        """Get user approval for domains to scan."""
        self.console.print("\n[bold]Phase 3: Review detected domains[/bold]\n")

        # Display detected domains
        table = Table(title="Detected Domains")
        table.add_column("#", style="dim")
        table.add_column("Name", style="cyan")
        table.add_column("Type", style="green")
        table.add_column("Files")
        table.add_column("Languages")

        for i, d in enumerate(self.session.detected_domains, 1):
            langs = ", ".join(d.detected_languages) if d.detected_languages else "-"
            table.add_row(
                str(i),
                d.name,
                d.classification,
                str(d.file_count),
                langs,
            )

        self.console.print(table)
        self.console.print()

        # Get selection
        code_domains = [
            d for d in self.session.detected_domains
            if d.classification == "code"
        ]

        self.console.print("Options:")
        self.console.print("  [A] Scan all code domains")
        self.console.print("  [S] Select specific domains")
        self.console.print("  [C] Cancel")

        choice = Prompt.ask("Choose", choices=["a", "s", "c"], default="a").lower()

        if choice == "c":
            return []

        approved = []
        default_depth = self.session.criteria.depth

        if choice == "a":
            # Approve all code domains
            for i, d in enumerate(code_domains):
                approved.append(ApprovedDomain(
                    path=d.path,
                    name=d.name,
                    scan_depth=default_depth,
                    priority=i,
                ))
        else:
            # Select specific domains
            selection = Prompt.ask(
                "Enter domain numbers (comma-separated, e.g., 1,3,5)"
            )
            indices = [int(x.strip()) - 1 for x in selection.split(",") if x.strip().isdigit()]

            for i, idx in enumerate(indices):
                if 0 <= idx < len(self.session.detected_domains):
                    d = self.session.detected_domains[idx]
                    # Ask for depth per domain
                    depth = Prompt.ask(
                        f"  Depth for {d.name}",
                        choices=["quick", "standard", "deep"],
                        default=default_depth
                    )
                    approved.append(ApprovedDomain(
                        path=d.path,
                        name=d.name,
                        scan_depth=depth,
                        priority=i,
                    ))

        return approved

    # --- Phase 4: Layered Exploration ---

    def _phase4_layered_exploration(self):
        """Run layered exploration on approved domains."""
        from core.symbols import CHECK, CROSS

        total = len(self.session.approved_domains)

        for i, domain in enumerate(self.session.approved_domains, 1):
            self.console.print(f"\n  [{i}/{total}] Scanning [cyan]{domain.name}[/cyan] ({domain.scan_depth} mode)")

            try:
                knowledge = self._scan_domain_layered(domain)
                self.session.knowledge[domain.name] = knowledge
                self.console.print(f"    [green]{CHECK}[/green] Complete")
            except Exception as e:
                self.console.print(f"    [red]{CROSS}[/red] Failed: {e}")

    def _scan_domain_layered(self, domain: ApprovedDomain) -> LayeredKnowledge:
        """Scan a single domain with layered depth."""
        knowledge = LayeredKnowledge(
            domain=domain.name,
            last_scanned=datetime.now().isoformat(),
        )

        domain_path = self.project_root / domain.path

        # Layer 1: Overview (always)
        knowledge.overview = self._scan_layer1_overview(domain_path, domain.name)
        knowledge.scan_depth_reached = "quick"

        if domain.scan_depth in ["standard", "deep"]:
            # Layer 2: Tech Stack
            knowledge.tech_stack = self._scan_layer2_tech_stack(domain_path, domain.name)

            # Layer 3: Domain Details
            knowledge.domain_details = self._scan_layer3_domain_details(domain_path, domain.name)
            knowledge.scan_depth_reached = "standard"

        if domain.scan_depth == "deep":
            # Layer 4: Deep Technical
            knowledge.deep_technical = self._scan_layer4_deep_technical(domain_path, domain.name)
            knowledge.scan_depth_reached = "deep"

        return knowledge

    def _scan_layer1_overview(self, path: Path, name: str) -> SolutionOverview:
        """Layer 1: Basic structure overview using agent or fallback."""
        self.console.print("      [dim]Layer 1: Overview...[/dim]")

        # Try to use agent
        if self._has_agent("scout-overview"):
            try:
                prompt = f"""Analyze the directory: {path}
This is the '{name}' domain/module.
Provide a high-level overview following your instructions.
Remember: Do NOT scan .orchestrator/ folder."""

                result = self.run_agent("scout-overview", message=prompt, show_progress=False)
                if result.success and result.content:
                    data = self._extract_json(result.content)
                    if data:
                        return SolutionOverview(
                            purpose=data.get("purpose", ""),
                            domains=data.get("domains", []),
                            estimated_size=data.get("estimated_size", "unknown"),
                            structure_type=data.get("structure_type", "unknown"),
                            root_directories=data.get("root_directories", []),
                            primary_language=data.get("primary_language", ""),
                        )
            except Exception as e:
                self.console.print(f"      [yellow]Agent failed, using fallback: {e}[/yellow]")

        # Fallback: simple analysis
        return self._fallback_layer1_overview(path)

    def _fallback_layer1_overview(self, path: Path) -> SolutionOverview:
        """Fallback Layer 1 analysis without agent."""
        overview = SolutionOverview()

        # Count subdirectories
        try:
            subdirs = [d.name for d in path.iterdir() if d.is_dir() and not d.name.startswith(".")]
            overview.domains = subdirs[:10]
            overview.root_directories = subdirs
        except Exception:
            pass

        # Estimate size
        try:
            file_count = sum(1 for _ in path.rglob("*") if _.is_file())
            if file_count < 50:
                overview.estimated_size = "small"
            elif file_count < 500:
                overview.estimated_size = "medium"
            elif file_count < 5000:
                overview.estimated_size = "large"
            else:
                overview.estimated_size = "enterprise"
        except Exception:
            pass

        # Detect primary language
        try:
            ext_counts: dict[str, int] = {}
            from core.domain_scanner import EXTENSION_TO_LANGUAGE
            for f in path.rglob("*"):
                if f.is_file():
                    ext = f.suffix.lower()
                    if ext in EXTENSION_TO_LANGUAGE:
                        lang = EXTENSION_TO_LANGUAGE[ext]
                        ext_counts[lang] = ext_counts.get(lang, 0) + 1

            if ext_counts:
                overview.primary_language = max(ext_counts.keys(), key=lambda k: ext_counts[k])
        except Exception:
            pass

        # Detect structure type
        try:
            if any(f.suffix == ".sln" for f in path.glob("*")):
                overview.structure_type = "multi-project"
            elif len(overview.root_directories) > 5:
                overview.structure_type = "monorepo"
            else:
                overview.structure_type = "single"
        except Exception:
            pass

        return overview

    def _scan_layer2_tech_stack(self, path: Path, name: str) -> TechStackInfo:
        """Layer 2: Technology stack detection using agent or fallback."""
        self.console.print("      [dim]Layer 2: Tech Stack...[/dim]")

        # Try to use agent
        if self._has_agent("scout-techstack"):
            try:
                prompt = f"""Analyze the technology stack in: {path}
This is the '{name}' domain/module.
Detect languages, frameworks, tools, and infrastructure.
Remember: Do NOT scan .orchestrator/ folder."""

                result = self.run_agent("scout-techstack", message=prompt, show_progress=False)
                if result.success and result.content:
                    data = self._extract_json(result.content)
                    if data:
                        tech = TechStackInfo(domain=name)
                        # Parse languages
                        for lang in data.get("languages", []):
                            if isinstance(lang, dict):
                                tech.languages.append(TechInfo(
                                    name=lang.get("name", ""),
                                    confidence=lang.get("confidence", 0.5),
                                    version=lang.get("version"),
                                ))
                            elif isinstance(lang, str):
                                tech.languages.append(TechInfo(name=lang, confidence=0.7))
                        # Parse frameworks
                        for fw in data.get("frameworks", []):
                            if isinstance(fw, dict):
                                tech.frameworks.append(TechInfo(
                                    name=fw.get("name", ""),
                                    confidence=fw.get("confidence", 0.5),
                                    version=fw.get("version"),
                                    entry_point=fw.get("entry_point"),
                                ))
                            elif isinstance(fw, str):
                                tech.frameworks.append(TechInfo(name=fw, confidence=0.7))
                        # Parse tools
                        for tool in data.get("tools", []):
                            if isinstance(tool, dict):
                                tech.tools.append(TechInfo(
                                    name=tool.get("name", ""),
                                    confidence=tool.get("confidence", 0.5),
                                    config_file=tool.get("config_file"),
                                ))
                            elif isinstance(tool, str):
                                tech.tools.append(TechInfo(name=tool, confidence=0.7))
                        tech.build_system = data.get("build_system", "")
                        tech.package_manager = data.get("package_manager", "")
                        tech.test_framework = data.get("test_framework", "")
                        return tech
            except Exception as e:
                self.console.print(f"      [yellow]Agent failed, using fallback: {e}[/yellow]")

        # Fallback: simple analysis
        return self._fallback_layer2_tech_stack(path, name)

    def _fallback_layer2_tech_stack(self, path: Path, name: str) -> TechStackInfo:
        """Fallback Layer 2 analysis without agent."""
        tech = TechStackInfo(domain=name)

        # Detect from config files
        config_detectors = [
            ("package.json", self._parse_package_json),
            ("pyproject.toml", self._parse_pyproject),
            ("go.mod", self._parse_go_mod),
            ("Cargo.toml", self._parse_cargo),
        ]

        for config_file, parser in config_detectors:
            config_path = path / config_file
            if config_path.exists():
                try:
                    parser(config_path, tech)
                except Exception:
                    pass

        # Also check for .csproj files
        csproj_files = list(path.glob("**/*.csproj"))
        if csproj_files:
            tech.languages.append(TechInfo(name="csharp", confidence=0.95))
            tech.build_system = "dotnet"

        return tech

    def _parse_package_json(self, path: Path, tech: TechStackInfo):
        """Parse package.json for Node.js projects."""
        data = json.loads(path.read_text())

        tech.languages.append(TechInfo(name="javascript", confidence=0.9))
        tech.package_manager = "npm"

        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}

        # Detect frameworks
        framework_patterns = {
            "react": "React",
            "vue": "Vue",
            "angular": "Angular",
            "express": "Express",
            "fastify": "Fastify",
            "next": "Next.js",
            "nuxt": "Nuxt",
        }

        for pkg, name in framework_patterns.items():
            if any(pkg in d.lower() for d in deps):
                tech.frameworks.append(TechInfo(name=name, confidence=0.85))

        # Detect TypeScript
        if "typescript" in deps:
            tech.languages.append(TechInfo(name="typescript", confidence=0.9))

    def _parse_pyproject(self, path: Path, tech: TechStackInfo):
        """Parse pyproject.toml for Python projects."""
        import tomllib
        data = tomllib.loads(path.read_text())

        tech.languages.append(TechInfo(name="python", confidence=0.95))
        tech.package_manager = "pip"

        deps = data.get("project", {}).get("dependencies", [])
        if isinstance(deps, list):
            dep_str = " ".join(deps)

            framework_patterns = {
                "fastapi": "FastAPI",
                "django": "Django",
                "flask": "Flask",
                "pytest": None,  # Test framework
            }

            for pkg, name in framework_patterns.items():
                if pkg in dep_str.lower():
                    if name:
                        tech.frameworks.append(TechInfo(name=name, confidence=0.85))
                    elif pkg == "pytest":
                        tech.test_framework = "pytest"

    def _parse_go_mod(self, path: Path, tech: TechStackInfo):
        """Parse go.mod for Go projects."""
        tech.languages.append(TechInfo(name="go", confidence=0.95))
        tech.build_system = "go"

    def _parse_cargo(self, path: Path, tech: TechStackInfo):
        """Parse Cargo.toml for Rust projects."""
        tech.languages.append(TechInfo(name="rust", confidence=0.95))
        tech.build_system = "cargo"

    def _scan_layer3_domain_details(self, path: Path, name: str) -> DomainDetails:
        """Layer 3: Domain responsibilities and boundaries using agent or fallback."""
        self.console.print("      [dim]Layer 3: Domain Details...[/dim]")

        # Try to use agent
        if self._has_agent("scout-domain"):
            try:
                prompt = f"""Analyze the domain details for: {path}
This is the '{name}' domain/module.
Discover responsibilities, boundaries, dependencies, and key files.
Remember: Do NOT scan .orchestrator/ folder."""

                result = self.run_agent("scout-domain", message=prompt, show_progress=False)
                if result.success and result.content:
                    data = self._extract_json(result.content)
                    if data:
                        details = DomainDetails(name=name)
                        details.responsibilities = data.get("responsibilities", [])
                        details.boundaries = data.get("boundaries", [])
                        details.key_files = data.get("key_files", [])
                        details.entry_points = data.get("entry_points", [])
                        details.public_apis = [
                            f"{api.get('method', '')} {api.get('path', '')}"
                            for api in data.get("public_apis", [])
                            if isinstance(api, dict)
                        ]
                        # Parse dependencies
                        deps = data.get("dependencies", {})
                        if isinstance(deps, dict):
                            details.dependencies = (
                                deps.get("internal", []) +
                                deps.get("external", []) +
                                deps.get("third_party", [])
                            )
                        elif isinstance(deps, list):
                            details.dependencies = deps
                        return details
            except Exception as e:
                self.console.print(f"      [yellow]Agent failed, using fallback: {e}[/yellow]")

        # Fallback: simple analysis
        return self._fallback_layer3_domain_details(path, name)

    def _fallback_layer3_domain_details(self, path: Path, name: str) -> DomainDetails:
        """Fallback Layer 3 analysis without agent."""
        details = DomainDetails(name=name)

        # Find key files
        key_patterns = ["main.*", "app.*", "index.*", "startup.*", "program.*"]
        for pattern in key_patterns:
            for f in path.glob(f"**/{pattern}"):
                if f.is_file():
                    details.key_files.append(str(f.relative_to(path)))

        # Find entry points
        entry_patterns = ["main.py", "main.go", "main.rs", "index.ts", "index.js", "Program.cs"]
        for pattern in entry_patterns:
            for f in path.glob(f"**/{pattern}"):
                details.entry_points.append(str(f.relative_to(path)))

        details.dependencies = []
        return details

    def _scan_layer4_deep_technical(self, path: Path, name: str) -> DeepTechnicalInfo:
        """Layer 4: Deep patterns, risks, rules using agent or fallback."""
        self.console.print("      [dim]Layer 4: Deep Technical...[/dim]")

        # Try to use agent
        if self._has_agent("scout-deep"):
            try:
                prompt = f"""Perform deep technical analysis of: {path}
This is the '{name}' domain/module.
Extract patterns, conventions, risks, rules, and constraints.
Be thorough - read actual code files.
Remember: Do NOT scan .orchestrator/ folder."""

                result = self.run_agent("scout-deep", message=prompt, show_progress=False)
                if result.success and result.content:
                    data = self._extract_json(result.content)
                    if data:
                        deep = DeepTechnicalInfo(domain=name)
                        # Parse patterns
                        for p in data.get("patterns", []):
                            if isinstance(p, dict):
                                deep.patterns.append(p.get("name", str(p)))
                            else:
                                deep.patterns.append(str(p))
                        # Parse conventions
                        for c in data.get("conventions", []):
                            if isinstance(c, dict):
                                deep.conventions.append(c.get("convention", str(c)))
                            else:
                                deep.conventions.append(str(c))
                        # Parse risks
                        for r in data.get("risks", []):
                            if isinstance(r, dict):
                                deep.risks.append(RiskInfo(
                                    category=r.get("category", ""),
                                    description=r.get("description", ""),
                                    severity=r.get("severity", "low"),
                                    location=r.get("location", ""),
                                    recommendation=r.get("recommendation", ""),
                                ))
                        # Parse rules
                        for rule in data.get("rules", []):
                            if isinstance(rule, dict):
                                deep.rules.append(RuleInfo(
                                    name=rule.get("name", ""),
                                    description=rule.get("description", ""),
                                    scope=rule.get("scope", "global"),
                                    examples=rule.get("examples", []),
                                    rationale=rule.get("rationale", ""),
                                ))
                        deep.constraints = data.get("constraints", [])
                        if isinstance(deep.constraints, list) and deep.constraints:
                            if isinstance(deep.constraints[0], dict):
                                deep.constraints = [c.get("constraint", str(c)) for c in deep.constraints]
                        deep.assumptions = data.get("assumptions", [])
                        deep.gaps = [
                            g.get("description", str(g)) if isinstance(g, dict) else str(g)
                            for g in data.get("gaps", [])
                        ]
                        return deep
            except Exception as e:
                self.console.print(f"      [yellow]Agent failed, using fallback: {e}[/yellow]")

        # Fallback: empty deep analysis
        return self._fallback_layer4_deep_technical(path, name)

    def _fallback_layer4_deep_technical(self, path: Path, name: str) -> DeepTechnicalInfo:
        """Fallback Layer 4 - returns minimal structure."""
        deep = DeepTechnicalInfo(domain=name)
        deep.patterns = []
        deep.conventions = []
        deep.constraints = []
        return deep

    # --- Phase 5: Synthesis ---

    def _phase5_synthesis(self):
        """Synthesize knowledge and generate experts."""
        # Save session
        session_file = self.output_dir / "session.json"
        self._save_session(session_file)

        # Generate experts based on detected technologies
        self._generate_experts()

        # Extract rules
        self._extract_rules()

    def _save_session(self, path: Path):
        """Save session to JSON file."""
        # Convert to dict for JSON serialization
        data = {
            "session_id": self.session.session_id,
            "started_at": self.session.started_at,
            "completed_at": self.session.completed_at,
            "status": self.session.status,
            "criteria": {
                "focus": self.session.criteria.focus,
                "areas": self.session.criteria.areas,
                "depth": self.session.criteria.depth,
            } if self.session.criteria else None,
            "domains_scanned": len(self.session.approved_domains),
            "knowledge": {
                name: {
                    "domain": k.domain,
                    "scan_depth_reached": k.scan_depth_reached,
                    "last_scanned": k.last_scanned,
                    "overview": {
                        "purpose": k.overview.purpose if k.overview else "",
                        "estimated_size": k.overview.estimated_size if k.overview else "",
                        "structure_type": k.overview.structure_type if k.overview else "",
                        "primary_language": k.overview.primary_language if k.overview else "",
                    } if k.overview else None,
                    "tech_stack": {
                        "languages": [t.name for t in k.tech_stack.languages] if k.tech_stack else [],
                        "frameworks": [t.name for t in k.tech_stack.frameworks] if k.tech_stack else [],
                    } if k.tech_stack else None,
                }
                for name, k in self.session.knowledge.items()
            },
            "experts_generated": self.session.experts_generated,
        }

        path.write_text(json.dumps(data, indent=2))

    def _generate_experts(self):
        """Generate expert agents based on discovered technologies."""
        from core.symbols import SPARKLES

        # Collect all unique technologies
        all_langs = set()
        all_frameworks = set()

        for knowledge in self.session.knowledge.values():
            if knowledge.tech_stack:
                all_langs.update(t.name for t in knowledge.tech_stack.languages)
                all_frameworks.update(t.name for t in knowledge.tech_stack.frameworks)

        # Check existing experts
        experts_dir = self.project_root / ".orchestrator" / "agents" / "experts"
        existing = set()
        if experts_dir.exists():
            existing = {f.stem.lower() for f in experts_dir.glob("*.md")}

        # Generate missing experts
        try:
            from core.expert_loader import ExpertLoader, ExpertType

            loader = ExpertLoader(self.project_root)

            for tech in all_langs | all_frameworks:
                tech_lower = tech.lower().replace(".", "-")
                if tech_lower not in existing:
                    self.console.print(f"  [dim]{SPARKLES} Creating expert: {tech}[/dim]")
                    if loader.create_expert(tech, expert_type=ExpertType.TECH):
                        self.session.experts_generated.append(tech)
                        existing.add(tech_lower)

        except Exception as e:
            self.console.print(f"  [yellow]Warning: Expert generation failed: {e}[/yellow]")

    def _extract_rules(self):
        """Extract coding rules from discovered patterns."""
        # Simplified - would use deep technical layer data
        self.session.rules_extracted = []

    def _print_summary(self):
        """Print final summary."""
        self.console.print("\n" + "=" * 50)
        self.console.print("[bold]Summary[/bold]")
        self.console.print("=" * 50)

        self.console.print(f"  Session ID: {self.session.session_id}")
        self.console.print(f"  Domains scanned: {len(self.session.approved_domains)}")

        if self.session.knowledge:
            self.console.print("\n  Knowledge acquired:")
            for name, k in self.session.knowledge.items():
                langs = []
                if k.tech_stack:
                    langs = [t.name for t in k.tech_stack.languages]
                lang_str = f" [{', '.join(langs)}]" if langs else ""
                self.console.print(f"    - {name}{lang_str} (depth: {k.scan_depth_reached})")

        if self.session.experts_generated:
            self.console.print(f"\n  Experts generated: {', '.join(self.session.experts_generated)}")


def run(args=None) -> int:
    """Run smart scouting from CLI."""
    import argparse

    parser = argparse.ArgumentParser(description="Smart Scout - Multi-phase codebase analysis")
    parser.add_argument(
        "--non-interactive", "-n",
        action="store_true",
        help="Run without user prompts (use defaults)"
    )
    parser.add_argument(
        "--depth",
        choices=["quick", "standard", "deep"],
        default="standard",
        help="Scan depth (default: standard)"
    )
    parser.add_argument(
        "--focus",
        choices=["overview", "domains", "audit", "architecture"],
        default="overview",
        help="Scan focus (default: overview)"
    )

    parsed = parser.parse_args(args or [])

    # Determine project root (multi-project mode vs single-project mode)
    from config import get_config
    config = get_config()

    project_id = None
    project_slug = None

    if config.is_multi_project_mode:
        from db.repositories.project import get_project_repository
        repo = get_project_repository()
        active = repo.get_active(as_dict=True)
        if not active:
            print("Error: No active project. Use 'orch project switch <name>' first.")
            return 1
        project_root = Path(active['path'])
        project_id = active['id']
        project_slug = active['slug']
        print(f"Project: {active['name']} ({active['slug']})")
    else:
        project_root = Path(__file__).parent.parent.parent

    criteria = None
    if parsed.non_interactive:
        criteria = ScanCriteria(
            focus=parsed.focus,
            areas=["backend", "frontend"],
            depth=parsed.depth,
        )

    workflow = SmartScoutingWorkflow(
        project_root=project_root,
        interactive=not parsed.non_interactive,
        criteria=criteria,
    )

    # Set project context for multi-project mode
    if project_id:
        workflow._project_id = project_id
        workflow._project_slug = project_slug

    result = workflow.run()
    return 0 if result.success else 1


if __name__ == "__main__":
    import sys
    sys.exit(run(sys.argv[1:]))
