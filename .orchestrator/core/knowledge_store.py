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

from db import get_knowledge_repository, KnowledgeRepository, get_file_knowledge_repository, FileKnowledgeRepository

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
class CodingRule:
    """
    Coding rule extracted from codebase analysis.

    Used for soft-enforcement of conventions during planning.
    """
    id: str                           # e.g., "naming-001"
    category: str                     # naming, structure, patterns, security, testing, documentation
    rule: str                         # "Use snake_case for Python files"
    severity: str = "info"            # info, warning, error
    examples: list[str] = field(default_factory=list)  # Good/bad examples
    source_files: list[str] = field(default_factory=list)  # Where this was inferred from
    confidence: float = 0.5           # 0-1

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "category": self.category,
            "rule": self.rule,
            "severity": self.severity,
            "examples": self.examples,
            "source_files": self.source_files,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CodingRule":
        """Create from dictionary."""
        return cls(
            id=data.get("id", ""),
            category=data.get("category", "general"),
            rule=data.get("rule", ""),
            severity=data.get("severity", "info"),
            examples=data.get("examples", []),
            source_files=data.get("source_files", []),
            confidence=data.get("confidence", 0.5),
        )


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
    coding_rules: list[CodingRule] = field(default_factory=list)

    # Backward compatibility properties
    @property
    def project_name(self) -> str:
        return self.project.name

    @property
    def project_type(self) -> str:
        return self.project.type

    @property
    def primary_language(self) -> str:
        return self.project.primary_language

    @property
    def languages(self) -> list[TechInfo]:
        return self.technologies.languages

    @property
    def frameworks(self) -> list[TechInfo]:
        return self.technologies.frameworks

    @property
    def tools(self) -> list[TechInfo]:
        return self.technologies.tools

    @property
    def architecture_pattern(self) -> str:
        return self.architecture.pattern

    @property
    def modules(self) -> list[ModuleInfo]:
        return self.architecture.modules

    @property
    def entry_points(self) -> list[str]:
        return self.architecture.entry_points

    @property
    def naming_conventions(self) -> dict[str, str]:
        return self.patterns.naming

    @property
    def structure_conventions(self) -> dict[str, str]:
        return self.patterns.structure

    @property
    def code_conventions(self) -> list[str]:
        return self.patterns.conventions

    @property
    def last_scan(self) -> str:
        return self.last_updated

    @property
    def experts(self) -> list:
        """Placeholder for expert list - populated separately."""
        return []

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "version": self.version,
            "last_updated": self.last_updated,
            "project": {
                "name": self.project.name,
                "type": self.project.type,
                "primary_language": self.project.primary_language,
            },
            "technologies": {
                "languages": [{"name": t.name, "confidence": t.confidence, "version": t.version} for t in self.technologies.languages],
                "frameworks": [{"name": t.name, "confidence": t.confidence, "version": t.version} for t in self.technologies.frameworks],
                "tools": [{"name": t.name, "confidence": t.confidence, "version": t.version} for t in self.technologies.tools],
            },
            "architecture": {
                "pattern": self.architecture.pattern,
                "modules": [{"name": m.name, "path": m.path, "purpose": m.purpose, "depends_on": m.depends_on} for m in self.architecture.modules],
                "entry_points": self.architecture.entry_points,
            },
            "domains": [{"name": d.name, "keywords": d.keywords, "files": d.files, "models": d.models, "routes": d.routes} for d in self.domains],
            "patterns": {
                "naming": self.patterns.naming,
                "structure": self.patterns.structure,
                "conventions": self.patterns.conventions,
            },
            "statistics": self.statistics,
            "coding_rules": [r.to_dict() for r in self.coding_rules],
        }


# --- Aliases for unified scout workflow compatibility ---

# Technology is an alias for TechInfo
Technology = TechInfo

# Module is an alias for ModuleInfo
Module = ModuleInfo

# Domain is an alias for DomainInfo
Domain = DomainInfo

# Expert placeholder dataclass for unified scout
@dataclass
class Expert:
    """Expert profile (placeholder for unified scout compatibility)."""
    name: str
    description: str = ""
    triggers: list[str] = field(default_factory=list)


# --- Smart Scout: Layered Knowledge Models ---

@dataclass
class ScanCriteria:
    """User-provided scan criteria (Phase 1)."""
    focus: str = "overview"  # overview, domains, audit, architecture
    areas: list[str] = field(default_factory=list)  # backend, frontend, infra, data, testing
    depth: str = "standard"  # quick, standard, deep
    specific_paths: list[str] = field(default_factory=list)


