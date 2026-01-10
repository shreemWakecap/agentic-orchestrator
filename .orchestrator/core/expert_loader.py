"""
Expert Loader: Manages tech-specific expert agents.

Loads experts from .claude/agents/experts/ directory:
- Discovers available experts
- Matches experts to detected tech stack
- Can trigger meta-expert to create new experts
"""
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from rich.console import Console

from .agent import Agent


@dataclass
class ExpertInfo:
    """Information about an expert agent."""
    name: str
    description: str
    file_path: Path
    category: str = "general"  # language, framework, tool


class ExpertLoader:
    """
    Manages tech-specific expert agents.

    Usage:
        loader = ExpertLoader(project_root)
        experts = loader.get_experts_for_stack(["python", "fastapi", "react"])
    """

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.experts_dir = project_root / ".claude" / "agents" / "experts"
        self.console = Console()

        # Ensure directory exists
        self.experts_dir.mkdir(parents=True, exist_ok=True)

    def discover_experts(self) -> list[ExpertInfo]:
        """Discover all available expert agents."""
        experts = []

        for file_path in self.experts_dir.glob("*.md"):
            if file_path.name.startswith("_"):
                continue  # Skip meta files

            try:
                content = file_path.read_text(encoding="utf-8")

                # Parse frontmatter
                name = file_path.stem
                description = ""

                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        frontmatter = parts[1]
                        for line in frontmatter.split("\n"):
                            if line.startswith("name:"):
                                name = line.split(":", 1)[1].strip()
                            elif line.startswith("description:"):
                                description = line.split(":", 1)[1].strip()

                # Determine category
                category = self._categorize_expert(name, content)

                experts.append(ExpertInfo(
                    name=name,
                    description=description,
                    file_path=file_path,
                    category=category
                ))

            except Exception as e:
                self.console.print(f"[yellow]Warning: Could not load expert {file_path.name}: {e}[/yellow]")

        return experts

    def _categorize_expert(self, name: str, content: str) -> str:
        """Categorize an expert by type."""
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

    def list_experts(self) -> dict:
        """List all available experts grouped by category."""
        experts = self.discover_experts()

        result = {
            "language": [],
            "framework": [],
            "tool": [],
            "general": []
        }

        for expert in experts:
            result[expert.category].append({
                "name": expert.name,
                "description": expert.description
            })

        return result

    def create_expert(self, name: str, based_on: str = "python", focus: str = "") -> bool:
        """
        Create a new expert using the meta-expert.

        This runs the meta-expert to generate a new expert definition.
        """
        meta_expert = self.experts_dir / "_meta.md"
        if not meta_expert.exists():
            self.console.print("[red]Meta-expert not found[/red]")
            return False

        # Load meta-expert and run it to create new expert
        try:
            meta = Agent.load("experts/_meta", self.project_root)

            # Run meta-expert to generate new expert
            result = meta.run(
                f"Create a new expert agent for: {name}",
                context=f"Based on: {based_on}\nFocus: {focus or 'General best practices'}"
            )

            if result.success and result.content:
                # Save new expert
                new_expert_file = self.experts_dir / f"{name}.md"
                new_expert_file.write_text(result.content, encoding="utf-8")
                self.console.print(f"[green]Created expert: {name}[/green]")
                return True

        except Exception as e:
            self.console.print(f"[red]Error creating expert: {e}[/red]")

        return False

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
