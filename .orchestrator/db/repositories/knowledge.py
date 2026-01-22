"""
Knowledge Repository - ORM-based implementation.

Handles codebase knowledge, expert index, and scan metadata operations
using SQLAlchemy ORM for clean, type-safe database access.
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


class KnowledgeRepository:
    """Repository for knowledge store operations using ORM."""

    def __init__(self, db: "Database"):
        self.db = db

    def save_knowledge(self, project_name: str, project_type: str, primary_language: str,
                       languages: list[dict], frameworks: list[dict], tools: list[dict],
                       architecture_pattern: str, modules: list[dict], entry_points: list[str],
                       domains: list[dict], naming: dict, structure: dict, conventions: list[str],
                       statistics: dict, version: str = "1.0") -> int:
        """Save codebase knowledge, replacing any existing."""
        with self.db.session() as session:
            # Clear existing knowledge
            session.query(CodebaseKnowledge).delete()

            # Create main knowledge record
            knowledge = CodebaseKnowledge(
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
        """Load codebase knowledge from database."""
        with self.db.session() as session:
            knowledge = session.query(CodebaseKnowledge).first()
            if not knowledge:
                return None

            # Load related data
            technologies = session.query(Technology).filter_by(knowledge_id=knowledge.id).all()
            arch = session.query(ArchitectureInfo).filter_by(knowledge_id=knowledge.id).first()
            modules = session.query(ArchitectureModule).filter_by(knowledge_id=knowledge.id).all()
            domains = session.query(Domain).filter_by(knowledge_id=knowledge.id).all()
            patterns = session.query(Pattern).filter_by(knowledge_id=knowledge.id).first()

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
        """Save expert index, replacing any existing."""
        with self.db.session() as session:
            # Clear existing index
            session.query(ExpertIndex).delete()

            # Create index record
            index = ExpertIndex(
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
        """Load expert index from database."""
        with self.db.session() as session:
            index = session.query(ExpertIndex).first()
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
        """Check if expert index exists."""
        with self.db.session() as session:
            return session.query(ExpertIndex).count() > 0

    # --- Scan Metadata ---

    def save_scan_meta(self, scan_id: str, started_at: str, completed_at: str = None,
                       duration_seconds: float = 0, files_scanned: int = 0,
                       scan_type: str = "full", trigger: str = "manual",
                       experts_generated: list[str] = None) -> int:
        """Save scan metadata."""
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
        """Load most recent scan metadata."""
        with self.db.session() as session:
            scan = session.query(ScanMetadata).order_by(ScanMetadata.started_at.desc()).first()
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
        """Search domains that match any of the given keywords."""
        if not keywords:
            return []

        with self.db.session() as session:
            knowledge = session.query(CodebaseKnowledge).first()
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
        """Search modules whose path matches the given pattern."""
        if not path_pattern:
            return []

        with self.db.session() as session:
            knowledge = session.query(CodebaseKnowledge).first()
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
        """Get all technologies from knowledge store."""
        with self.db.session() as session:
            knowledge = session.query(CodebaseKnowledge).first()
            if not knowledge:
                return {'languages': [], 'frameworks': [], 'tools': []}

            technologies = session.query(Technology).filter_by(knowledge_id=knowledge.id).all()

            return {
                'languages': [{'name': t.name, 'confidence': t.confidence, 'version': t.version} for t in technologies if t.tech_type == 'language'],
                'frameworks': [{'name': t.name, 'confidence': t.confidence, 'entry_point': t.entry_point, 'config_file': t.config_file} for t in technologies if t.tech_type == 'framework'],
                'tools': [{'name': t.name, 'confidence': t.confidence, 'config_file': t.config_file} for t in technologies if t.tech_type == 'tool'],
            }

    def get_conventions(self) -> dict:
        """Get coding conventions and patterns from knowledge store."""
        with self.db.session() as session:
            knowledge = session.query(CodebaseKnowledge).first()
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
        """Save a coding rule to the database."""
        with self.db.session() as session:
            # Get knowledge ID
            knowledge = session.query(CodebaseKnowledge).first()
            knowledge_id = knowledge.id if knowledge else None

            # Check for existing rule
            existing = session.query(CodingRule).filter_by(rule_id=rule.id).first()

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
        """Get coding rules from the database."""
        with self.db.session() as session:
            query = session.query(CodingRule).filter(CodingRule.confidence >= min_confidence)

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
        """Delete a coding rule by its ID."""
        with self.db.session() as session:
            deleted = session.query(CodingRule).filter_by(rule_id=rule_id).delete()
            return deleted > 0

    def clear_coding_rules(self):
        """Clear all coding rules."""
        with self.db.session() as session:
            session.query(CodingRule).delete()

    # --- Extended Scan Metadata (with Git State) ---

    def save_scan_metadata(self, metadata: dict) -> int:
        """Save extended scan metadata including git state."""
        with self.db.session() as session:
            scan = ExtendedScanMetadata(
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
        """Get the most recent extended scan metadata."""
        with self.db.session() as session:
            scan = session.query(ExtendedScanMetadata).order_by(ExtendedScanMetadata.scan_time.desc()).first()
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
        """Get recent scan history."""
        with self.db.session() as session:
            scans = session.query(ExtendedScanMetadata).order_by(
                ExtendedScanMetadata.scan_time.desc()
            ).limit(limit).all()

            return [{
                'id': s.id,
                'git_commit_hash': s.git_commit_hash,
                'git_branch': s.git_branch,
                'scanned_paths': json.loads(s.scanned_paths_json or '[]'),
                'trigger': s.trigger_type,
                'scan_time': s.scan_time.isoformat() if s.scan_time else None,
                'mode': s.scan_mode,
            } for s in scans]