@dataclass
class DetectedDomain:
    """Domain detected during Phase 2."""
    path: str
    name: str
    classification: str = "unknown"  # code, config, docs, generated, unknown
    file_count: int = 0
    subdirectory_count: int = 0
    detected_languages: list[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class ApprovedDomain:
    """User-approved domain for scanning (Phase 3)."""
    path: str
    name: str
    scan_depth: str = "standard"  # quick, standard, deep
    priority: int = 0


@dataclass
class SolutionOverview:
    """Layer 1: High-level solution overview."""
    purpose: str = ""
    domains: list[str] = field(default_factory=list)
    estimated_size: str = "unknown"  # small, medium, large, enterprise
    structure_type: str = "unknown"  # single, multi-project, monorepo, microservices
    root_directories: list[str] = field(default_factory=list)
    primary_language: str = ""


@dataclass
class TechStackInfo:
    """Layer 2: Technology stack details."""
    domain: str = ""
    languages: list[TechInfo] = field(default_factory=list)
    frameworks: list[TechInfo] = field(default_factory=list)
    tools: list[TechInfo] = field(default_factory=list)
    build_system: str = ""
    package_manager: str = ""
    test_framework: str = ""


@dataclass
class DomainDetails:
    """Layer 3: Domain responsibilities and boundaries."""
    name: str = ""
    responsibilities: list[str] = field(default_factory=list)
    boundaries: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    key_files: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    public_apis: list[str] = field(default_factory=list)


@dataclass
class RiskInfo:
    """Identified risk in codebase."""
    category: str = ""  # security, performance, maintainability
    description: str = ""
    severity: str = "low"  # low, medium, high, critical
    location: str = ""
    recommendation: str = ""


@dataclass
class RuleInfo:
    """Extracted coding rule."""
    name: str = ""
    description: str = ""
    scope: str = "global"  # global, domain-specific
    examples: list[str] = field(default_factory=list)
    rationale: str = ""


@dataclass
class DeepTechnicalInfo:
    """Layer 4: Patterns, rules, risks."""
    domain: str = ""
    patterns: list[str] = field(default_factory=list)
    conventions: list[str] = field(default_factory=list)
    risks: list[RiskInfo] = field(default_factory=list)
    rules: list[RuleInfo] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)


@dataclass
class LayeredKnowledge:
    """Complete layered knowledge for a domain."""
    domain: str = ""
    overview: Optional[SolutionOverview] = None
    tech_stack: Optional[TechStackInfo] = None
    domain_details: Optional[DomainDetails] = None
    deep_technical: Optional[DeepTechnicalInfo] = None
    scan_depth_reached: str = ""  # quick, standard, deep
    last_scanned: str = ""


@dataclass
class SmartScanSession:
    """Tracks a multi-phase scan session."""
    session_id: str = ""
    started_at: str = ""
    completed_at: str = ""
    criteria: Optional[ScanCriteria] = None
    detected_domains: list[DetectedDomain] = field(default_factory=list)
    approved_domains: list[ApprovedDomain] = field(default_factory=list)
    current_phase: int = 0  # 1-5
    status: str = "pending"  # pending, in_progress, paused, completed, failed
    knowledge: dict[str, LayeredKnowledge] = field(default_factory=dict)  # domain -> knowledge
    experts_generated: list[str] = field(default_factory=list)
    rules_extracted: list[RuleInfo] = field(default_factory=list)


# --- Original Models (Legacy) ---

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


# --- File-Level Knowledge Data Models ---

@dataclass
class FileKnowledge:
    """File-level knowledge from targeted scouting."""
    file_path: str
    file_name: str = ""
    language: str = ""
    size_bytes: int = 0
    line_count: int = 0
    last_modified: str = ""
    content_hash: str = ""
    imports: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    classes: list[dict] = field(default_factory=list)
    functions: list[dict] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    domain_hints: list[str] = field(default_factory=list)
    notes: str = ""
    scouted_at: str = ""


@dataclass
class FileScanResult:
    """Result of a file-level scan operation."""
    scan_id: str
    file_path: str
    success: bool = False
    started_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0
    error: Optional[str] = None


# --- Knowledge Store ---

