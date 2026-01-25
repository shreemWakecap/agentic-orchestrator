"""
Knowledge Repository - ORM-based implementation.

Handles codebase knowledge, expert index, and scan metadata operations
using SQLAlchemy ORM for clean, type-safe database access.

SOLID Revamp:
- Implements IKnowledgeRepository interface
- Accepts optional project_id for dependency injection
- Falls back to contextvar if project_id not provided
"""
import json
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from ..connection import Database

from ..models import (
    CodebaseKnowledge, Technology, ArchitectureInfo, ArchitectureModule,
    Domain, Pattern, ExpertIndex, ExpertEntry, ScanMetadata,
    ExtendedScanMetadata, CodingRule
)
from .base import get_current_project_id
from .interfaces import IKnowledgeRepository


class KnowledgeRepository(IKnowledgeRepository):
    """Repository for knowledge store operations using ORM.

    Implements IKnowledgeRepository interface for dependency injection.

    Args:
        db: Database connection instance
        project_id: Optional project ID for explicit scoping.
                   If not provided, falls back to contextvar.
    """

    def __init__(self, db: "Database", project_id: Optional[str] = None):
        self.db = db
        self._project_id = project_id

    @property
    def project_id(self) -> Optional[str]:
        """Get the project ID for this repository.

        Returns injected project_id if available, otherwise
        falls back to the contextvar.
        """
        if self._project_id:
            return self._project_id
        return get_current_project_id()

    def save_knowledge(self, project_name: str, project_type: str, primary_language: str,
                       languages: list[dict], frameworks: list[dict], tools: list[dict],
                       architecture_pattern: str, modules: list[dict], entry_points: list[str],
                       domains: list[dict], naming: dict, structure: dict, conventions: list[str],
                       statistics: dict, version: str = "1.0") -> int:
        """Save codebase knowledge, replacing any existing for current project."""
        project_id = self.project_id

        with self.db.session() as session:
            # Clear existing knowledge for current project only
            if project_id:
                session.query(CodebaseKnowledge).filter_by(project_id=project_id).delete()
            else:
                # Legacy: clear all if no project context (shouldn't happen in multi-project mode)
                session.query(CodebaseKnowledge).filter_by(project_id=None).delete()

            # Create main knowledge record with project_id
            knowledge = CodebaseKnowledge(
                project_id=project_id,
                version=version,
                last_updated=datetime.now(),
                project_name=project_name,
                project_type=project_type,
                primary_language=primary_language,
                statistics_json=json.dumps(statistics)
            )
            session.add(knowledge)
            session.flush()  # Get the ID

            # Add technologies
            for tech in languages:
                session.add(Technology(
                    knowledge_id=knowledge.id,
                    tech_type='language',
                    name=tech.get('name'),
                    confidence=tech.get('confidence', 0.0),
                    version=tech.get('version')
                ))

            for tech in frameworks:
                session.add(Technology(
                    knowledge_id=knowledge.id,
                    tech_type='framework',
                    name=tech.get('name'),
                    confidence=tech.get('confidence', 0.0),
                    entry_point=tech.get('entry_point'),
                    config_file=tech.get('config_file')
                ))

            for tech in tools:
                session.add(Technology(
                    knowledge_id=knowledge.id,
                    tech_type='tool',
                    name=tech.get('name'),
                    confidence=tech.get('confidence', 0.0),
                    config_file=tech.get('config_file')
                ))

            # Add architecture info
            session.add(ArchitectureInfo(
                knowledge_id=knowledge.id,
                pattern=architecture_pattern,
                entry_points_json=json.dumps(entry_points)
            ))

            # Add modules
            for module in modules:
                session.add(ArchitectureModule(
                    knowledge_id=knowledge.id,
                    name=module.get('name'),
                    path=module.get('path'),
                    purpose=module.get('purpose'),
                    depends_on_json=json.dumps(module.get('depends_on', []))
                ))

            # Add domains
            for domain in domains:
                session.add(Domain(
                    knowledge_id=knowledge.id,
                    name=domain.get('name'),
                    keywords_json=json.dumps(domain.get('keywords', [])),
                    files_json=json.dumps(domain.get('files', [])),
                    models_json=json.dumps(domain.get('models', [])),
                    routes_json=json.dumps(domain.get('routes', []))
                ))

            # Add patterns
            session.add(Pattern(
                knowledge_id=knowledge.id,
                naming_json=json.dumps(naming),
                structure_json=json.dumps(structure),
                conventions_json=json.dumps(conventions)
            ))

            return knowledge.id

    def load_knowledge(self) -> Optional[dict]:
        """Load codebase knowledge from database for current project.

        Uses eager loading to fetch all related data in a single query,
        avoiding N+1 query issues.
        """
        from sqlalchemy.orm import joinedload

        project_id = self.project_id

        with self.db.session() as session:
            # Eager load all related data in a single query
            query = session.query(CodebaseKnowledge).options(
                joinedload(CodebaseKnowledge.technologies),
                joinedload(CodebaseKnowledge.architecture),
                joinedload(CodebaseKnowledge.modules),
                joinedload(CodebaseKnowledge.domains),
                joinedload(CodebaseKnowledge.patterns),
            )

            # Filter by project_id if available
            if project_id:
                query = query.filter_by(project_id=project_id)

            knowledge = query.first()

            if not knowledge:
                return None

            # Access pre-loaded relationships
            technologies = knowledge.technologies or []
            arch = knowledge.architecture
            modules = knowledge.modules or []
            domains = knowledge.domains or []
            patterns = knowledge.patterns

            languages = [t for t in technologies if t.tech_type == 'language']
            frameworks = [t for t in technologies if t.tech_type == 'framework']
            tools = [t for t in technologies if t.tech_type == 'tool']

            return {
                'version': knowledge.version,
                'last_updated': knowledge.last_updated.isoformat() if knowledge.last_updated else None,
                'project': {
                    'name': knowledge.project_name,
                    'type': knowledge.project_type,
                    'primary_language': knowledge.primary_language,
                },
                'technologies': {
                    'languages': [{'name': t.name, 'confidence': t.confidence, 'version': t.version} for t in languages],
                    'frameworks': [{'name': t.name, 'confidence': t.confidence, 'entry_point': t.entry_point, 'config_file': t.config_file} for t in frameworks],
                    'tools': [{'name': t.name, 'confidence': t.confidence, 'config_file': t.config_file} for t in tools],
                },
                'architecture': {
                    'pattern': arch.pattern if arch else 'unknown',
                    'entry_points': json.loads(arch.entry_points_json) if arch and arch.entry_points_json else [],
                    'modules': [{'name': m.name, 'path': m.path, 'purpose': m.purpose, 'depends_on': json.loads(m.depends_on_json or '[]')} for m in modules],
                },
                'domains': [{'name': d.name, 'keywords': json.loads(d.keywords_json or '[]'), 'files': json.loads(d.files_json or '[]'), 'models': json.loads(d.models_json or '[]'), 'routes': json.loads(d.routes_json or '[]')} for d in domains],
                'patterns': {
                    'naming': json.loads(patterns.naming_json) if patterns and patterns.naming_json else {},
                    'structure': json.loads(patterns.structure_json) if patterns and patterns.structure_json else {},
                    'conventions': json.loads(patterns.conventions_json) if patterns and patterns.conventions_json else [],
                },
                'statistics': json.loads(knowledge.statistics_json) if knowledge.statistics_json else {},
            }

    def exists(self) -> bool:
        """Check if knowledge exists."""
        with self.db.session() as session:
            return session.query(CodebaseKnowledge).count() > 0

    def clear(self):
        """Clear all knowledge data."""
        with self.db.session() as session:
            session.query(CodebaseKnowledge).delete()

    # --- Expert Index ---

    def save_expert_index(self, experts: list[dict], keyword_map: dict,
                          path_map: dict, version: str = "1.0") -> int:
        """Save expert index for current project, replacing any existing."""
        project_id = self.project_id

        with self.db.session() as session:
            # Clear existing index for current project only
            if project_id:
                session.query(ExpertIndex).filter_by(project_id=project_id).delete()
            else:
                session.query(ExpertIndex).filter_by(project_id=None).delete()

            # Create index record with project_id
            index = ExpertIndex(
                project_id=project_id,
                version=version,
                last_updated=datetime.now(),
                keyword_map_json=json.dumps(keyword_map),
                path_map_json=json.dumps(path_map)
            )
            session.add(index)
            session.flush()

            # Add expert entries
            for expert in experts:
                triggers = expert.get('triggers', {})
                session.add(ExpertEntry(
                    index_id=index.id,
                    name=expert.get('name'),
                    expert_type=expert.get('type'),
                    file_path=expert.get('file'),
                    weight=expert.get('weight', 1.0),
                    triggers_keywords_json=json.dumps(triggers.get('keywords', [])),
                    triggers_paths_json=json.dumps(triggers.get('paths', [])),
                    triggers_topics_json=json.dumps(triggers.get('topics', []))
                ))

            return index.id

    def load_expert_index(self) -> Optional[dict]:
        """Load expert index from database for current project."""
        project_id = self.project_id

        with self.db.session() as session:
            query = session.query(ExpertIndex)
            if project_id:
                query = query.filter_by(project_id=project_id)
            index = query.first()

            if not index:
                return None

            entries = session.query(ExpertEntry).filter_by(index_id=index.id).all()

            return {
                'version': index.version,
                'last_updated': index.last_updated.isoformat() if index.last_updated else None,
                'experts': [{
                    'name': e.name,
                    'type': e.expert_type,
                    'file': e.file_path,
                    'weight': e.weight,
                    'triggers': {
                        'keywords': json.loads(e.triggers_keywords_json or '[]'),
                        'paths': json.loads(e.triggers_paths_json or '[]'),
                        'topics': json.loads(e.triggers_topics_json or '[]'),
                    }
                } for e in entries],
                'keyword_map': json.loads(index.keyword_map_json or '{}'),
                'path_map': json.loads(index.path_map_json or '{}'),
            }

    def has_expert_index(self) -> bool:
        """Check if expert index exists for current project."""
        project_id = self.project_id

        with self.db.session() as session:
            query = session.query(ExpertIndex)
            if project_id:
                query = query.filter_by(project_id=project_id)
            return query.count() > 0

    # --- Scan Metadata ---

    def save_scan_meta(self, scan_id: str, started_at: str, completed_at: str = None,
                       duration_seconds: float = 0, files_scanned: int = 0,
                       scan_type: str = "full", trigger: str = "manual",
                       experts_generated: list[str] = None) -> int:
        """Save scan metadata for current project."""
        project_id = self.project_id

        with self.db.session() as session:
            # Check for existing scan
            existing = session.query(ScanMetadata).filter_by(scan_id=scan_id).first()

            if existing:
                existing.completed_at = datetime.fromisoformat(completed_at) if completed_at else None
                existing.duration_seconds = duration_seconds
                existing.files_scanned = files_scanned
                existing.experts_generated_json = json.dumps(experts_generated or [])
                return existing.id
            else:
                scan = ScanMetadata(
                    project_id=project_id,
                    scan_id=scan_id,
                    started_at=datetime.fromisoformat(started_at) if started_at else datetime.now(),
                    completed_at=datetime.fromisoformat(completed_at) if completed_at else None,
                    duration_seconds=duration_seconds,
                    files_scanned=files_scanned,
                    scan_type=scan_type,
                    trigger_type=trigger,
                    experts_generated_json=json.dumps(experts_generated or [])
                )
                session.add(scan)
                session.flush()
                return scan.id

    def load_scan_meta(self) -> Optional[dict]:
        """Load most recent scan metadata for current project."""
        project_id = self.project_id

        with self.db.session() as session:
            query = session.query(ScanMetadata).order_by(ScanMetadata.started_at.desc())
            if project_id:
                query = query.filter_by(project_id=project_id)
            scan = query.first()

            if not scan:
                return None

            return {
                'id': scan.id,
                'scan_id': scan.scan_id,
                'started_at': scan.started_at.isoformat() if scan.started_at else None,
                'completed_at': scan.completed_at.isoformat() if scan.completed_at else None,
                'duration_seconds': scan.duration_seconds,
                'files_scanned': scan.files_scanned,
                'scan_type': scan.scan_type,
                'trigger_type': scan.trigger_type,
                'experts_generated': json.loads(scan.experts_generated_json or '[]'),
            }

    # --- Search Methods for Codebase Explorer ---

    def search_domains_by_keyword(self, keywords: list[str]) -> list[dict]:
        """Search domains that match any of the given keywords for current project."""
        if not keywords:
            return []

        project_id = self.project_id

        with self.db.session() as session:
            query = session.query(CodebaseKnowledge)
            if project_id:
                query = query.filter_by(project_id=project_id)
            knowledge = query.first()

            if not knowledge:
                return []

            domains = session.query(Domain).filter_by(knowledge_id=knowledge.id).all()
            results = []
            keywords_lower = [kw.lower() for kw in keywords]

            for d in domains:
                domain_keywords = json.loads(d.keywords_json or '[]')
                domain_keywords_lower = [dk.lower() for dk in domain_keywords]

                matching_keywords = [
                    kw for kw in keywords_lower
                    if any(kw in dk or dk in kw for dk in domain_keywords_lower)
                ]

                if matching_keywords:
                    results.append({
                        'name': d.name,
                        'keywords': domain_keywords,
                        'files': json.loads(d.files_json or '[]'),
                        'models': json.loads(d.models_json or '[]'),
                        'routes': json.loads(d.routes_json or '[]'),
                        'matched_keywords': matching_keywords,
                    })

            return results

    def search_modules_by_path(self, path_pattern: str) -> list[dict]:
        """Search modules whose path matches the given pattern for current project."""
        if not path_pattern:
            return []

        project_id = self.project_id

        with self.db.session() as session:
            query = session.query(CodebaseKnowledge)
            if project_id:
                query = query.filter_by(project_id=project_id)
            knowledge = query.first()

            if not knowledge:
                return []

            modules = session.query(ArchitectureModule).filter_by(knowledge_id=knowledge.id).all()
            results = []
            pattern_lower = path_pattern.lower()

            for m in modules:
                module_path = m.path or ''
                module_name = m.name or ''

                if pattern_lower in module_path.lower() or pattern_lower in module_name.lower():
                    results.append({
                        'name': m.name,
                        'path': m.path,
                        'purpose': m.purpose,
                        'depends_on': json.loads(m.depends_on_json or '[]'),
                    })

            return results

    def get_technologies(self) -> dict:
        """Get all technologies from knowledge store for current project."""
        project_id = self.project_id

        with self.db.session() as session:
            query = session.query(CodebaseKnowledge)
            if project_id:
                query = query.filter_by(project_id=project_id)
            knowledge = query.first()

            if not knowledge:
                return {'languages': [], 'frameworks': [], 'tools': []}

            technologies = session.query(Technology).filter_by(knowledge_id=knowledge.id).all()

            return {
                'languages': [{'name': t.name, 'confidence': t.confidence, 'version': t.version} for t in technologies if t.tech_type == 'language'],
                'frameworks': [{'name': t.name, 'confidence': t.confidence, 'entry_point': t.entry_point, 'config_file': t.config_file} for t in technologies if t.tech_type == 'framework'],
                'tools': [{'name': t.name, 'confidence': t.confidence, 'config_file': t.config_file} for t in technologies if t.tech_type == 'tool'],
            }

    def get_conventions(self) -> dict:
        """Get coding conventions and patterns from knowledge store for current project."""
        project_id = self.project_id

        with self.db.session() as session:
            query = session.query(CodebaseKnowledge)
            if project_id:
                query = query.filter_by(project_id=project_id)
            knowledge = query.first()

            if not knowledge:
                return {'naming': {}, 'structure': {}, 'conventions': []}

            patterns = session.query(Pattern).filter_by(knowledge_id=knowledge.id).first()
            if not patterns:
                return {'naming': {}, 'structure': {}, 'conventions': []}

            return {
                'naming': json.loads(patterns.naming_json or '{}'),
                'structure': json.loads(patterns.structure_json or '{}'),
                'conventions': json.loads(patterns.conventions_json or '[]'),
            }

    # --- Coding Rules ---

    def save_coding_rule(self, rule) -> int:
        """Save a coding rule to the database for current project."""
        project_id = self.project_id

        with self.db.session() as session:
            # Get knowledge ID for current project
            query = session.query(CodebaseKnowledge)
            if project_id:
                query = query.filter_by(project_id=project_id)
            knowledge = query.first()
            knowledge_id = knowledge.id if knowledge else None

            # Check for existing rule (scoped to project)
            rule_query = session.query(CodingRule).filter_by(rule_id=rule.id)
            if project_id:
                rule_query = rule_query.filter_by(project_id=project_id)
            existing = rule_query.first()

            if existing:
                existing.category = rule.category
                existing.rule_text = rule.rule
                existing.severity = rule.severity
                existing.examples_json = json.dumps(rule.examples)
                existing.source_files_json = json.dumps(rule.source_files)
                existing.confidence = max(existing.confidence, rule.confidence)
                existing.updated_at = datetime.now()
                return existing.id
            else:
                coding_rule = CodingRule(
                    project_id=project_id,
                    knowledge_id=knowledge_id,
                    rule_id=rule.id,
                    category=rule.category,
                    rule_text=rule.rule,
                    severity=rule.severity,
                    examples_json=json.dumps(rule.examples),
                    source_files_json=json.dumps(rule.source_files),
                    confidence=rule.confidence
                )
                session.add(coding_rule)
                session.flush()
                return coding_rule.id

    def get_coding_rules(self, category: str = None, min_confidence: float = 0.0) -> list[dict]:
        """Get coding rules from the database for current project."""
        project_id = self.project_id

        with self.db.session() as session:
            query = session.query(CodingRule).filter(CodingRule.confidence >= min_confidence)

            if project_id:
                query = query.filter_by(project_id=project_id)

            if category:
                query = query.filter_by(category=category)

            rules = query.order_by(CodingRule.severity.desc(), CodingRule.confidence.desc()).all()

            return [{
                'id': r.rule_id,
                'category': r.category,
                'rule': r.rule_text,
                'severity': r.severity,
                'examples': json.loads(r.examples_json or '[]'),
                'source_files': json.loads(r.source_files_json or '[]'),
                'confidence': r.confidence,
            } for r in rules]

    def delete_coding_rule(self, rule_id: str) -> bool:
        """Delete a coding rule by its ID for current project."""
        project_id = self.project_id

        with self.db.session() as session:
            query = session.query(CodingRule).filter_by(rule_id=rule_id)
            if project_id:
                query = query.filter_by(project_id=project_id)
            deleted = query.delete()
            return deleted > 0

    def clear_coding_rules(self):
        """Clear all coding rules for current project."""
        project_id = self.project_id

        with self.db.session() as session:
            query = session.query(CodingRule)
            if project_id:
                query = query.filter_by(project_id=project_id)
            query.delete()

    # --- Extended Scan Metadata (with Git State) ---

    def save_scan_metadata(self, metadata: dict) -> int:
        """Save extended scan metadata including git state for current project."""
        project_id = self.project_id

        with self.db.session() as session:
            scan = ExtendedScanMetadata(
                project_id=project_id,
                git_commit_hash=metadata.get('git_commit_hash'),
                git_branch=metadata.get('git_branch'),
                scanned_paths_json=json.dumps(metadata.get('scanned_paths', [])),
                trigger_type=metadata.get('trigger', 'manual'),
                scan_time=datetime.fromisoformat(metadata['scan_time']) if metadata.get('scan_time') else datetime.now(),
                scan_mode=metadata.get('mode', 'full')
            )
            session.add(scan)
            session.flush()
            return scan.id

    def get_scan_metadata(self) -> Optional[dict]:
        """Get the most recent extended scan metadata for current project."""
        project_id = self.project_id

        with self.db.session() as session:
            query = session.query(ExtendedScanMetadata).order_by(ExtendedScanMetadata.scan_time.desc())
            if project_id:
                query = query.filter_by(project_id=project_id)
            scan = query.first()

            if not scan:
                return None

            return {
                'id': scan.id,
                'git_commit_hash': scan.git_commit_hash,
                'git_branch': scan.git_branch,
                'scanned_paths': json.loads(scan.scanned_paths_json or '[]'),
                'trigger': scan.trigger_type,
                'scan_time': scan.scan_time.isoformat() if scan.scan_time else None,
                'mode': scan.scan_mode,
            }

    def get_scan_history(self, limit: int = 10) -> list[dict]:
        """Get recent scan history for current project."""
        project_id = self.project_id

        with self.db.session() as session:
            query = session.query(ExtendedScanMetadata).order_by(
                ExtendedScanMetadata.scan_time.desc()
            )
            if project_id:
                query = query.filter_by(project_id=project_id)
            scans = query.limit(limit).all()

            return [{
                'id': s.id,
                'git_commit_hash': s.git_commit_hash,
                'git_branch': s.git_branch,
                'scanned_paths': json.loads(s.scanned_paths_json or '[]'),
                'trigger': s.trigger_type,
                'scan_time': s.scan_time.isoformat() if s.scan_time else None,
                'mode': s.scan_mode,
            } for s in scans]
