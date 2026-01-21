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

    # --- Search Methods for Codebase Explorer ---

    def search_domains_by_keyword(self, keywords: list[str]) -> list[dict]:
        """Search domains that match any of the given keywords.

        Args:
            keywords: List of keywords to search for in domain keywords.

        Returns:
            List of matching domains with their details.
        """
        if not keywords:
            return []

        # Get knowledge ID first
        knowledge_row = self.db.fetchone("SELECT id FROM codebase_knowledge LIMIT 1")
        if not knowledge_row:
            return []

        knowledge_id = knowledge_row['id']

        # Fetch all domains and filter by keywords
        domain_rows = self.db.fetchall(
            "SELECT * FROM domains WHERE knowledge_id = ?", (knowledge_id,)
        )

        results = []
        keywords_lower = [kw.lower() for kw in keywords]

        for d in domain_rows:
            domain_keywords = self.db.from_json(d['keywords_json'], [])
            domain_keywords_lower = [dk.lower() for dk in domain_keywords]

            # Check if any search keyword matches domain keywords
            matching_keywords = [
                kw for kw in keywords_lower
                if any(kw in dk or dk in kw for dk in domain_keywords_lower)
            ]

            if matching_keywords:
                results.append({
                    'name': d['name'],
                    'keywords': domain_keywords,
                    'files': self.db.from_json(d['files_json'], []),
                    'models': self.db.from_json(d['models_json'], []),
                    'routes': self.db.from_json(d['routes_json'], []),
                    'matched_keywords': matching_keywords,
                })

        return results

    def search_modules_by_path(self, path_pattern: str) -> list[dict]:
        """Search modules whose path matches the given pattern.

        Args:
            path_pattern: Pattern to match against module paths (case-insensitive substring match).

        Returns:
            List of matching modules with their details.
        """
        if not path_pattern:
            return []

        # Get knowledge ID first
        knowledge_row = self.db.fetchone("SELECT id FROM codebase_knowledge LIMIT 1")
        if not knowledge_row:
            return []

        knowledge_id = knowledge_row['id']

        # Fetch all modules and filter by path pattern
        module_rows = self.db.fetchall(
            "SELECT * FROM architecture_modules WHERE knowledge_id = ?", (knowledge_id,)
        )

        results = []
        pattern_lower = path_pattern.lower()

        for m in module_rows:
            module_path = m['path'] or ''
            module_name = m['name'] or ''

            # Check if pattern matches path or name
            if pattern_lower in module_path.lower() or pattern_lower in module_name.lower():
                results.append({
                    'name': m['name'],
                    'path': m['path'],
                    'purpose': m['purpose'],
                    'depends_on': self.db.from_json(m['depends_on_json'], []),
                })

        return results

    def get_technologies(self) -> dict:
        """Get all technologies (languages, frameworks, tools) from knowledge store.

        Returns:
            Dictionary with 'languages', 'frameworks', and 'tools' lists.
        """
        # Get knowledge ID first
        knowledge_row = self.db.fetchone("SELECT id FROM codebase_knowledge LIMIT 1")
        if not knowledge_row:
            return {'languages': [], 'frameworks': [], 'tools': []}

        knowledge_id = knowledge_row['id']

        # Fetch all technologies
        tech_rows = self.db.fetchall(
            "SELECT * FROM technologies WHERE knowledge_id = ?", (knowledge_id,)
        )

        languages = []
        frameworks = []
        tools = []

        for t in tech_rows:
            tech_data = {
                'name': t['name'],
                'confidence': t['confidence'],
            }

            if t['tech_type'] == 'language':
                tech_data['version'] = t['version']
                languages.append(tech_data)
            elif t['tech_type'] == 'framework':
                tech_data['entry_point'] = t['entry_point']
                tech_data['config_file'] = t['config_file']
                frameworks.append(tech_data)
            elif t['tech_type'] == 'tool':
                tech_data['config_file'] = t['config_file']
                tools.append(tech_data)

        return {
            'languages': languages,
            'frameworks': frameworks,
            'tools': tools,
        }

    def get_conventions(self) -> dict:
        """Get coding conventions and patterns from knowledge store.

        Returns:
            Dictionary with 'naming', 'structure', and 'conventions' data.
        """
        # Get knowledge ID first
        knowledge_row = self.db.fetchone("SELECT id FROM codebase_knowledge LIMIT 1")
        if not knowledge_row:
            return {'naming': {}, 'structure': {}, 'conventions': []}

        knowledge_id = knowledge_row['id']

        # Fetch patterns
        pattern_row = self.db.fetchone(
            "SELECT * FROM patterns WHERE knowledge_id = ?", (knowledge_id,)
        )

        if not pattern_row:
            return {'naming': {}, 'structure': {}, 'conventions': []}

        return {
            'naming': self.db.from_json(pattern_row['naming_json'], {}),
            'structure': self.db.from_json(pattern_row['structure_json'], {}),
            'conventions': self.db.from_json(pattern_row['conventions_json'], []),
        }

    # --- Coding Rules ---

    def save_coding_rule(self, rule) -> int:
        """Save a coding rule to the database.

        Args:
            rule: CodingRule object with id, category, rule, severity, examples, source_files, confidence

        Returns:
            Row ID of the inserted/updated rule.
        """
        with self.db.transaction() as conn:
            # Get knowledge ID
            knowledge_row = conn.execute("SELECT id FROM codebase_knowledge LIMIT 1").fetchone()
            knowledge_id = knowledge_row['id'] if knowledge_row else None

            cursor = conn.execute("""
                INSERT INTO coding_rules (knowledge_id, rule_id, category, rule_text, severity,
                                         examples_json, source_files_json, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(rule_id) DO UPDATE SET
                    category = excluded.category,
                    rule_text = excluded.rule_text,
                    severity = excluded.severity,
                    examples_json = excluded.examples_json,
                    source_files_json = excluded.source_files_json,
                    confidence = MAX(coding_rules.confidence, excluded.confidence),
                    updated_at = CURRENT_TIMESTAMP
            """, (
                knowledge_id,
                rule.id,
                rule.category,
                rule.rule,
                rule.severity,
                self.db.to_json(rule.examples),
                self.db.to_json(rule.source_files),
                rule.confidence
            ))
            return cursor.lastrowid

    def get_coding_rules(self, category: str = None, min_confidence: float = 0.0) -> list[dict]:
        """Get coding rules from the database.

        Args:
            category: Optional category filter (naming, structure, patterns, etc.)
            min_confidence: Minimum confidence threshold (0.0 - 1.0)

        Returns:
            List of coding rule dictionaries.
        """
        query = "SELECT * FROM coding_rules WHERE confidence >= ?"
        params = [min_confidence]

        if category:
            query += " AND category = ?"
            params.append(category)

        query += " ORDER BY severity DESC, confidence DESC"

        rows = self.db.fetchall(query, tuple(params))

        return [{
            'id': r['rule_id'],
            'category': r['category'],
            'rule': r['rule_text'],
            'severity': r['severity'],
            'examples': self.db.from_json(r['examples_json'], []),
            'source_files': self.db.from_json(r['source_files_json'], []),
            'confidence': r['confidence'],
        } for r in rows]

    def delete_coding_rule(self, rule_id: str) -> bool:
        """Delete a coding rule by its ID.

        Args:
            rule_id: The rule ID to delete.

        Returns:
            True if a rule was deleted, False otherwise.
        """
        with self.db.transaction() as conn:
            cursor = conn.execute("DELETE FROM coding_rules WHERE rule_id = ?", (rule_id,))
            return cursor.rowcount > 0

    def clear_coding_rules(self):
        """Clear all coding rules."""
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM coding_rules")

    # --- Extended Scan Metadata (with Git State) ---

    def save_scan_metadata(self, metadata: dict) -> int:
        """Save extended scan metadata including git state.

        Args:
            metadata: Dictionary with keys:
                - git_commit_hash: Current HEAD commit hash
                - git_branch: Current branch name
                - scanned_paths: List of paths that were scanned
                - trigger: What triggered the scan (manual, auto, post_build)
                - scan_time: ISO timestamp of the scan
                - mode: full or incremental

        Returns:
            Row ID of the inserted record.
        """
        with self.db.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO extended_scan_metadata
                    (git_commit_hash, git_branch, scanned_paths_json, trigger_type,
                     scan_time, scan_mode)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                metadata.get('git_commit_hash'),
                metadata.get('git_branch'),
                self.db.to_json(metadata.get('scanned_paths', [])),
                metadata.get('trigger', 'manual'),
                metadata.get('scan_time', datetime.now().isoformat()),
                metadata.get('mode', 'full')
            ))
            return cursor.lastrowid

    def get_scan_metadata(self) -> Optional[dict]:
        """Get the most recent extended scan metadata.

        Returns:
            Dictionary with git_commit_hash, git_branch, scanned_paths, etc.
        """
        row = self.db.fetchone("""
            SELECT * FROM extended_scan_metadata
            ORDER BY scan_time DESC LIMIT 1
        """)

        if not row:
            return None

        return {
            'id': row['id'],
            'git_commit_hash': row['git_commit_hash'],
            'git_branch': row['git_branch'],
            'scanned_paths': self.db.from_json(row['scanned_paths_json'], []),
            'trigger': row['trigger_type'],
            'scan_time': row['scan_time'],
            'mode': row['scan_mode'],
        }

    def get_scan_history(self, limit: int = 10) -> list[dict]:
        """Get recent scan history.

        Args:
            limit: Maximum number of records to return.

        Returns:
            List of scan metadata dictionaries.
        """
        rows = self.db.fetchall("""
            SELECT * FROM extended_scan_metadata
            ORDER BY scan_time DESC LIMIT ?
        """, (limit,))

        return [{
            'id': r['id'],
            'git_commit_hash': r['git_commit_hash'],
            'git_branch': r['git_branch'],
            'scanned_paths': self.db.from_json(r['scanned_paths_json'], []),
            'trigger': r['trigger_type'],
            'scan_time': r['scan_time'],
            'mode': r['scan_mode'],
        } for r in rows]
