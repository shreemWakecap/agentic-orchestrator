"""
Knowledge Repository.

Handles codebase knowledge, expert index, and scan metadata operations.
"""
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..connection import Database


class KnowledgeRepository:
    """Repository for knowledge store operations."""

    def __init__(self, db: "Database"):
        self.db = db

    def save_knowledge(self, project_name: str, project_type: str, primary_language: str,
                       languages: list[dict], frameworks: list[dict], tools: list[dict],
                       architecture_pattern: str, modules: list[dict], entry_points: list[str],
                       domains: list[dict], naming: dict, structure: dict, conventions: list[str],
                       statistics: dict, version: str = "1.0") -> int:
        """Save codebase knowledge, replacing any existing."""
        now = datetime.now().isoformat()

        with self.db.transaction() as conn:
            # Clear existing knowledge
            conn.execute("DELETE FROM codebase_knowledge")

            # Insert main knowledge record
            cursor = conn.execute("""
                INSERT INTO codebase_knowledge (version, last_updated, project_name,
                                               project_type, primary_language, statistics_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (version, now, project_name, project_type, primary_language,
                  self.db.to_json(statistics)))
            knowledge_id = cursor.lastrowid

            # Insert technologies
            for tech in languages:
                conn.execute("""
                    INSERT INTO technologies (knowledge_id, tech_type, name, confidence, version)
                    VALUES (?, 'language', ?, ?, ?)
                """, (knowledge_id, tech.get('name'), tech.get('confidence', 0.0),
                      tech.get('version')))

            for tech in frameworks:
                conn.execute("""
                    INSERT INTO technologies (knowledge_id, tech_type, name, confidence,
                                             entry_point, config_file)
                    VALUES (?, 'framework', ?, ?, ?, ?)
                """, (knowledge_id, tech.get('name'), tech.get('confidence', 0.0),
                      tech.get('entry_point'), tech.get('config_file')))

            for tech in tools:
                conn.execute("""
                    INSERT INTO technologies (knowledge_id, tech_type, name, confidence, config_file)
                    VALUES (?, 'tool', ?, ?, ?)
                """, (knowledge_id, tech.get('name'), tech.get('confidence', 0.0),
                      tech.get('config_file')))

            # Insert architecture info
            conn.execute("""
                INSERT INTO architecture_info (knowledge_id, pattern, entry_points_json)
                VALUES (?, ?, ?)
            """, (knowledge_id, architecture_pattern, self.db.to_json(entry_points)))

            # Insert modules
            for module in modules:
                conn.execute("""
                    INSERT INTO architecture_modules (knowledge_id, name, path, purpose, depends_on_json)
                    VALUES (?, ?, ?, ?, ?)
                """, (knowledge_id, module.get('name'), module.get('path'),
                      module.get('purpose'), self.db.to_json(module.get('depends_on', []))))

            # Insert domains
            for domain in domains:
                conn.execute("""
                    INSERT INTO domains (knowledge_id, name, keywords_json, files_json,
                                        models_json, routes_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (knowledge_id, domain.get('name'),
                      self.db.to_json(domain.get('keywords', [])),
                      self.db.to_json(domain.get('files', [])),
                      self.db.to_json(domain.get('models', [])),
                      self.db.to_json(domain.get('routes', []))))

            # Insert patterns
            conn.execute("""
                INSERT INTO patterns (knowledge_id, naming_json, structure_json, conventions_json)
                VALUES (?, ?, ?, ?)
            """, (knowledge_id, self.db.to_json(naming), self.db.to_json(structure),
                  self.db.to_json(conventions)))

            return knowledge_id

    def load_knowledge(self) -> Optional[dict]:
        """Load codebase knowledge from database."""
        row = self.db.fetchone("SELECT * FROM codebase_knowledge LIMIT 1")
        if not row:
            return None

        knowledge_id = row['id']

        # Load technologies
        tech_rows = self.db.fetchall(
            "SELECT * FROM technologies WHERE knowledge_id = ?", (knowledge_id,)
        )

        languages = [r for r in tech_rows if r['tech_type'] == 'language']
        frameworks = [r for r in tech_rows if r['tech_type'] == 'framework']
        tools = [r for r in tech_rows if r['tech_type'] == 'tool']

        # Load architecture
        arch_row = self.db.fetchone(
            "SELECT * FROM architecture_info WHERE knowledge_id = ?", (knowledge_id,)
        )
        module_rows = self.db.fetchall(
            "SELECT * FROM architecture_modules WHERE knowledge_id = ?", (knowledge_id,)
        )

        # Load domains
        domain_rows = self.db.fetchall(
            "SELECT * FROM domains WHERE knowledge_id = ?", (knowledge_id,)
        )

        # Load patterns
        pattern_row = self.db.fetchone(
            "SELECT * FROM patterns WHERE knowledge_id = ?", (knowledge_id,)
        )

        return {
            'version': row['version'],
            'last_updated': row['last_updated'],
            'project': {
                'name': row['project_name'],
                'type': row['project_type'],
                'primary_language': row['primary_language'],
            },
            'technologies': {
                'languages': [{
                    'name': t['name'],
                    'confidence': t['confidence'],
                    'version': t['version'],
                } for t in languages],
                'frameworks': [{
                    'name': t['name'],
                    'confidence': t['confidence'],
                    'entry_point': t['entry_point'],
                    'config_file': t['config_file'],
                } for t in frameworks],
                'tools': [{
                    'name': t['name'],
                    'confidence': t['confidence'],
                    'config_file': t['config_file'],
                } for t in tools],
            },
            'architecture': {
                'pattern': arch_row['pattern'] if arch_row else 'unknown',
                'entry_points': self.db.from_json(arch_row['entry_points_json'], []) if arch_row else [],
                'modules': [{
                    'name': m['name'],
                    'path': m['path'],
                    'purpose': m['purpose'],
                    'depends_on': self.db.from_json(m['depends_on_json'], []),
                } for m in module_rows],
            },
            'domains': [{
                'name': d['name'],
                'keywords': self.db.from_json(d['keywords_json'], []),
                'files': self.db.from_json(d['files_json'], []),
                'models': self.db.from_json(d['models_json'], []),
                'routes': self.db.from_json(d['routes_json'], []),
            } for d in domain_rows],
            'patterns': {
                'naming': self.db.from_json(pattern_row['naming_json'], {}) if pattern_row else {},
                'structure': self.db.from_json(pattern_row['structure_json'], {}) if pattern_row else {},
                'conventions': self.db.from_json(pattern_row['conventions_json'], []) if pattern_row else [],
            },
            'statistics': self.db.from_json(row['statistics_json'], {}),
        }

    def exists(self) -> bool:
        """Check if knowledge exists."""
        row = self.db.fetchone("SELECT COUNT(*) as count FROM codebase_knowledge")
        return row and row['count'] > 0

    def clear(self):
        """Clear all knowledge data."""
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM codebase_knowledge")

    # --- Expert Index ---

    def save_expert_index(self, experts: list[dict], keyword_map: dict,
                          path_map: dict, version: str = "1.0") -> int:
        """Save expert index, replacing any existing."""
        now = datetime.now().isoformat()

        with self.db.transaction() as conn:
            # Clear existing index
            conn.execute("DELETE FROM expert_index")

            # Insert index record
            cursor = conn.execute("""
                INSERT INTO expert_index (version, last_updated, keyword_map_json, path_map_json)
                VALUES (?, ?, ?, ?)
            """, (version, now, self.db.to_json(keyword_map), self.db.to_json(path_map)))
            index_id = cursor.lastrowid

            # Insert expert entries
            for expert in experts:
                triggers = expert.get('triggers', {})
                conn.execute("""
                    INSERT INTO expert_entries (index_id, name, expert_type, file_path, weight,
                                               triggers_keywords_json, triggers_paths_json,
                                               triggers_topics_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    index_id, expert.get('name'), expert.get('type'), expert.get('file'),
                    expert.get('weight', 1.0),
                    self.db.to_json(triggers.get('keywords', [])),
                    self.db.to_json(triggers.get('paths', [])),
                    self.db.to_json(triggers.get('topics', []))
                ))

            return index_id

    def load_expert_index(self) -> Optional[dict]:
        """Load expert index from database."""
        row = self.db.fetchone("SELECT * FROM expert_index LIMIT 1")
        if not row:
            return None

        index_id = row['id']
        expert_rows = self.db.fetchall(
            "SELECT * FROM expert_entries WHERE index_id = ?", (index_id,)
        )

        return {
            'version': row['version'],
            'last_updated': row['last_updated'],
            'experts': [{
                'name': e['name'],
                'type': e['expert_type'],
                'file': e['file_path'],
                'weight': e['weight'],
                'triggers': {
                    'keywords': self.db.from_json(e['triggers_keywords_json'], []),
                    'paths': self.db.from_json(e['triggers_paths_json'], []),
                    'topics': self.db.from_json(e['triggers_topics_json'], []),
                }
            } for e in expert_rows],
            'keyword_map': self.db.from_json(row['keyword_map_json'], {}),
            'path_map': self.db.from_json(row['path_map_json'], {}),
        }

    def has_expert_index(self) -> bool:
        """Check if expert index exists."""
        row = self.db.fetchone("SELECT COUNT(*) as count FROM expert_index")
        return row and row['count'] > 0

    # --- Scan Metadata ---

    def save_scan_meta(self, scan_id: str, started_at: str, completed_at: str = None,
                       duration_seconds: float = 0, files_scanned: int = 0,
                       scan_type: str = "full", trigger: str = "manual",
                       experts_generated: list[str] = None) -> int:
        """Save scan metadata."""
        with self.db.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO scan_metadata (scan_id, started_at, completed_at, duration_seconds,
                                          files_scanned, scan_type, trigger_type, experts_generated_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(scan_id) DO UPDATE SET
                    completed_at = excluded.completed_at,
                    duration_seconds = excluded.duration_seconds,
                    files_scanned = excluded.files_scanned,
                    experts_generated_json = excluded.experts_generated_json
            """, (scan_id, started_at, completed_at, duration_seconds, files_scanned,
                  scan_type, trigger, self.db.to_json(experts_generated or [])))
            return cursor.lastrowid

    def load_scan_meta(self) -> Optional[dict]:
        """Load most recent scan metadata."""
        row = self.db.fetchone(
            "SELECT * FROM scan_metadata ORDER BY started_at DESC LIMIT 1"
        )
        if row:
            row['experts_generated'] = self.db.from_json(row.get('experts_generated_json'), [])
        return row
