"""
Expert Loader: Manages tech-specific, domain, and module expert agents.

Loads experts from .orchestrator/agents/experts/ directory:
- Discovers available experts (tech, domain, module types)
- Matches experts to detected tech stack
- Can trigger meta-expert to create new experts
- Provides domain experts for planning workflow consultation
"""
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from rich.console import Console

from .agent import Agent


class ExpertType(Enum):
    """Type of expert agent."""
    TECH = "tech"       # Languages, frameworks, tools (existing)
    DOMAIN = "domain"   # Business domains: auth, payments, inventory, etc.
    MODULE = "module"   # Project-specific modules


@dataclass
class ExpertInfo:
    """Information about an expert agent."""
    name: str
    description: str
    file_path: Path
    category: str = "general"  # language, framework, tool, general (for TECH type)
    expert_type: ExpertType = ExpertType.TECH
    module_path: Optional[str] = None  # For MODULE type: path to source
    domain_keywords: list[str] = field(default_factory=list)  # Keywords for matching


class ExpertLoader:
    """
    Manages tech-specific, domain, and module expert agents.

    Multi-Project Support:
        In multi-project mode, experts are loaded in priority order:
        1. Project-specific experts: $SDLC_ORCHESTRATOR_HOME/projects/{slug}/experts/
        2. Shared experts: {project_root}/.orchestrator/agents/experts/
        3. Built-in experts: {orchestrator_dir}/agents/experts/

    Usage:
        loader = ExpertLoader(project_root)

        # Tech experts (for code review)
        experts = loader.get_experts_for_stack(["python", "fastapi", "react"])

        # Domain experts (for planning)
        domain_experts = loader.get_all_domain_experts()

        # Find missing experts
        gaps = loader.find_missing_experts()

        # Create new experts
        loader.create_expert("auth", expert_type=ExpertType.DOMAIN,
                            domain_keywords=["auth", "login", "jwt"])
    """

    def __init__(self, project_root: Path, project_slug: str = None):
        self.project_root = project_root
        self.project_slug = project_slug
        self.console = Console()

        # Primary experts directory (local to project)
        self.experts_dir = project_root / ".orchestrator" / "agents" / "experts"

        # Additional experts directories (for multi-project mode)
        self._project_experts_dir = None
        self._shared_experts_dir = None

        # Try to get project-specific paths from orchestrator home
        self._init_multi_project_paths()

        # Ensure primary directory exists
        self.experts_dir.mkdir(parents=True, exist_ok=True)

    def _init_multi_project_paths(self):
        """Initialize paths for multi-project mode."""
        try:
            from config import get_config

            config = get_config()
            if not config.is_multi_project_mode:
                return

            # Get project slug from context if not provided
            slug = self.project_slug
            if not slug:
                from db.project_context import get_optional_project_id
                # We need the slug, not ID, so try to get from database
                project_id = get_optional_project_id()
                if project_id:
                    try:
                        from db.repositories.project import get_project_repository
                        repo = get_project_repository()
                        project = repo.get_by_id(project_id)
                        if project:
                            slug = project.slug
                    except Exception:
                        pass

            if slug and config.orchestrator_home.projects_dir:
                self._project_experts_dir = config.orchestrator_home.projects_dir / slug / "experts"
                self._project_experts_dir.mkdir(parents=True, exist_ok=True)

            # Shared experts from orchestrator home
            if config.orchestrator_home.home_path:
                self._shared_experts_dir = config.orchestrator_home.home_path / "agents" / "experts"
                if self._shared_experts_dir.exists():
                    pass  # Use it
                else:
                    self._shared_experts_dir = None

        except Exception:
            pass  # Fall back to single-project mode

    def _get_all_expert_dirs(self) -> list[Path]:
        """Get all expert directories in priority order."""
        dirs = []

        # 1. Project-specific (highest priority)
        if self._project_experts_dir and self._project_experts_dir.exists():
            dirs.append(self._project_experts_dir)

        # 2. Local project directory
        if self.experts_dir.exists():
            dirs.append(self.experts_dir)

        # 3. Shared experts from orchestrator home
        if self._shared_experts_dir and self._shared_experts_dir.exists():
            dirs.append(self._shared_experts_dir)

        return dirs

    def discover_experts(self) -> list[ExpertInfo]:
        """
        Discover all available expert agents.

        In multi-project mode, searches:
        1. Project-specific experts (highest priority)
        2. Local project experts
        3. Shared experts (lowest priority)

        Experts with the same name are not duplicated (first found wins).
        """
        experts = []
        seen_names = set()

        # Search all directories in priority order
        for experts_dir in self._get_all_expert_dirs():
            for file_path in experts_dir.glob("*.md"):
                if file_path.name.startswith("_"):
                    continue  # Skip meta files

                # Skip if already found with this name
                if file_path.stem in seen_names:
                    continue

                try:
                    content = file_path.read_text(encoding="utf-8")

                    # Parse frontmatter
                    name = file_path.stem
                    description = ""
                    expert_type = ExpertType.TECH
                    module_path = None
                    domain_keywords = []

                    if content.startswith("---"):
                        parts = content.split("---", 2)
                        if len(parts) >= 3:
                            frontmatter = parts[1]
                            for line in frontmatter.split("\n"):
                                line = line.strip()
                                if line.startswith("name:"):
                                    name = line.split(":", 1)[1].strip()
                                elif line.startswith("description:"):
                                    description = line.split(":", 1)[1].strip()
                                elif line.startswith("expert_type:"):
                                    type_str = line.split(":", 1)[1].strip()
                                    if type_str in [e.value for e in ExpertType]:
                                        expert_type = ExpertType(type_str)
                                elif line.startswith("module_path:"):
                                    module_path = line.split(":", 1)[1].strip()
                                elif line.startswith("domain_keywords:"):
                                    # Parse YAML-style list: [auth, login, jwt]
                                    kw_str = line.split(":", 1)[1].strip()
                                    if kw_str.startswith("[") and kw_str.endswith("]"):
                                        domain_keywords = [k.strip() for k in kw_str[1:-1].split(",")]

                    # Determine category (for TECH type)
                    category = self._categorize_expert(name, content)

                    experts.append(ExpertInfo(
                        name=name,
                        description=description,
                        file_path=file_path,
                        category=category,
                        expert_type=expert_type,
                        module_path=module_path,
                        domain_keywords=domain_keywords
                    ))
                    seen_names.add(file_path.stem)

                except Exception as e:
                    self.console.print(f"[yellow]Warning: Could not load expert {file_path.name}: {e}[/yellow]")

        return experts

    def _categorize_expert(self, name: str, content: str) -> str:
        """Categorize an expert by type (for TECH experts)."""
        languages = ["python", "typescript", "javascript", "go", "rust", "java", "ruby"]
        frameworks = ["react", "vue", "angular", "fastapi", "django", "express", "next"]
        tools = ["docker", "kubernetes", "github-actions", "terraform"]

        name_lower = name.lower()

        if any(lang in name_lower for lang in languages):
            return "language"
        elif any(fw in name_lower for fw in frameworks):
            return "framework"
        elif any(tool in name_lower for tool in tools):
            return "tool"
        else:
            return "general"

    def get_expert(self, name: str) -> Optional[Agent]:
        """Load a specific expert agent."""
        expert_file = self.experts_dir / f"{name}.md"
        if not expert_file.exists():
            return None

        try:
            return Agent.load(f"experts/{name}", self.project_root)
        except FileNotFoundError:
            return None

    def get_experts_for_stack(self, techs: list[str]) -> list[Agent]:
        """
        Get expert agents for a list of technologies.

        Args:
            techs: List of technology names (e.g., ["python", "react"])

        Returns:
            List of loaded expert agents
        """
        available = self.discover_experts()
        matched_experts = []
        missing_techs = []

        for tech in techs:
            tech_lower = tech.lower()
            found = False

            for expert in available:
                # Only match TECH type experts
                if expert.expert_type != ExpertType.TECH:
                    continue

                if (tech_lower == expert.name.lower() or
                    tech_lower in expert.name.lower() or
                    tech_lower in expert.description.lower()):
                    agent = self.get_expert(expert.name)
                    if agent and agent not in matched_experts:
                        matched_experts.append(agent)
                        found = True
                        break

            if not found:
                missing_techs.append(tech)

        if missing_techs:
            self.console.print(f"[yellow]Missing experts for: {', '.join(missing_techs)}[/yellow]")

        return matched_experts

    def get_all_domain_experts(self) -> list[Agent]:
        """
        Get all domain and module experts (for planning workflow).

        Returns:
            List of loaded domain/module expert agents
        """
        experts = self.discover_experts()
        domain_experts = []

        for expert in experts:
            if expert.expert_type in (ExpertType.DOMAIN, ExpertType.MODULE):
                agent = self.get_expert(expert.name)
                if agent:
                    domain_experts.append(agent)

        return domain_experts

    def get_experts_by_type(self, expert_type: ExpertType) -> list[ExpertInfo]:
        """Get all experts of a specific type."""
        return [e for e in self.discover_experts() if e.expert_type == expert_type]

    def list_experts(self) -> dict:
        """List all available experts grouped by type and category."""
        experts = self.discover_experts()

        result = {
            "tech": {
                "language": [],
                "framework": [],
                "tool": [],
                "general": []
            },
            "domain": [],
            "module": []
        }

        for expert in experts:
            if expert.expert_type == ExpertType.TECH:
                result["tech"][expert.category].append({
                    "name": expert.name,
                    "description": expert.description
                })
            elif expert.expert_type == ExpertType.DOMAIN:
                result["domain"].append({
                    "name": expert.name,
                    "description": expert.description,
                    "keywords": expert.domain_keywords
                })
            else:  # MODULE
                result["module"].append({
                    "name": expert.name,
                    "description": expert.description,
                    "module_path": expert.module_path
                })

        return result

    def find_missing_experts(self) -> list[dict]:
        """
        Find technologies without expert coverage.

        Returns:
            List of gaps with name, type, category, confidence
        """
        from .system_explorer import find_missing_experts

        existing_names = [e.name for e in self.discover_experts()]
        return find_missing_experts(self.project_root, existing_names)

    def create_expert(
        self,
        name: str,
        expert_type: ExpertType = ExpertType.TECH,
        based_on: str = "python",
        focus: str = "",
        module_path: Optional[str] = None,
        domain_keywords: Optional[list[str]] = None,
        use_ultra_think: bool = True
    ) -> bool:
        """
        Create a new expert using the meta-expert.

        Args:
            name: Expert name (e.g., "auth-expert", "payments")
            expert_type: TECH, DOMAIN, or MODULE
            based_on: Base technology (for TECH) or source context
            focus: Specific focus area
            module_path: Path to module code (for MODULE type)
            domain_keywords: Keywords for domain matching (for DOMAIN type)
            use_ultra_think: Use deep reasoning mode (default: True)

        Returns:
            True if expert was created successfully
        """
        meta_expert = self.experts_dir / "_meta.md"
        if not meta_expert.exists():
            self.console.print("[red]Meta-expert not found[/red]")
            return False

        # Build context based on expert type
        context_parts = []

        # Add ultra think trigger
        if use_ultra_think:
            context_parts.append("[ULTRA_THINK]")
            context_parts.append("")

        context_parts.append(f"Expert Type: {expert_type.value}")

        if expert_type == ExpertType.TECH:
            context_parts.append(f"Based on: {based_on}")
            context_parts.append(f"Focus: {focus or 'General best practices'}")

        elif expert_type == ExpertType.DOMAIN:
            context_parts.append(f"Domain: {name}")
            context_parts.append(f"Focus: {focus or 'Domain-specific patterns and business logic'}")
            if domain_keywords:
                context_parts.append(f"Keywords: {', '.join(domain_keywords)}")
            # Add code context from project
            code_context = self._gather_domain_code_context(name, domain_keywords or [])
            if code_context:
                context_parts.append(f"\n## Existing Code Patterns\n{code_context}")

        elif expert_type == ExpertType.MODULE:
            context_parts.append(f"Module: {name}")
            if module_path:
                context_parts.append(f"Module Path: {module_path}")
                # Read actual module code
                code_context = self._gather_module_code_context(module_path)
                if code_context:
                    context_parts.append(f"\n## Module Code\n{code_context}")
            context_parts.append(f"Focus: {focus or 'Module-specific patterns and APIs'}")

        # Load docs context
        try:
            from .docs_loader import DocsLoader
            docs_loader = DocsLoader(self.project_root)
            docs = docs_loader.load_docs()
            if docs and docs.docs:
                docs_context = docs.get_context_string(max_chars=6000)
                context_parts.append(f"\n## Project Documentation\n{docs_context}")
        except Exception:
            pass  # Docs loading is optional

        try:
            meta = Agent.load("experts/_meta", self.project_root)

            result = meta.run(
                f"Create a new {expert_type.value} expert agent for: {name}",
                context="\n".join(context_parts)
            )

            if result.success and result.content:
                # Build frontmatter with type info
                frontmatter_lines = [
                    "---",
                    f"name: {name}",
                    f"description: Expert in {name} {'patterns' if expert_type != ExpertType.TECH else 'best practices'}",
                    f"expert_type: {expert_type.value}"
                ]
                if domain_keywords:
                    frontmatter_lines.append(f"domain_keywords: [{', '.join(domain_keywords)}]")
                if module_path:
                    frontmatter_lines.append(f"module_path: {module_path}")
                frontmatter_lines.append("---\n\n")
                frontmatter = "\n".join(frontmatter_lines)

                # Check if result already has frontmatter
                content = result.content
                if content.startswith("---"):
                    # Replace existing frontmatter
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        content = parts[2].strip()

                new_expert_file = self.experts_dir / f"{name}.md"
                new_expert_file.write_text(frontmatter + content, encoding="utf-8")
                self.console.print(f"[green]Created {expert_type.value} expert: {name}[/green]")
                return True

        except Exception as e:
            self.console.print(f"[red]Error creating expert: {e}[/red]")

        return False

    def _gather_domain_code_context(self, domain: str, keywords: list[str]) -> str:
        """Gather code samples related to a domain."""
        if not keywords:
            keywords = [domain]

        samples = []
        total_chars = 0
        max_chars = 8000

        # Search for relevant files
        for ext in [".py", ".ts", ".js"]:
            for file_path in self.project_root.rglob(f"*{ext}"):
                if any(skip in str(file_path) for skip in [".venv", "node_modules", "__pycache__", ".git"]):
                    continue

                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    content_lower = content.lower()

                    # Check if file contains domain keywords
                    if any(kw.lower() in content_lower for kw in keywords):
                        rel_path = file_path.relative_to(self.project_root)
                        sample = f"### {rel_path}\n```{ext[1:]}\n{content[:2000]}\n```"

                        if total_chars + len(sample) > max_chars:
                            break

                        samples.append(sample)
                        total_chars += len(sample)
                except Exception:
                    continue

        return "\n\n".join(samples) if samples else ""

    def _gather_module_code_context(self, module_path: str) -> str:
        """Read code from a specific module path."""
        full_path = self.project_root / module_path

        if not full_path.exists():
            return ""

        samples = []
        total_chars = 0
        max_chars = 12000

        if full_path.is_file():
            files = [full_path]
        else:
            files = list(full_path.rglob("*.py")) + list(full_path.rglob("*.ts")) + list(full_path.rglob("*.js"))

        for file_path in files[:10]:  # Limit files
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                rel_path = file_path.relative_to(self.project_root)
                sample = f"### {rel_path}\n```{file_path.suffix[1:]}\n{content[:3000]}\n```"

                if total_chars + len(sample) > max_chars:
                    break

                samples.append(sample)
                total_chars += len(sample)
            except Exception:
                continue

        return "\n\n".join(samples)

    def get_recommended_experts(self, project_root: Path) -> list[str]:
        """
        Analyze project and recommend experts.

        Uses stack detector patterns to identify needed experts.
        """
        recommendations = []

        # Check for common files
        if (project_root / "package.json").exists():
            recommendations.extend(["typescript", "javascript"])

            # Check for specific frameworks
            try:
                pkg = json.loads((project_root / "package.json").read_text())
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

                if "react" in deps or "next" in deps:
                    recommendations.append("react")
                if "vue" in deps:
                    recommendations.append("vue")
                if "typescript" in deps:
                    recommendations.append("typescript")
            except Exception:
                pass

        if (project_root / "pyproject.toml").exists() or (project_root / "requirements.txt").exists():
            recommendations.append("python")

        if (project_root / "go.mod").exists():
            recommendations.append("go")

        if (project_root / "Cargo.toml").exists():
            recommendations.append("rust")

        return list(set(recommendations))
