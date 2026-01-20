"""File knowledge service for business logic related to file-level scouting."""
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from pathlib import Path

from db import FileKnowledgeRepository
from core.knowledge_store import FileKnowledgeStore, FileKnowledge, FileScanResult


@dataclass
class FileOverview:
    """Summary of knowledge for a specific file."""
    file_path: str = ""
    file_name: str = ""
    exists: bool = False
    has_knowledge: bool = False
    language: str = ""
    size_bytes: int = 0
    line_count: int = 0
    last_scanned: str = ""
    classes_count: int = 0
    functions_count: int = 0
    imports_count: int = 0
    exports_count: int = 0
    summary: str = ""


@dataclass
class FilesSummary:
    """Summary of all scanned files."""
    total_files: int = 0
    total_size_bytes: int = 0
    total_lines: int = 0
    languages: Dict[str, int] = field(default_factory=dict)
    file_types: Dict[str, int] = field(default_factory=dict)
    last_scan_time: str = ""
    files: List[Dict] = field(default_factory=list)


@dataclass
class FileScanStatus:
    """Status of a file scout operation."""
    scan_id: str = ""
    file_path: str = ""
    status: str = "pending"  # pending, in_progress, completed, failed
    started_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0
    error: Optional[str] = None
    knowledge_saved: bool = False


