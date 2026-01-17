"""
Knowledge Store: Persistent codebase understanding.

Stores codebase knowledge in SQLite database:
- Architecture, domains, patterns
- Expert index for query → Expert mappings
- Scan metadata
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .database import get_knowledge_repository, KnowledgeRepository

logger = logging.getLogger(__name__)


# --- Data Models ---

@dataclass
class TechInfo:
    """Detected technology."""
    name: str
    confidence: float = 0.0
    version: Optional[str] = None
    entry_point: Optional[str] = None
    config_file: Optional[str] = None


@dataclass
class ModuleInfo:
    """Module/package in the architecture."""
    name: str
    path: str
    purpose: str = ""
    depends_on: list[str] = field(default_factory=list)


@dataclass
class DomainInfo:
    """Business domain discovered in codebase."""
    name: str
    keywords: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)
    routes: list[str] = field(default_factory=list)


@dataclass
class PatternInfo:
    """Codebase patterns and conventions."""
    naming: dict[str, str] = field(default_factory=dict)  # files, classes, functions
    structure: dict[str, str] = field(default_factory=dict)  # routes_in, models_in, etc.
    conventions: list[str] = field(default_factory=list)


@dataclass
class ArchitectureInfo:
    """Architecture overview."""
    pattern: str = "unknown"  # layered, hexagonal, mvc, etc.
    modules: list[ModuleInfo] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)


@dataclass
class ProjectInfo:
    """Project metadata."""
    name: str = ""
    type: str = "unknown"  # web_api, cli, library, monorepo
    primary_language: str = ""


@dataclass
class TechnologiesInfo:
    """All detected technologies."""
    languages: list[TechInfo] = field(default_factory=list)
    frameworks: list[TechInfo] = field(default_factory=list)
    tools: list[TechInfo] = field(default_factory=list)


@dataclass
class CodebaseKnowledge:
    """Complete codebase knowledge."""
    version: str = "1.0"
    last_updated: str = ""
    project: ProjectInfo = field(default_factory=ProjectInfo)
    technologies: TechnologiesInfo = field(default_factory=TechnologiesInfo)
    architecture: ArchitectureInfo = field(default_factory=ArchitectureInfo)
    domains: list[DomainInfo] = field(default_factory=list)
    patterns: PatternInfo = field(default_factory=PatternInfo)
    statistics: dict = field(default_factory=dict)


@dataclass
class ExpertTriggers:
    """Triggers for expert selection."""
    keywords: list[str] = field(default_factory=list)
    paths: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)


@dataclass
class ExpertIndexEntry:
    """Entry in the expert index."""
    name: str
    type: str  # tech, domain, module
    file: str
    triggers: ExpertTriggers = field(default_factory=ExpertTriggers)
    weight: float = 1.0


@dataclass
class ExpertIndex:
    """Expert index for intelligent selection."""
    version: str = "1.0"
    last_updated: str = ""
    experts: list[ExpertIndexEntry] = field(default_factory=list)
    keyword_map: dict[str, list[str]] = field(default_factory=dict)
    path_map: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class ScanMeta:
    """Metadata about the last scan."""
    scan_id: str = ""
    started_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0
    files_scanned: int = 0
    scan_type: str = "full"  # full, quick
    trigger: str = "manual"  # manual, auto
    experts_generated: list[str] = field(default_factory=list)


# --- Knowledge Store ---

class KnowledgeStore:
    """
    Manages persistent codebase knowledge in SQLite database.

    Usage:
        store = KnowledgeStore(project_root)

        # Check if knowledge exists
        if store.exists():
            knowledge = store.load()

        # Save knowledge
        store.save(knowledge)

        # Get planning context
        context = store.get_planning_context()
    """

    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()
        self._repo = get_knowledge_repository(project_root)

    def exists(self) -> bool:
        """Check if codebase knowledge exists."""
        return self._repo.exists()

    def has_index(self) -> bool:
        """Check if expert index exists."""
        return self._repo.has_expert_index()

    # --- Codebase Knowledge ---

    def load(self) -> Optional[CodebaseKnowledge]:
        """Load codebase knowledge from database."""
        data = self._repo.load_knowledge()
        if not data:
            return None

        try:
            return self._dict_to_knowledge(data)
        except Exception as e:
            logger.warning(f"Error loading knowledge: {e}")
            return None

    def save(self, knowledge: CodebaseKnowledge) -> bool:
        """Save codebase knowledge to database."""
        try:
            knowledge.last_updated = datetime.now().isoformat()

            # Convert to flat structure for repository
            languages = [self._tech_to_dict(t) for t in knowledge.technologies.languages]
            frameworks = [self._tech_to_dict(t) for t in knowledge.technologies.frameworks]
            tools = [self._tech_to_dict(t) for t in knowledge.technologies.tools]
            modules = [
                {
                    "name": m.name,
                    "path": m.path,
                    "purpose": m.purpose,
                    "depends_on": m.depends_on,
                }
                for m in knowledge.architecture.modules
            ]
            domains = [
                {
                    "name": d.name,
                    "keywords": d.keywords,
                    "files": d.files,
                    "models": d.models,
                    "routes": d.routes,
                }
                for d in knowledge.domains
            ]

            self._repo.save_knowledge(
                project_name=knowledge.project.name,
                project_type=knowledge.project.type,
                primary_language=knowledge.project.primary_language,
                languages=languages,
                frameworks=frameworks,
                tools=tools,
                architecture_pattern=knowledge.architecture.pattern,
                modules=modules,
                entry_points=knowledge.architecture.entry_points,
                domains=domains,
                naming=knowledge.patterns.naming,
                structure=knowledge.patterns.structure,
                conventions=knowledge.patterns.conventions,
                statistics=knowledge.statistics,
                version=knowledge.version
            )
            return True
        except Exception as e:
            logger.error(f"Error saving knowledge: {e}")
            return False

    def _tech_to_dict(self, t: TechInfo) -> dict:
        """Convert TechInfo to dict."""
        d = {"name": t.name, "confidence": t.confidence}
        if t.version:
            d["version"] = t.version
        if t.entry_point:
            d["entry_point"] = t.entry_point
        if t.config_file:
            d["config_file"] = t.config_file
        return d

    def _dict_to_knowledge(self, data: dict) -> CodebaseKnowledge:
        """Convert dict to CodebaseKnowledge."""
        project_data = data.get("project", {})
        tech_data = data.get("technologies", {})
        arch_data = data.get("architecture", {})
        pattern_data = data.get("patterns", {})

        return CodebaseKnowledge(
            version=data.get("version", "1.0"),
            last_updated=data.get("last_updated", ""),
            project=ProjectInfo(
                name=project_data.get("name", ""),
                type=project_data.get("type", "unknown"),
                primary_language=project_data.get("primary_language", ""),
            ),
            technologies=TechnologiesInfo(
                languages=[self._dict_to_tech(t) for t in tech_data.get("languages", [])],
                frameworks=[self._dict_to_tech(t) for t in tech_data.get("frameworks", [])],
                tools=[self._dict_to_tech(t) for t in tech_data.get("tools", [])],
            ),
            architecture=ArchitectureInfo(
                pattern=arch_data.get("pattern", "unknown"),
                modules=[
                    ModuleInfo(
                        name=m.get("name", ""),
                        path=m.get("path", ""),
                        purpose=m.get("purpose", ""),
                        depends_on=m.get("depends_on", []),
                    )
                    for m in arch_data.get("modules", [])
                ],
                entry_points=arch_data.get("entry_points", []),
            ),
            domains=[
                DomainInfo(
                    name=d.get("name", ""),
                    keywords=d.get("keywords", []),
                    files=d.get("files", []),
                    models=d.get("models", []),
                    routes=d.get("routes", []),
                )
                for d in data.get("domains", [])
            ],
            patterns=PatternInfo(
                naming=pattern_data.get("naming", {}),
                structure=pattern_data.get("structure", {}),
                conventions=pattern_data.get("conventions", []),
            ),
            statistics=data.get("statistics", {}),
        )

    def _dict_to_tech(self, data: dict) -> TechInfo:
        """Convert dict to TechInfo."""
        return TechInfo(
            name=data.get("name", ""),
            confidence=data.get("confidence", 0.0),
            version=data.get("version"),
            entry_point=data.get("entry_point"),
            config_file=data.get("config_file"),
        )

    # --- Expert Index ---

    def load_index(self) -> Optional[ExpertIndex]:
        """Load expert index from database."""
        data = self._repo.load_expert_index()
        if not data:
            return None

        try:
            return self._dict_to_index(data)
        except Exception as e:
            logger.warning(f"Error loading expert index: {e}")
            return None

    def save_index(self, index: ExpertIndex) -> bool:
        """Save expert index to database."""
        try:
            index.last_updated = datetime.now().isoformat()

            experts = [
                {
                    "name": e.name,
                    "type": e.type,
                    "file": e.file,
                    "triggers": {
                        "keywords": e.triggers.keywords,
                        "paths": e.triggers.paths,
                        "topics": e.triggers.topics,
                    },
                    "weight": e.weight,
                }
                for e in index.experts
            ]

            self._repo.save_expert_index(
                experts=experts,
                keyword_map=index.keyword_map,
                path_map=index.path_map,
                version=index.version
            )
            return True
        except Exception as e:
            logger.error(f"Error saving expert index: {e}")
            return False

    def _dict_to_index(self, data: dict) -> ExpertIndex:
        """Convert dict to ExpertIndex."""
        return ExpertIndex(
            version=data.get("version", "1.0"),
            last_updated=data.get("last_updated", ""),
            experts=[
                ExpertIndexEntry(
                    name=e.get("name", ""),
                    type=e.get("type", "tech"),
                    file=e.get("file", ""),
                    triggers=ExpertTriggers(
                        keywords=e.get("triggers", {}).get("keywords", []),
                        paths=e.get("triggers", {}).get("paths", []),
                        topics=e.get("triggers", {}).get("topics", []),
                    ),
                    weight=e.get("weight", 1.0),
                )
                for e in data.get("experts", [])
            ],
            keyword_map=data.get("keyword_map", {}),
            path_map=data.get("path_map", {}),
        )

    # --- Scan Metadata ---

    def load_meta(self) -> Optional[ScanMeta]:
        """Load scan metadata from database."""
        data = self._repo.load_scan_meta()
        if not data:
            return None

        try:
            return ScanMeta(
                scan_id=data.get("scan_id", ""),
                started_at=data.get("started_at", ""),
                completed_at=data.get("completed_at", ""),
                duration_seconds=data.get("duration_seconds", 0),
                files_scanned=data.get("files_scanned", 0),
                scan_type=data.get("scan_type", "full"),
                trigger=data.get("trigger_type", "manual"),
                experts_generated=data.get("experts_generated", []),
            )
        except Exception as e:
            logger.warning(f"Error loading scan metadata: {e}")
            return None

    def save_meta(self, meta: ScanMeta) -> bool:
        """Save scan metadata to database."""
        try:
            self._repo.save_scan_meta(
                scan_id=meta.scan_id,
                started_at=meta.started_at,
                completed_at=meta.completed_at,
                duration_seconds=meta.duration_seconds,
                files_scanned=meta.files_scanned,
                scan_type=meta.scan_type,
                trigger=meta.trigger,
                experts_generated=meta.experts_generated
            )
            return True
        except Exception as e:
            logger.error(f"Error saving scan metadata: {e}")
            return False

    # --- Context Helpers ---

    def get_planning_context(self, max_chars: int = 4000) -> str:
        """
        Get architecture context for planning.

        Returns formatted string with key codebase information.
        """
        knowledge = self.load()
        if not knowledge:
            return ""

        sections = []

        # Project info
        if knowledge.project.name:
            sections.append(
                f"Project: {knowledge.project.name} ({knowledge.project.type})\n"
                f"Primary Language: {knowledge.project.primary_language}"
            )

        # Technologies
        tech_parts = []
        for lang in knowledge.technologies.languages:
            tech_parts.append(f"- {lang.name}")
        for fw in knowledge.technologies.frameworks:
            entry = f" ({fw.entry_point})" if fw.entry_point else ""
            tech_parts.append(f"- {fw.name}{entry}")
        for tool in knowledge.technologies.tools:
            tech_parts.append(f"- {tool.name}")
        if tech_parts:
            sections.append("Technologies:\n" + "\n".join(tech_parts))

        # Architecture
        if knowledge.architecture.modules:
            module_parts = []
            for m in knowledge.architecture.modules[:5]:  # Limit
                deps = f" -> {', '.join(m.depends_on)}" if m.depends_on else ""
                module_parts.append(f"- {m.name} ({m.path}): {m.purpose}{deps}")
            sections.append(
                f"Architecture: {knowledge.architecture.pattern}\n"
                f"Modules:\n" + "\n".join(module_parts)
            )

        # Domains
        if knowledge.domains:
            domain_parts = []
            for d in knowledge.domains[:5]:  # Limit
                files = f" - Files: {', '.join(d.files[:3])}" if d.files else ""
                domain_parts.append(f"- {d.name}: {', '.join(d.keywords[:5])}{files}")
            sections.append("Domains:\n" + "\n".join(domain_parts))

        # Patterns/Conventions
        if knowledge.patterns.conventions:
            sections.append(
                "Conventions:\n" +
                "\n".join(f"- {c}" for c in knowledge.patterns.conventions[:5])
            )

        context = "\n\n".join(sections)

        # Truncate if needed
        if len(context) > max_chars:
            context = context[:max_chars - 3] + "..."

        return context

    def get_domain_keywords(self) -> dict[str, list[str]]:
        """Get mapping of domain names to their keywords."""
        knowledge = self.load()
        if not knowledge:
            return {}

        return {d.name: d.keywords for d in knowledge.domains}

    def get_all_keywords(self) -> set[str]:
        """Get all domain keywords for matching."""
        knowledge = self.load()
        if not knowledge:
            return set()

        keywords = set()
        for domain in knowledge.domains:
            keywords.update(domain.keywords)
        return keywords

    def clear(self) -> None:
        """Clear all knowledge data from database."""
        self._repo.clear()
