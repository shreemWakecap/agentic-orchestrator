"""
File Knowledge Repository.

Handles file-level knowledge storage and scan history for targeted file scouting.
"""
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

from .base import BaseRepository

if TYPE_CHECKING:
    from ..connection import Database


class FileKnowledgeRepository(BaseRepository):
    """Repository for file-level knowledge operations."""

    # Fields that need JSON serialization/deserialization
    JSON_FIELDS: List[str] = [
        "imports", "exports", "classes", "functions", "dependencies", "metadata"
    ]

    # Allowed columns for dynamic updates
    ALLOWED_UPDATE_COLUMNS = {
        "file_type", "language", "size_bytes", "line_count",
        "imports_json", "exports_json", "classes_json", "functions_json",
        "dependencies_json", "metadata_json", "summary", "last_scanned"
    }

    def __init__(self, db: "Database"):
        super().__init__(db)

    def save_file_knowledge(
        self,
        file_path: str,
        file_type: str,
        language: str,
        size_bytes: int,
        line_count: int,
        imports: List[str] = None,
        exports: List[str] = None,
        classes: List[dict] = None,
        functions: List[dict] = None,
        dependencies: List[str] = None,
        metadata: dict = None,
        summary: str = None
    ) -> int:
        """Save or update file-level knowledge.

        Args:
            file_path: Absolute or relative path to the file
            file_type: Type of file (e.g., 'python', 'javascript', 'config')
            language: Programming language or format
            size_bytes: File size in bytes
            line_count: Number of lines in file
            imports: List of imported modules/packages
            exports: List of exported symbols
            classes: List of class definitions with metadata
            functions: List of function definitions with metadata
            dependencies: List of file dependencies
            metadata: Additional file-specific metadata
            summary: AI-generated summary of file purpose

        Returns:
            Row ID of the saved record
        """
        now = datetime.now().isoformat()

        with self.db.transaction() as conn:
            # Check if file knowledge already exists
            existing = conn.execute(
                "SELECT id FROM file_knowledge WHERE file_path = ?",
                (file_path,)
            ).fetchone()

            if existing:
                # Update existing record
                cursor = conn.execute("""
                    UPDATE file_knowledge SET
                        file_type = ?,
                        language = ?,
                        size_bytes = ?,
                        line_count = ?,
                        imports_json = ?,
                        exports_json = ?,
                        classes_json = ?,
                        functions_json = ?,
                        dependencies_json = ?,
                        metadata_json = ?,
                        summary = ?,
                        last_scanned = ?
                    WHERE file_path = ?
                """, (
                    file_type,
                    language,
                    size_bytes,
                    line_count,
                    self.db.to_json(imports or []),
                    self.db.to_json(exports or []),
                    self.db.to_json(classes or []),
                    self.db.to_json(functions or []),
                    self.db.to_json(dependencies or []),
                    self.db.to_json(metadata or {}),
                    summary,
                    now,
                    file_path
                ))
                return existing['id'] if isinstance(existing, dict) else existing[0]
            else:
                # Insert new record
                cursor = conn.execute("""
                    INSERT INTO file_knowledge (
                        file_path, file_type, language, size_bytes, line_count,
                        imports_json, exports_json, classes_json, functions_json,
                        dependencies_json, metadata_json, summary, last_scanned
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    file_path,
                    file_type,
                    language,
                    size_bytes,
                    line_count,
                    self.db.to_json(imports or []),
                    self.db.to_json(exports or []),
                    self.db.to_json(classes or []),
                    self.db.to_json(functions or []),
                    self.db.to_json(dependencies or []),
                    self.db.to_json(metadata or {}),
                    summary,
                    now
                ))
                return cursor.lastrowid

    def load_file_knowledge(self, file_path: str) -> Optional[dict]:
        """Load knowledge for a specific file.

        Args:
            file_path: Path to the file

        Returns:
            Dictionary with file knowledge or None if not found
        """
        row = self.db.fetchone(
            "SELECT * FROM file_knowledge WHERE file_path = ?",
            (file_path,)
        )

        if not row:
            return None

        return self._format_file_knowledge(row)

    def get_all_file_knowledge(self) -> List[dict]:
        """Get knowledge for all scanned files.

        Returns:
            List of file knowledge dictionaries
        """
        rows = self.db.fetchall(
            "SELECT * FROM file_knowledge ORDER BY last_scanned DESC"
        )

        return [self._format_file_knowledge(row) for row in rows]

    def delete_file_knowledge(self, file_path: str) -> bool:
        """Delete knowledge for a specific file.

        Args:
            file_path: Path to the file

        Returns:
            True if a record was deleted, False otherwise
        """
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM file_knowledge WHERE file_path = ?",
                (file_path,)
            )
            return cursor.rowcount > 0

    def exists(self, file_path: str) -> bool:
        """Check if knowledge exists for a specific file.

        Args:
            file_path: Path to the file

        Returns:
            True if knowledge exists, False otherwise
        """
        row = self.db.fetchone(
            "SELECT COUNT(*) as count FROM file_knowledge WHERE file_path = ?",
            (file_path,)
        )
        return row and row['count'] > 0

    def save_file_scan(
        self,
        scan_id: str,
        file_path: str,
        scan_type: str = "single",
        trigger: str = "manual",
        started_at: str = None,
        completed_at: str = None,
        duration_seconds: float = 0,
        status: str = "completed",
        error_message: str = None,
        knowledge_id: int = None
    ) -> int:
        """Save a file scan history record.

        Args:
            scan_id: Unique identifier for the scan
            file_path: Path to the scanned file
            scan_type: Type of scan ('single', 'batch', 'watch')
            trigger: What triggered the scan ('manual', 'auto', 'watch')
            started_at: ISO timestamp when scan started
            completed_at: ISO timestamp when scan completed
            duration_seconds: How long the scan took
            status: Scan status ('pending', 'in_progress', 'completed', 'failed')
            error_message: Error message if scan failed
            knowledge_id: ID of the file_knowledge record created

        Returns:
            Row ID of the saved record
        """
        now = datetime.now().isoformat()
        started_at = started_at or now

        with self.db.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO file_scan_history (
                    scan_id, file_path, scan_type, trigger_type,
                    started_at, completed_at, duration_seconds,
                    status, error_message, knowledge_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(scan_id) DO UPDATE SET
                    completed_at = excluded.completed_at,
                    duration_seconds = excluded.duration_seconds,
                    status = excluded.status,
                    error_message = excluded.error_message,
                    knowledge_id = excluded.knowledge_id
            """, (
                scan_id,
                file_path,
                scan_type,
                trigger,
                started_at,
                completed_at,
                duration_seconds,
                status,
                error_message,
                knowledge_id
            ))
            return cursor.lastrowid

    def get_file_scan_history(self, file_path: str, limit: int = 10) -> List[dict]:
        """Get scan history for a specific file.

        Args:
            file_path: Path to the file
            limit: Maximum number of records to return

        Returns:
            List of scan history records, most recent first
        """
        rows = self.db.fetchall(
            """SELECT * FROM file_scan_history
               WHERE file_path = ?
               ORDER BY started_at DESC
               LIMIT ?""",
            (file_path, limit)
        )
        return list(rows) if rows else []

    def clear_all_file_knowledge(self) -> int:
        """Clear all file knowledge and scan history.

        Returns:
            Number of file knowledge records deleted
        """
        with self.db.transaction() as conn:
            # Get count before deletion
            count_row = conn.execute(
                "SELECT COUNT(*) as count FROM file_knowledge"
            ).fetchone()
            count = count_row['count'] if isinstance(count_row, dict) else count_row[0]

            # Clear both tables
            conn.execute("DELETE FROM file_scan_history")
            conn.execute("DELETE FROM file_knowledge")

            return count

    def search_by_function_name(self, name: str) -> List[dict]:
        """Search for files containing functions matching the given name.

        Args:
            name: Function name or partial name to search for (case-insensitive)

        Returns:
            List of file knowledge records containing matching functions
        """
        # Use LIKE for SQLite JSON text search
        pattern = f'%"name": "{name}%'
        pattern_alt = f'%"name":"{name}%'

        rows = self.db.fetchall(
            """SELECT * FROM file_knowledge
               WHERE functions_json LIKE ? OR functions_json LIKE ?
               ORDER BY last_scanned DESC""",
            (pattern, pattern_alt)
        )

        results = []
        for row in rows:
            formatted = self._format_file_knowledge(row)
            # Filter to only include matching functions in result
            matching_functions = [
                f for f in formatted['functions']
                if isinstance(f, dict) and name.lower() in f.get('name', '').lower()
            ]
            if matching_functions:
                formatted['matching_functions'] = matching_functions
                results.append(formatted)

        return results

    def search_by_class_name(self, name: str) -> List[dict]:
        """Search for files containing classes matching the given name.

        Args:
            name: Class name or partial name to search for (case-insensitive)

        Returns:
            List of file knowledge records containing matching classes
        """
        # Use LIKE for SQLite JSON text search
        pattern = f'%"name": "{name}%'
        pattern_alt = f'%"name":"{name}%'

        rows = self.db.fetchall(
            """SELECT * FROM file_knowledge
               WHERE classes_json LIKE ? OR classes_json LIKE ?
               ORDER BY last_scanned DESC""",
            (pattern, pattern_alt)
        )

        results = []
        for row in rows:
            formatted = self._format_file_knowledge(row)
            # Filter to only include matching classes in result
            matching_classes = [
                c for c in formatted['classes']
                if isinstance(c, dict) and name.lower() in c.get('name', '').lower()
            ]
            if matching_classes:
                formatted['matching_classes'] = matching_classes
                results.append(formatted)

        return results

    def search_by_import(self, module: str) -> List[dict]:
        """Search for files that import the given module.

        Args:
            module: Module name or partial name to search for (case-insensitive)

        Returns:
            List of file knowledge records that import the module
        """
        # Search in imports_json for the module name
        pattern = f'%{module}%'

        rows = self.db.fetchall(
            """SELECT * FROM file_knowledge
               WHERE imports_json LIKE ?
               ORDER BY last_scanned DESC""",
            (pattern,)
        )

        results = []
        for row in rows:
            formatted = self._format_file_knowledge(row)
            # Filter to only include matching imports in result
            matching_imports = [
                imp for imp in formatted['imports']
                if module.lower() in str(imp).lower()
            ]
            if matching_imports:
                formatted['matching_imports'] = matching_imports
                results.append(formatted)

        return results

    def get_files_by_language(self, language: str) -> List[dict]:
        """Get all files written in a specific programming language.

        Args:
            language: Programming language to filter by (case-insensitive)

        Returns:
            List of file knowledge records for files in that language
        """
        rows = self.db.fetchall(
            """SELECT * FROM file_knowledge
               WHERE LOWER(language) = LOWER(?)
               ORDER BY file_path ASC""",
            (language,)
        )

        return [self._format_file_knowledge(row) for row in rows]

    def search_by_content_summary(self, query: str) -> List[dict]:
        """Search files by their content summary.

        Args:
            query: Search query to match against file summaries (case-insensitive)

        Returns:
            List of file knowledge records with matching summaries
        """
        pattern = f'%{query}%'

        rows = self.db.fetchall(
            """SELECT * FROM file_knowledge
               WHERE summary LIKE ?
               ORDER BY last_scanned DESC""",
            (pattern,)
        )

        return [self._format_file_knowledge(row) for row in rows]

    def _format_file_knowledge(self, row: dict) -> dict:
        """Format a file knowledge database row into a structured dictionary.

        Args:
            row: Database row dictionary

        Returns:
            Formatted file knowledge dictionary
        """
        return {
            'id': row['id'],
            'file_path': row['file_path'],
            'file_type': row['file_type'],
            'language': row['language'],
            'size_bytes': row['size_bytes'],
            'line_count': row['line_count'],
            'imports': self.db.from_json(row.get('imports_json'), []),
            'exports': self.db.from_json(row.get('exports_json'), []),
            'classes': self.db.from_json(row.get('classes_json'), []),
            'functions': self.db.from_json(row.get('functions_json'), []),
            'dependencies': self.db.from_json(row.get('dependencies_json'), []),
            'metadata': self.db.from_json(row.get('metadata_json'), {}),
            'summary': row.get('summary'),
            'last_scanned': row['last_scanned'],
        }