class FileKnowledgeService:
    """Service for file-level knowledge operations.

    Encapsulates file knowledge retrieval, scouting triggers, and
    history tracking for the portal layer. Follows patterns from
    KnowledgeService for async wrapping.
    """

    def __init__(
        self,
        file_knowledge_repo: FileKnowledgeRepository,
        project_root: Path = None
    ):
        self.file_knowledge_repo = file_knowledge_repo
        self.project_root = project_root or Path.cwd()
        self._file_store = FileKnowledgeStore(self.project_root)

    async def get_file_overview(self, file_path: str) -> FileOverview:
        """Get summary of knowledge for a specific file.

        Returns a lightweight overview of the file's knowledge state
        including counts and basic file info.

        Args:
            file_path: Path to the file (relative or absolute)

        Returns:
            FileOverview with file knowledge summary
        """
        overview = FileOverview(file_path=file_path)

        # Normalize the file path
        normalized_path = self._normalize_path(file_path)
        overview.file_path = normalized_path
        overview.file_name = Path(normalized_path).name

        # Check if the physical file exists
        try:
            full_path = self._resolve_full_path(normalized_path)
            overview.exists = full_path.exists()
        except Exception:
            overview.exists = False

        # Check if knowledge exists
        knowledge_data = self.file_knowledge_repo.load_file_knowledge(normalized_path)
        if not knowledge_data:
            return overview

        overview.has_knowledge = True

        # Extract file info
        overview.language = knowledge_data.get("language", "")
        overview.size_bytes = knowledge_data.get("size_bytes", 0)
        overview.line_count = knowledge_data.get("line_count", 0)
        overview.last_scanned = knowledge_data.get("last_scanned", "")
        overview.summary = knowledge_data.get("summary", "")

        # Extract counts
        overview.classes_count = len(knowledge_data.get("classes", []))
        overview.functions_count = len(knowledge_data.get("functions", []))
        overview.imports_count = len(knowledge_data.get("imports", []))
        overview.exports_count = len(knowledge_data.get("exports", []))

        return overview

    async def get_all_files_summary(self) -> FilesSummary:
        """Get summary of all scanned files.

        Returns aggregate statistics and a list of all files
        with their basic knowledge info.

        Returns:
            FilesSummary with aggregate stats and file list
        """
        summary = FilesSummary()

        # Get all file knowledge
        all_files = self.file_knowledge_repo.get_all_file_knowledge()
        if not all_files:
            return summary

        summary.total_files = len(all_files)
        languages = {}
        file_types = {}
        latest_scan = ""
        files_list = []

        for file_data in all_files:
            # Aggregate size and lines
            summary.total_size_bytes += file_data.get("size_bytes", 0)
            summary.total_lines += file_data.get("line_count", 0)

            # Count by language
            lang = file_data.get("language", "unknown")
            languages[lang] = languages.get(lang, 0) + 1

            # Count by file type
            ftype = file_data.get("file_type", "unknown")
            file_types[ftype] = file_types.get(ftype, 0) + 1

            # Track latest scan
            scanned = file_data.get("last_scanned", "")
            if scanned and scanned > latest_scan:
                latest_scan = scanned

            # Add to files list
            files_list.append({
                "file_path": file_data.get("file_path", ""),
                "file_name": Path(file_data.get("file_path", "")).name,
                "language": lang,
                "size_bytes": file_data.get("size_bytes", 0),
                "line_count": file_data.get("line_count", 0),
                "last_scanned": scanned,
                "classes_count": len(file_data.get("classes", [])),
                "functions_count": len(file_data.get("functions", [])),
            })

        summary.languages = languages
        summary.file_types = file_types
        summary.last_scan_time = latest_scan
        summary.files = files_list

        return summary

    async def scout_file(self, file_path: str, trigger: str = "manual") -> FileScanStatus:
        """Trigger scouting for a specific file.

        Initiates file analysis and stores the results. This method
        performs basic file analysis (size, lines, language detection)
        and stores the results. For full AI-powered analysis, the
        CLI scout command should be used.

        Args:
            file_path: Path to the file to scout
            trigger: What triggered the scan ('manual', 'auto', 'watch')

        Returns:
            FileScanStatus with the operation result
        """
        scan_id = str(uuid.uuid4())[:8]
        started_at = datetime.now().isoformat()

        status = FileScanStatus(
            scan_id=scan_id,
            file_path=file_path,
            status="in_progress",
            started_at=started_at
        )

        try:
            # Normalize and resolve the path
            normalized_path = self._normalize_path(file_path)
            full_path = self._resolve_full_path(normalized_path)
            status.file_path = normalized_path

            # Verify file exists
            if not full_path.exists():
                status.status = "failed"
                status.error = f"File not found: {normalized_path}"
                status.completed_at = datetime.now().isoformat()
                return status

            if not full_path.is_file():
                status.status = "failed"
                status.error = f"Not a file: {normalized_path}"
                status.completed_at = datetime.now().isoformat()
                return status

            # Perform basic file analysis
            file_knowledge = await self._analyze_file(full_path, normalized_path)

            # Save the knowledge
            success = self._file_store.save(file_knowledge)
            if not success:
                status.status = "failed"
                status.error = "Failed to save file knowledge"
                status.completed_at = datetime.now().isoformat()
                return status

            # Record the scan
            completed_at = datetime.now().isoformat()
            start_dt = datetime.fromisoformat(started_at)
            end_dt = datetime.fromisoformat(completed_at)
            duration = (end_dt - start_dt).total_seconds()

            scan_result = FileScanResult(
                scan_id=scan_id,
                file_path=normalized_path,
                success=True,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration,
            )
            self._file_store.save_scan_result(scan_result)

            status.status = "completed"
            status.completed_at = completed_at
            status.duration_seconds = duration
            status.knowledge_saved = True

        except Exception as e:
            status.status = "failed"
            status.error = str(e)
            status.completed_at = datetime.now().isoformat()

            # Record failed scan
            scan_result = FileScanResult(
                scan_id=scan_id,
                file_path=file_path,
                success=False,
                started_at=started_at,
                completed_at=status.completed_at,
                error=str(e),
            )
            try:
                self._file_store.save_scan_result(scan_result)
            except Exception:
                pass  # Don't fail if we can't record the failed scan

        return status

    async def get_file_scan_history(
        self,
        file_path: str,
        limit: int = 10
    ) -> List[Dict]:
        """Get scan history for a specific file.

        Returns a list of previous scan records for the file,
        including timestamps, duration, and status.

        Args:
            file_path: Path to the file
            limit: Maximum number of records to return

        Returns:
            List of scan history records, most recent first
        """
        normalized_path = self._normalize_path(file_path)
        history = self._file_store.get_scan_history(normalized_path, limit)

        return [
            {
                "scan_id": scan.scan_id,
                "file_path": scan.file_path,
                "success": scan.success,
                "started_at": scan.started_at,
                "completed_at": scan.completed_at,
                "duration_seconds": scan.duration_seconds,
                "error": scan.error,
            }
            for scan in history
        ]

    async def clear_file_knowledge(self, file_path: str) -> bool:
        """Clear knowledge for a specific file.

        Removes all stored knowledge for the specified file.
        Does not affect scan history.

        Args:
            file_path: Path to the file

        Returns:
            True if knowledge was cleared, False otherwise
        """
        try:
            normalized_path = self._normalize_path(file_path)
            return self._file_store.delete(normalized_path)
        except Exception:
            return False

    async def get_full_file_knowledge(self, file_path: str) -> Optional[Dict]:
        """Get complete knowledge for a specific file.

        Returns the full knowledge data structure including
        imports, exports, classes, functions, and metadata.

        Args:
            file_path: Path to the file

        Returns:
            Dictionary with full file knowledge or None
        """
        normalized_path = self._normalize_path(file_path)
        knowledge = self._file_store.load(normalized_path)

        if not knowledge:
            return None

        return {
            "file_path": knowledge.file_path,
            "file_name": knowledge.file_name,
            "language": knowledge.language,
            "size_bytes": knowledge.size_bytes,
            "line_count": knowledge.line_count,
            "last_modified": knowledge.last_modified,
            "content_hash": knowledge.content_hash,
            "imports": knowledge.imports,
            "exports": knowledge.exports,
            "classes": knowledge.classes,
            "functions": knowledge.functions,
            "dependencies": knowledge.dependencies,
            "domain_hints": knowledge.domain_hints,
            "notes": knowledge.notes,
            "scouted_at": knowledge.scouted_at,
        }

    async def clear_all_file_knowledge(self) -> int:
        """Clear all file knowledge data.

        Removes all file knowledge and scan history.

        Returns:
            Number of file records deleted
        """
        try:
            return self._file_store.clear()
        except Exception:
            return 0

    # --- Private Helper Methods ---

    def _normalize_path(self, file_path: str) -> str:
        """Normalize a file path for consistent storage.

        Converts to forward slashes and makes relative to project root
        when possible.

        Args:
            file_path: Input path (relative or absolute)

        Returns:
            Normalized path string
        """
        path = Path(file_path)

        # If absolute, try to make relative to project root
        if path.is_absolute():
            try:
                path = path.relative_to(self.project_root)
            except ValueError:
                # Path is outside project root, keep as absolute
                pass

        # Convert to forward slashes for consistency
        return str(path).replace("\\", "/")

    def _resolve_full_path(self, normalized_path: str) -> Path:
        """Resolve a normalized path to an absolute path.

        Args:
            normalized_path: Normalized path string

        Returns:
            Absolute Path object
        """
        path = Path(normalized_path)
        if not path.is_absolute():
            path = self.project_root / path
        return path.resolve()

    async def _analyze_file(self, full_path: Path, normalized_path: str) -> FileKnowledge:
        """Perform basic file analysis.

        Extracts file metadata and basic structure information.
        This is a simple analysis; full AI-powered analysis happens
        in the CLI scout command.

        Args:
            full_path: Absolute path to the file
            normalized_path: Normalized relative path

        Returns:
            FileKnowledge with extracted information
        """
        import hashlib

        # Read file content
        try:
            content = full_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Binary file or encoding issue
            content = ""

        # Basic file stats
        stat = full_path.stat()
        size_bytes = stat.st_size
        line_count = len(content.splitlines()) if content else 0
        last_modified = datetime.fromtimestamp(stat.st_mtime).isoformat()

        # Content hash
        content_hash = hashlib.md5(content.encode()).hexdigest() if content else ""

        # Language detection based on extension
        language = self._detect_language(full_path)

        # Basic structure extraction (imports, classes, functions)
        imports = self._extract_imports(content, language)
        classes = self._extract_classes(content, language)
        functions = self._extract_functions(content, language)

        return FileKnowledge(
            file_path=normalized_path,
            file_name=full_path.name,
            language=language,
            size_bytes=size_bytes,
            line_count=line_count,
            last_modified=last_modified,
            content_hash=content_hash,
            imports=imports,
            exports=[],  # Would need AST analysis
            classes=classes,
            functions=functions,
            dependencies=[],  # Would need dependency analysis
            domain_hints=[],
            notes="",
        )

    def _detect_language(self, file_path: Path) -> str:
        """Detect programming language from file extension."""
        ext_map = {
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
            ".h": "c",
            ".hpp": "cpp",
            ".cs": "csharp",
            ".swift": "swift",
            ".kt": "kotlin",
            ".sql": "sql",
            ".html": "html",
            ".css": "css",
            ".scss": "scss",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".toml": "toml",
            ".xml": "xml",
            ".md": "markdown",
            ".sh": "shell",
            ".bash": "shell",
        }
        return ext_map.get(file_path.suffix.lower(), "unknown")

    def _extract_imports(self, content: str, language: str) -> List[str]:
        """Extract import statements from file content."""
        imports = []

        if language == "python":
            import re
            # Match 'import x' and 'from x import y'
            for match in re.finditer(r'^(?:from\s+([\w.]+)|import\s+([\w.]+))', content, re.MULTILINE):
                module = match.group(1) or match.group(2)
                if module:
                    imports.append(module)

        elif language in ("javascript", "typescript"):
            import re
            # Match 'import ... from "x"' and 'require("x")'
            for match in re.finditer(r'(?:import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]|require\([\'"]([^\'"]+)[\'"]\))', content):
                module = match.group(1) or match.group(2)
                if module:
                    imports.append(module)

        return imports[:50]  # Limit to prevent huge lists

    def _extract_classes(self, content: str, language: str) -> List[Dict]:
        """Extract class definitions from file content."""
        classes = []

        if language == "python":
            import re
            for match in re.finditer(r'^class\s+(\w+)(?:\([^)]*\))?:', content, re.MULTILINE):
                classes.append({
                    "name": match.group(1),
                    "line": content[:match.start()].count('\n') + 1
                })

        elif language in ("javascript", "typescript"):
            import re
            for match in re.finditer(r'(?:^|\s)class\s+(\w+)', content, re.MULTILINE):
                classes.append({
                    "name": match.group(1),
                    "line": content[:match.start()].count('\n') + 1
                })

        elif language == "java":
            import re
            for match in re.finditer(r'(?:public|private|protected)?\s*class\s+(\w+)', content):
                classes.append({
                    "name": match.group(1),
                    "line": content[:match.start()].count('\n') + 1
                })

        return classes[:30]  # Limit

    def _extract_functions(self, content: str, language: str) -> List[Dict]:
        """Extract function/method definitions from file content."""
        functions = []

        if language == "python":
            import re
            for match in re.finditer(r'^(?:async\s+)?def\s+(\w+)\s*\(', content, re.MULTILINE):
                functions.append({
                    "name": match.group(1),
                    "line": content[:match.start()].count('\n') + 1
                })

        elif language in ("javascript", "typescript"):
            import re
            # Match function declarations and arrow functions
            for match in re.finditer(r'(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)', content):
                name = match.group(1) or match.group(2)
                if name:
                    functions.append({
                        "name": name,
                        "line": content[:match.start()].count('\n') + 1
                    })

        return functions[:50]  # Limit
