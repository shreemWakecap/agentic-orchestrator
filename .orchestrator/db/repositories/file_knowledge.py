"""
File Knowledge Repository - ORM-based implementation.

Handles file-level knowledge storage and scan history using SQLAlchemy ORM.
"""
import json
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from ..connection import Database

from ..models import FileKnowledge, FileScanHistory


class FileKnowledgeRepository:
    """Repository for file-level knowledge operations using ORM."""

    def __init__(self, db: "Database"):
        self.db = db

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
        """Save or update file-level knowledge."""
        with self.db.session() as session:
            existing = session.query(FileKnowledge).filter_by(file_path=file_path).first()

            if existing:
                existing.file_type = file_type
                existing.language = language
                existing.size_bytes = size_bytes
                existing.line_count = line_count
                existing.imports_json = json.dumps(imports or [])
                existing.exports_json = json.dumps(exports or [])
                existing.classes_json = json.dumps(classes or [])
                existing.functions_json = json.dumps(functions or [])
                existing.dependencies_json = json.dumps(dependencies or [])
                existing.metadata_json = json.dumps(metadata or {})
                existing.summary = summary
                existing.last_scanned = datetime.now()
                return existing.id
            else:
                fk = FileKnowledge(
                    file_path=file_path,
                    file_type=file_type,
                    language=language,
                    size_bytes=size_bytes,
                    line_count=line_count,
                    imports_json=json.dumps(imports or []),
                    exports_json=json.dumps(exports or []),
                    classes_json=json.dumps(classes or []),
                    functions_json=json.dumps(functions or []),
                    dependencies_json=json.dumps(dependencies or []),
                    metadata_json=json.dumps(metadata or {}),
                    summary=summary,
                    last_scanned=datetime.now()
                )
                session.add(fk)
                session.flush()
                return fk.id

    def load_file_knowledge(self, file_path: str) -> Optional[dict]:
        """Load knowledge for a specific file."""
        with self.db.session() as session:
            fk = session.query(FileKnowledge).filter_by(file_path=file_path).first()
            if not fk:
                return None
            return self._file_knowledge_to_dict(fk)

    def get_all_file_knowledge(self) -> List[dict]:
        """Get knowledge for all scanned files."""
        with self.db.session() as session:
            files = session.query(FileKnowledge).order_by(FileKnowledge.last_scanned.desc()).all()
            return [self._file_knowledge_to_dict(f) for f in files]

    def delete_file_knowledge(self, file_path: str) -> bool:
        """Delete knowledge for a specific file."""
        with self.db.session() as session:
            deleted = session.query(FileKnowledge).filter_by(file_path=file_path).delete()
            return deleted > 0

    def exists(self, file_path: str) -> bool:
        """Check if knowledge exists for a specific file."""
        with self.db.session() as session:
            return session.query(FileKnowledge).filter_by(file_path=file_path).count() > 0

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
        """Save a file scan history record."""
        with self.db.session() as session:
            existing = session.query(FileScanHistory).filter_by(scan_id=scan_id).first()

            if existing:
                if completed_at:
                    existing.completed_at = datetime.fromisoformat(completed_at) if isinstance(completed_at, str) else completed_at
                existing.duration_seconds = duration_seconds
                existing.status = status
                existing.error_message = error_message
                existing.knowledge_id = knowledge_id
                return existing.id
            else:
                scan = FileScanHistory(
                    scan_id=scan_id,
                    file_path=file_path,
                    scan_type=scan_type,
                    trigger_type=trigger,
                    started_at=datetime.fromisoformat(started_at) if started_at else datetime.now(),
                    completed_at=datetime.fromisoformat(completed_at) if completed_at else None,
                    duration_seconds=duration_seconds,
                    status=status,
                    error_message=error_message,
                    knowledge_id=knowledge_id
                )
                session.add(scan)
                session.flush()
                return scan.id

    def get_file_scan_history(self, file_path: str, limit: int = 10) -> List[dict]:
        """Get scan history for a specific file."""
        with self.db.session() as session:
            scans = session.query(FileScanHistory).filter_by(
                file_path=file_path
            ).order_by(FileScanHistory.started_at.desc()).limit(limit).all()

            return [{
                'id': s.id,
                'scan_id': s.scan_id,
                'file_path': s.file_path,
                'scan_type': s.scan_type,
                'trigger_type': s.trigger_type,
                'started_at': s.started_at.isoformat() if s.started_at else None,
                'completed_at': s.completed_at.isoformat() if s.completed_at else None,
                'duration_seconds': s.duration_seconds,
                'status': s.status,
                'error_message': s.error_message,
                'knowledge_id': s.knowledge_id,
            } for s in scans]

    def clear_all_file_knowledge(self) -> int:
        """Clear all file knowledge and scan history."""
        with self.db.session() as session:
            count = session.query(FileKnowledge).count()
            session.query(FileScanHistory).delete()
            session.query(FileKnowledge).delete()
            return count

    def search_by_function_name(self, name: str) -> List[dict]:
        """Search for files containing functions matching the given name."""
        with self.db.session() as session:
            # Use LIKE for text search in JSON
            pattern = f'%"name": "{name}%'
            pattern_alt = f'%"name":"{name}%'

            files = session.query(FileKnowledge).filter(
                (FileKnowledge.functions_json.like(pattern)) |
                (FileKnowledge.functions_json.like(pattern_alt))
            ).order_by(FileKnowledge.last_scanned.desc()).all()

            results = []
            for fk in files:
                formatted = self._file_knowledge_to_dict(fk)
                matching_functions = [
                    f for f in formatted['functions']
                    if isinstance(f, dict) and name.lower() in f.get('name', '').lower()
                ]
                if matching_functions:
                    formatted['matching_functions'] = matching_functions
                    results.append(formatted)

            return results

    def search_by_class_name(self, name: str) -> List[dict]:
        """Search for files containing classes matching the given name."""
        with self.db.session() as session:
            pattern = f'%"name": "{name}%'
            pattern_alt = f'%"name":"{name}%'

            files = session.query(FileKnowledge).filter(
                (FileKnowledge.classes_json.like(pattern)) |
                (FileKnowledge.classes_json.like(pattern_alt))
            ).order_by(FileKnowledge.last_scanned.desc()).all()

            results = []
            for fk in files:
                formatted = self._file_knowledge_to_dict(fk)
                matching_classes = [
                    c for c in formatted['classes']
                    if isinstance(c, dict) and name.lower() in c.get('name', '').lower()
                ]
                if matching_classes:
                    formatted['matching_classes'] = matching_classes
                    results.append(formatted)

            return results

    def search_by_import(self, module: str) -> List[dict]:
        """Search for files that import the given module."""
        with self.db.session() as session:
            pattern = f'%{module}%'

            files = session.query(FileKnowledge).filter(
                FileKnowledge.imports_json.like(pattern)
            ).order_by(FileKnowledge.last_scanned.desc()).all()

            results = []
            for fk in files:
                formatted = self._file_knowledge_to_dict(fk)
                matching_imports = [
                    imp for imp in formatted['imports']
                    if module.lower() in str(imp).lower()
                ]
                if matching_imports:
                    formatted['matching_imports'] = matching_imports
                    results.append(formatted)

            return results

    def get_files_by_language(self, language: str) -> List[dict]:
        """Get all files written in a specific programming language."""
        with self.db.session() as session:
            from sqlalchemy import func
            files = session.query(FileKnowledge).filter(
                func.lower(FileKnowledge.language) == language.lower()
            ).order_by(FileKnowledge.file_path).all()

            return [self._file_knowledge_to_dict(f) for f in files]

    def search_by_content_summary(self, query: str) -> List[dict]:
        """Search files by their content summary."""
        with self.db.session() as session:
            pattern = f'%{query}%'

            files = session.query(FileKnowledge).filter(
                FileKnowledge.summary.like(pattern)
            ).order_by(FileKnowledge.last_scanned.desc()).all()

            return [self._file_knowledge_to_dict(f) for f in files]

    def _file_knowledge_to_dict(self, fk: FileKnowledge) -> dict:
        """Convert FileKnowledge model to dictionary."""
        return {
            'id': fk.id,
            'file_path': fk.file_path,
            'file_type': fk.file_type,
            'language': fk.language,
            'size_bytes': fk.size_bytes,
            'line_count': fk.line_count,
            'imports': json.loads(fk.imports_json or '[]'),
            'exports': json.loads(fk.exports_json or '[]'),
            'classes': json.loads(fk.classes_json or '[]'),
            'functions': json.loads(fk.functions_json or '[]'),
            'dependencies': json.loads(fk.dependencies_json or '[]'),
            'metadata': json.loads(fk.metadata_json or '{}'),
            'summary': fk.summary,
            'last_scanned': fk.last_scanned.isoformat() if fk.last_scanned else None,
        }
