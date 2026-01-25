"""
Expert Loader: Manages tech-specific, domain, and module expert agents.

Loads experts from database (single source of truth):
- Discovers available experts (tech, domain, module types)
- Matches experts to detected tech stack
- Provides domain experts for planning workflow consultation
"""
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, List

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
    category: str = "general"  # language, framework, tool, general (for TECH type)
    expert_type: ExpertType = ExpertType.TECH
    module_path: Optional[str] = None  # For MODULE type: path to source
    domain_keywords: list[str] = field(default_factory=list)  # Keywords for matching


class ExpertLoader:
    """
    Manages tech-specific, domain, and module expert agents.

    Loads experts from database (single source of truth).

    Usage:
        loader = ExpertLoader(project_root)

        # Tech experts (for code review)
        experts = loader.get_experts_for_stack(["python", "fastapi", "react"])

        # Domain experts (for planning)
        domain_experts = loader.get_all_domain_experts()

        # Find experts by keywords
        matched = loader.find_by_keywords(["auth", "jwt"])
    """

    def __init__(self, project_root: Path, project_slug: str = None):
        self.project_root = project_root
        self.project_slug = project_slug
        self.console = Console()
        self._repo = None

    @property
    def repo(self):
        """Lazy-load expert repository."""
        if self._repo is None:
            from db.repositories.expert_definition import get_expert_definition_repository
            self._repo = get_expert_definition_repository()
        return self._repo

    def discover_experts(self) -> List[ExpertInfo]:
        """
        Discover all available expert agents from database.

        Returns:
            List of ExpertInfo objects
        """
        experts = []
        db_experts = self.repo.list_all()

        for db_expert in db_experts:
            try:
                expert_type = ExpertType(db_expert.expert_type or "tech")
            except ValueError:
                expert_type = ExpertType.TECH

            experts.append(ExpertInfo(
                name=db_expert.name,
                description=db_expert.description or "",
                category=db_expert.category or "general",
                expert_type=expert_type,
                domain_keywords=json.loads(db_expert.domain_keywords_json or "[]"),
                module_path=db_expert.module_path,
            ))

        return experts

    def get_expert(self, name: str) -> Optional[Agent]:
        """
        Load a specific expert agent from database.

        Args:
            name: Expert name (e.g., "python", "fastapi")

        Returns:
            Agent instance or None if not found
        """
        expert_def = self.repo.get_by_name(name)
        if not expert_def:
            return None

        return Agent(
            name=f"expert-{name}",
            system_prompt=expert_def.system_prompt,
            cwd=self.project_root,
        )

    def get_expert_content(self, name: str) -> Optional[str]:
        """
        Get raw expert system prompt content.

        Args:
            name: Expert name

        Returns:
            System prompt string or None
        """
        expert_def = self.repo.get_by_name(name)
        if not expert_def:
            return None
        return expert_def.system_prompt

    def get_experts_for_stack(self, techs: List[str]) -> List[Agent]:
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

    def get_all_domain_experts(self) -> List[Agent]:
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

    def get_experts_by_type(self, expert_type: ExpertType) -> List[ExpertInfo]:
        """Get all experts of a specific type."""
        db_experts = self.repo.list_by_type(expert_type.value)

        return [
            ExpertInfo(
                name=e.name,
                description=e.description or "",
                category=e.category or "general",
                expert_type=expert_type,
                domain_keywords=json.loads(e.domain_keywords_json or "[]"),
                module_path=e.module_path,
            )
            for e in db_experts
        ]

    def find_by_keywords(self, keywords: List[str]) -> List[ExpertInfo]:
        """
        Find experts matching keywords.

        Args:
            keywords: List of keywords to match

        Returns:
            List of matching ExpertInfo objects
        """
        db_experts = self.repo.find_by_keywords(keywords)

        return [
            ExpertInfo(
                name=e.name,
                description=e.description or "",
                category=e.category or "general",
                expert_type=ExpertType(e.expert_type or "tech"),
                domain_keywords=json.loads(e.domain_keywords_json or "[]"),
                module_path=e.module_path,
            )
            for e in db_experts
        ]

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
                category = expert.category if expert.category in result["tech"] else "general"
                result["tech"][category].append({
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

    def find_missing_experts(self) -> List[dict]:
        """
        Find technologies without expert coverage.

        Returns:
            List of gaps with name, type, category, confidence
        """
        from .system_explorer import find_missing_experts

        existing_names = [e.name for e in self.discover_experts()]
        return find_missing_experts(self.project_root, existing_names)

    def get_recommended_experts(self, project_root: Path) -> List[str]:
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
