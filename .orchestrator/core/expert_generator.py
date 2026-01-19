"""
Expert Generator: Auto-generates experts from codebase knowledge.

Generates three types of experts:
1. TECH experts - For detected languages and frameworks
2. DOMAIN experts - For discovered business domains
3. STRUCTURE expert - Single expert for architecture knowledge

Uses the meta-expert for generation and knowledge store for context.
"""
import logging
from pathlib import Path
from typing import Optional

from .knowledge_store import KnowledgeStore, CodebaseKnowledge
from .expert_loader import ExpertLoader, ExpertType

logger = logging.getLogger(__name__)


class ExpertGenerator:
    """
    Auto-generates expert agents based on codebase knowledge.

    Usage:
        generator = ExpertGenerator(project_root)

        # Generate all missing experts
        generated = generator.generate_all()

        # Generate structure expert
        generator.generate_structure_expert()

        # Generate domain experts
        generator.generate_domain_experts()
    """

    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()
        self.knowledge_store = KnowledgeStore(project_root)
        self.expert_loader = ExpertLoader(project_root)
        self.experts_dir = project_root / ".orchestrator" / "agents" / "experts"

    def generate_all(self, force: bool = False) -> list[str]:
        """
        Generate all missing experts based on knowledge.

        Args:
            force: Regenerate even if experts exist

        Returns:
            List of generated expert names
        """
        generated = []

        knowledge = self.knowledge_store.load()
        if not knowledge:
            logger.warning("No codebase knowledge found. Run scout first.")
            return []

        # Get existing experts
        existing = set(e.name.lower() for e in self.expert_loader.discover_experts())

        # Generate tech experts
        tech_experts = self._generate_tech_experts(knowledge, existing, force)
        generated.extend(tech_experts)

        # Generate domain experts
        domain_experts = self._generate_domain_experts(knowledge, existing, force)
        generated.extend(domain_experts)

        # Generate structure expert
        if force or "structure" not in existing:
            if self.generate_structure_expert(knowledge):
                generated.append("structure")

        return generated

    def _generate_tech_experts(
        self,
        knowledge: CodebaseKnowledge,
        existing: set[str],
        force: bool = False
    ) -> list[str]:
        """Generate experts for detected technologies."""
        generated = []

        # Combine languages and frameworks
        techs = (
            [(t.name, "language") for t in knowledge.technologies.languages] +
            [(t.name, "framework") for t in knowledge.technologies.frameworks]
        )

        for tech_name, category in techs:
            if not force and tech_name.lower() in existing:
                continue

            # Find relevant context
            tech_info = None
            for t in knowledge.technologies.languages + knowledge.technologies.frameworks:
                if t.name.lower() == tech_name.lower():
                    tech_info = t
                    break

            focus = f"{category} best practices"
            if tech_info and tech_info.entry_point:
                focus = f"{category} patterns as used in {tech_info.entry_point}"

            if self.expert_loader.create_expert(
                name=tech_name.lower(),
                expert_type=ExpertType.TECH,
                based_on=tech_name,
                focus=focus,
                use_ultra_think=True,
            ):
                generated.append(tech_name.lower())
                logger.info(f"Generated tech expert: {tech_name}")

        return generated

    def _generate_domain_experts(
        self,
        knowledge: CodebaseKnowledge,
        existing: set[str],
        force: bool = False
    ) -> list[str]:
        """Generate experts for discovered domains."""
        generated = []

        for domain in knowledge.domains:
            expert_name = domain.name.lower()

            # Check both "auth" and "auth-domain" forms
            if not force and (expert_name in existing or f"{expert_name}-domain" in existing):
                continue

            if self.expert_loader.create_expert(
                name=expert_name,
                expert_type=ExpertType.DOMAIN,
                domain_keywords=domain.keywords,
                focus=f"Domain-specific patterns for {domain.name}",
                use_ultra_think=True,
            ):
                generated.append(expert_name)
                logger.info(f"Generated domain expert: {expert_name}")

        return generated

    def generate_structure_expert(
        self,
        knowledge: Optional[CodebaseKnowledge] = None
    ) -> bool:
        """
        Generate or update the structure expert.

        The structure expert understands the project's architecture,
        module organization, and conventions.

        Args:
            knowledge: Optional pre-loaded knowledge

        Returns:
            True if expert was generated successfully
        """
        if knowledge is None:
            knowledge = self.knowledge_store.load()

        if not knowledge:
            logger.warning("No knowledge available for structure expert")
            return False

        # Build comprehensive structure content
        content = self._build_structure_expert_content(knowledge)

        # Write directly (don't use meta-expert for this one)
        expert_file = self.experts_dir / "structure.md"

        try:
            expert_file.write_text(content, encoding="utf-8")
            logger.info("Generated structure expert")
            return True
        except Exception as e:
            logger.error(f"Failed to write structure expert: {e}")
            return False

    def _build_structure_expert_content(self, knowledge: CodebaseKnowledge) -> str:
        """Build the structure expert markdown content."""
        sections = []

        # Frontmatter
        sections.append("""---
name: structure
description: Expert in this project's architecture, modules, and conventions
expert_type: domain
domain_keywords: [architecture, structure, module, refactor, organize, layout]
---

# Structure Expert

You deeply understand this project's architecture and can guide where new code should go.""")

        # Project overview
        if knowledge.project.name:
            sections.append(f"""
## Project Overview

- **Name**: {knowledge.project.name}
- **Type**: {knowledge.project.type}
- **Primary Language**: {knowledge.project.primary_language}""")

        # Architecture
        if knowledge.architecture.pattern != "unknown":
            arch_section = f"""
## Architecture

**Pattern**: {knowledge.architecture.pattern}
"""
            if knowledge.architecture.entry_points:
                entry_points = ", ".join(knowledge.architecture.entry_points)
                arch_section += f"\n**Entry Points**: {entry_points}\n"

            if knowledge.architecture.modules:
                arch_section += "\n### Modules\n"
                for m in knowledge.architecture.modules:
                    deps = f" (depends on: {', '.join(m.depends_on)})" if m.depends_on else ""
                    arch_section += f"- `{m.path}` - {m.purpose}{deps}\n"

            sections.append(arch_section)

        # Where things go
        if knowledge.patterns.structure:
            where_section = "\n## Where Things Go\n"
            for key, path in knowledge.patterns.structure.items():
                label = key.replace("_in", "").replace("_", " ").title()
                where_section += f"- {label}: `{path}`\n"
            sections.append(where_section)

        # Conventions
        if knowledge.patterns.conventions:
            conv_section = "\n## Conventions\n"
            for conv in knowledge.patterns.conventions:
                conv_section += f"- {conv}\n"
            sections.append(conv_section)

        # Naming patterns
        if knowledge.patterns.naming:
            naming_section = "\n## Naming Conventions\n"
            for what, style in knowledge.patterns.naming.items():
                naming_section += f"- {what.title()}: {style}\n"
            sections.append(naming_section)

        # Planning guidance
        sections.append("""
## Planning Guidance

When planning new features:
1. **Check existing patterns** - Look at similar modules first
2. **Follow the architecture** - Put code in the right layer
3. **Match conventions** - Use established naming and structure
4. **Consider dependencies** - Understand module relationships

When suggesting file locations:
- Routes/API handlers: Check `routes_in` path
- Business logic: Check `services_in` path
- Data models: Check `models_in` path
- Tests: Mirror source structure in test directory""")

        return "\n".join(sections)

    def refresh_structure_expert(self) -> bool:
        """
        Refresh the structure expert with latest knowledge.

        Call this after a new scout scan to update the structure expert.
        """
        return self.generate_structure_expert()

    def get_generation_report(self) -> dict:
        """
        Get a report of what experts could be generated.

        Returns dict with:
        - existing: List of existing expert names
        - missing_tech: List of technologies without experts
        - missing_domain: List of domains without experts
        - has_structure: Whether structure expert exists
        """
        knowledge = self.knowledge_store.load()
        existing = [e.name for e in self.expert_loader.discover_experts()]
        existing_lower = set(e.lower() for e in existing)

        report = {
            "existing": existing,
            "missing_tech": [],
            "missing_domain": [],
            "has_structure": "structure" in existing_lower,
        }

        if knowledge:
            # Check tech
            for t in knowledge.technologies.languages + knowledge.technologies.frameworks:
                if t.name.lower() not in existing_lower:
                    report["missing_tech"].append(t.name)

            # Check domains
            for d in knowledge.domains:
                if d.name.lower() not in existing_lower and f"{d.name.lower()}-domain" not in existing_lower:
                    report["missing_domain"].append(d.name)

        return report