class KnowledgeStore:
    """
    Manages persistent codebase knowledge in PostgreSQL database.

    Multi-Project Support:
        In multi-project mode, knowledge is scoped to the current project
        via the project_context. The store automatically filters by project_id.

    Usage:
        # Single-project mode (legacy)
        store = KnowledgeStore(project_root)

        # Multi-project mode
        from db.project_context import project_context
        with project_context.set_project(project_id):
            store = KnowledgeStore(project_root)
            knowledge = store.load()

        # Or explicitly pass project_id
        store = KnowledgeStore(project_root, project_id="uuid-123")

        # Check if knowledge exists
        if store.exists():
            knowledge = store.load()

        # Save knowledge
        store.save(knowledge)

        # Get planning context
        context = store.get_planning_context()
    """

    def __init__(self, project_root: Path, project_id: str = None):
        self.project_root = project_root.resolve()
        self._repo = get_knowledge_repository()
        self._project_id = project_id
        self._context_token = None

    @property
    def project_id(self) -> Optional[str]:
        """Get the current project ID (from explicit or context)."""
        if self._project_id:
            return self._project_id
        # Try to get from context
        try:
            from db.project_context import get_optional_project_id
            return get_optional_project_id()
        except ImportError:
            return None

    def _ensure_project_context(self):
        """Set project context if we have an explicit project_id."""
        if self._project_id and not self._context_token:
            from db.project_context import project_context
            self._context_token = project_context.set_project_sync(self._project_id)

    def _clear_project_context(self):
        """Clear project context if we set it."""
        if self._context_token:
            from db.project_context import project_context
            project_context.reset_project(self._context_token)
            self._context_token = None

    @property
    def codebase_file(self) -> Path:
        """Return path to the knowledge database file.

        This property provides backward compatibility for code that
        expects a file path for the knowledge storage.
        """
        from db import get_db_path
        return get_db_path()

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

        # Integration patterns for layered architecture
        if knowledge.architecture.pattern == "layered":
            sections.append("""Integration Pattern (CRITICAL for new features):
When adding a new feature module, create ALL layers in order:
1. Repository: db/repositories/{module}.py + export in __init__.py files
2. Service: portal/services/{module}_service.py
3. Dependency: portal/dependencies.py - add get_{module}_repo()
4. API Routes: portal/routes/{module}.py
5. Route Registration: import in routes/__init__.py + include_router in app.py
6. Page Route: portal/routes/pages.py - add /{module} page
7. Template: portal/templates/{module}.html

Reference: Trace the Knowledge module to see this pattern in action.""")

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


# --- File Knowledge Store ---

class FileKnowledgeStore:
    """
    Manages file-level knowledge for targeted scouting.

    Stores individual file analysis results separately from bulk scans.

    Multi-Project Support:
        In multi-project mode, file knowledge is scoped to the current project.
        File paths are unique within a project, not globally.

    Usage:
        store = FileKnowledgeStore(project_root)

        # Save file knowledge
        store.save(file_knowledge)

        # Load file knowledge
        knowledge = store.load("path/to/file.py")

        # Check if knowledge exists
        if store.exists("path/to/file.py"):
            ...

        # Get all scanned files
        all_files = store.get_all()
    """

    def __init__(self, project_root: Path, project_id: str = None):
        self.project_root = project_root.resolve()
        self._repo = get_file_knowledge_repository()
        self._project_id = project_id

    @property
    def project_id(self) -> Optional[str]:
        """Get the current project ID (from explicit or context)."""
        if self._project_id:
            return self._project_id
        try:
            from db.project_context import get_optional_project_id
            return get_optional_project_id()
        except ImportError:
            return None

    def exists(self, file_path: str) -> bool:
        """Check if knowledge exists for a specific file."""
        return self._repo.exists(file_path)

    def load(self, file_path: str) -> Optional[FileKnowledge]:
        """Load knowledge for a specific file."""
        data = self._repo.load_file_knowledge(file_path)
        if not data:
            return None

        try:
            return self._dict_to_file_knowledge(data)
        except Exception as e:
            logger.warning(f"Error loading file knowledge for {file_path}: {e}")
            return None

    def save(self, knowledge: FileKnowledge) -> bool:
        """Save file knowledge to database."""
        try:
            knowledge.scouted_at = datetime.now().isoformat()

            # Extract metadata for storage
            metadata = {
                "file_name": knowledge.file_name,
                "last_modified": knowledge.last_modified,
                "content_hash": knowledge.content_hash,
                "domain_hints": knowledge.domain_hints,
                "notes": knowledge.notes,
            }

            self._repo.save_file_knowledge(
                file_path=knowledge.file_path,
                file_type=self._detect_file_type(knowledge.file_path, knowledge.language),
                language=knowledge.language,
                size_bytes=knowledge.size_bytes,
                line_count=knowledge.line_count,
                imports=knowledge.imports,
                exports=knowledge.exports,
                classes=knowledge.classes,
                functions=knowledge.functions,
                dependencies=knowledge.dependencies,
                metadata=metadata,
                summary=knowledge.notes,
            )
            return True
        except Exception as e:
            logger.error(f"Error saving file knowledge for {knowledge.file_path}: {e}")
            return False

    def delete(self, file_path: str) -> bool:
        """Delete knowledge for a specific file."""
        return self._repo.delete_file_knowledge(file_path)

    def get_all(self) -> list[FileKnowledge]:
        """Get knowledge for all scanned files."""
        data_list = self._repo.get_all_file_knowledge()
        result = []
        for data in data_list:
            try:
                result.append(self._dict_to_file_knowledge(data))
            except Exception as e:
                logger.warning(f"Error loading file knowledge: {e}")
        return result

    def save_scan_result(self, result: FileScanResult, knowledge_id: int = None) -> bool:
        """Save a file scan result."""
        try:
            status = "completed" if result.success else "failed"
            self._repo.save_file_scan(
                scan_id=result.scan_id,
                file_path=result.file_path,
                scan_type="single",
                trigger="manual",
                started_at=result.started_at,
                completed_at=result.completed_at,
                duration_seconds=result.duration_seconds,
                status=status,
                error_message=result.error,
                knowledge_id=knowledge_id,
            )
            return True
        except Exception as e:
            logger.error(f"Error saving scan result for {result.file_path}: {e}")
            return False

    def get_scan_history(self, file_path: str, limit: int = 10) -> list[FileScanResult]:
        """Get scan history for a specific file."""
        rows = self._repo.get_file_scan_history(file_path, limit)
        result = []
        for row in rows:
            try:
                result.append(FileScanResult(
                    scan_id=row.get("scan_id", ""),
                    file_path=row.get("file_path", ""),
                    success=row.get("status") == "completed",
                    started_at=row.get("started_at", ""),
                    completed_at=row.get("completed_at", ""),
                    duration_seconds=row.get("duration_seconds", 0),
                    error=row.get("error_message"),
                ))
            except Exception as e:
                logger.warning(f"Error loading scan history: {e}")
        return result

    def clear(self) -> int:
        """Clear all file knowledge data from database."""
        return self._repo.clear_all_file_knowledge()

    def _dict_to_file_knowledge(self, data: dict) -> FileKnowledge:
        """Convert database dict to FileKnowledge dataclass."""
        metadata = data.get("metadata", {}) or {}
        return FileKnowledge(
            file_path=data.get("file_path", ""),
            file_name=metadata.get("file_name", Path(data.get("file_path", "")).name),
            language=data.get("language", ""),
            size_bytes=data.get("size_bytes", 0),
            line_count=data.get("line_count", 0),
            last_modified=metadata.get("last_modified", ""),
            content_hash=metadata.get("content_hash", ""),
            imports=data.get("imports", []),
            exports=data.get("exports", []),
            classes=data.get("classes", []),
            functions=data.get("functions", []),
            dependencies=data.get("dependencies", []),
            domain_hints=metadata.get("domain_hints", []),
            notes=data.get("summary", "") or metadata.get("notes", ""),
            scouted_at=data.get("last_scanned", ""),
        )

    def _detect_file_type(self, file_path: str, language: str) -> str:
        """Detect file type from path and language."""
        path = Path(file_path)
        ext = path.suffix.lower()

        # Map extensions to types
        type_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
            ".rb": "ruby",
            ".php": "php",
            ".c": "c",
            ".cpp": "cpp",
            ".h": "header",
            ".hpp": "header",
            ".cs": "csharp",
            ".swift": "swift",
            ".kt": "kotlin",
            ".sql": "sql",
            ".html": "html",
            ".css": "css",
            ".scss": "scss",
            ".json": "config",
            ".yaml": "config",
            ".yml": "config",
            ".toml": "config",
            ".xml": "config",
            ".md": "markdown",
            ".txt": "text",
        }

        return type_map.get(ext, language or "unknown")
