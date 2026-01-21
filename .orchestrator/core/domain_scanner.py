"""
Domain Scanner: Technology-agnostic project structure detection.

Scans the project root to detect domains/modules without assuming
any specific technology stack.
"""
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.knowledge_store import DetectedDomain
from core.config import get_agent_config

logger = logging.getLogger(__name__)


# File extension to language mapping
EXTENSION_TO_LANGUAGE = {
    # .NET / C#
    ".cs": "csharp",
    ".csproj": "csharp",
    ".sln": "csharp",
    ".fs": "fsharp",
    ".vb": "vbnet",
    # Python
    ".py": "python",
    ".pyx": "python",
    ".pyi": "python",
    # JavaScript / TypeScript
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    # Java / Kotlin
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    # Go
    ".go": "go",
    # Rust
    ".rs": "rust",
    # Ruby
    ".rb": "ruby",
    # PHP
    ".php": "php",
    # Swift
    ".swift": "swift",
    # C/C++
    ".c": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    # Other
    ".scala": "scala",
    ".dart": "dart",
    ".r": "r",
    ".lua": "lua",
    ".pl": "perl",
    ".ex": "elixir",
    ".exs": "elixir",
    ".clj": "clojure",
    ".hs": "haskell",
}

# Directories to always exclude
DEFAULT_EXCLUDES = {
    ".orchestrator", ".git", ".svn", ".hg",
    "node_modules", ".venv", "venv", "__pycache__",
    "dist", "build", "out", "target",
    "bin", "obj", ".vs", ".idea", ".vscode",
    "packages", ".nuget", "coverage",
    ".next", ".turbo", ".cache",
}

# Classification patterns
GENERATED_PATTERNS = {
    "node_modules", "dist", "build", "out", "target",
    "bin", "obj", ".next", "coverage", "__pycache__",
    ".turbo", ".cache", "packages", ".nuget",
}

DOCS_PATTERNS = {
    "docs", "documentation", "doc", "wiki", "manual",
}

CONFIG_PATTERNS = {
    ".github", ".gitlab", ".circleci", "scripts",
    "tools", "infra", "infrastructure", "deploy",
    ".devcontainer", "terraform", "helm", "k8s",
}


@dataclass
class ScanConfig:
    """Configuration for domain scanning."""
    exclude_paths: set[str]
    max_depth: int = 3
    min_files_for_code: int = 1
    sample_file_limit: int = 100


class DomainScanner:
    """
    Scans project structure to detect domains without technology assumptions.

    Usage:
        scanner = DomainScanner(project_root)
        domains = scanner.detect_domains()

        for domain in domains:
            print(f"{domain.name}: {domain.classification} ({domain.file_count} files)")
    """

    def __init__(self, project_root: Path, config: Optional[ScanConfig] = None):
        self.project_root = project_root.resolve()
        self.config = config or self._load_config()

    def _load_config(self) -> ScanConfig:
        """Load scan config from agent.json or use defaults."""
        try:
            agent_config = get_agent_config(self.project_root)
            scan_config = agent_config.get("scan", {})
            exclude_paths = set(scan_config.get("exclude_paths", DEFAULT_EXCLUDES))
        except Exception:
            exclude_paths = DEFAULT_EXCLUDES

        return ScanConfig(exclude_paths=exclude_paths)

    def detect_domains(self) -> list[DetectedDomain]:
        """
        Detect all domains/modules in the project.

        Returns list of DetectedDomain with classification and metadata.
        """
        domains = []

        # Get first-level directories (these are potential domains)
        try:
            for item in self.project_root.iterdir():
                if not item.is_dir():
                    continue

                name = item.name

                # Skip excluded paths
                if name in self.config.exclude_paths:
                    continue

                # Analyze this directory
                domain = self._analyze_directory(item)
                if domain:
                    domains.append(domain)

        except PermissionError as e:
            logger.warning(f"Permission denied scanning {self.project_root}: {e}")
        except Exception as e:
            logger.error(f"Error scanning project root: {e}")

        # Sort by classification priority: code first, then config, docs, others
        classification_order = {"code": 0, "config": 1, "docs": 2, "unknown": 3, "generated": 4}
        domains.sort(key=lambda d: (classification_order.get(d.classification, 5), d.name))

        return domains

    def _analyze_directory(self, path: Path) -> Optional[DetectedDomain]:
        """Analyze a single directory and return DetectedDomain."""
        name = path.name

        # Quick classification based on name patterns
        classification = self._classify_by_name(name)

        # If generated, skip detailed analysis
        if classification == "generated":
            return DetectedDomain(
                path=str(path.relative_to(self.project_root)),
                name=name,
                classification="generated",
                file_count=0,
                subdirectory_count=0,
                detected_languages=[],
                confidence=0.9,
            )

        # Count files and detect languages
        file_count = 0
        subdir_count = 0
        language_counts: dict[str, int] = {}

        try:
            for item in self._walk_limited(path, max_depth=2, max_files=self.config.sample_file_limit):
                if item.is_file():
                    file_count += 1
                    ext = item.suffix.lower()
                    if ext in EXTENSION_TO_LANGUAGE:
                        lang = EXTENSION_TO_LANGUAGE[ext]
                        language_counts[lang] = language_counts.get(lang, 0) + 1
                elif item.is_dir() and item.parent == path:
                    subdir_count += 1
        except PermissionError:
            pass
        except Exception as e:
            logger.debug(f"Error analyzing {path}: {e}")

        # Determine classification if not already set
        if classification == "unknown":
            if language_counts:
                classification = "code"
            elif file_count > 0:
                # Check if mostly config/doc files
                classification = self._classify_by_content(path)

        # Get top languages
        detected_languages = sorted(
            language_counts.keys(),
            key=lambda l: language_counts[l],
            reverse=True
        )[:3]

        # Calculate confidence
        confidence = self._calculate_confidence(classification, file_count, language_counts)

        return DetectedDomain(
            path=str(path.relative_to(self.project_root)),
            name=name,
            classification=classification,
            file_count=file_count,
            subdirectory_count=subdir_count,
            detected_languages=detected_languages,
            confidence=confidence,
        )

    def _classify_by_name(self, name: str) -> str:
        """Classify directory by its name."""
        name_lower = name.lower()

        if name_lower in GENERATED_PATTERNS or name.startswith("."):
            return "generated"

        if name_lower in DOCS_PATTERNS:
            return "docs"

        if name_lower in CONFIG_PATTERNS:
            return "config"

        return "unknown"

    def _classify_by_content(self, path: Path) -> str:
        """Classify directory by examining its content."""
        try:
            # Sample some files
            md_count = 0
            config_count = 0
            total = 0

            for item in path.iterdir():
                if not item.is_file():
                    continue
                total += 1
                if total > 20:
                    break

                ext = item.suffix.lower()
                name = item.name.lower()

                if ext in {".md", ".rst", ".txt", ".adoc"}:
                    md_count += 1
                elif ext in {".json", ".yaml", ".yml", ".toml", ".xml", ".ini", ".cfg"}:
                    config_count += 1
                elif name in {"readme", "changelog", "license", "contributing"}:
                    md_count += 1

            if total == 0:
                return "unknown"

            if md_count / total > 0.5:
                return "docs"
            if config_count / total > 0.5:
                return "config"

        except Exception:
            pass

        return "unknown"

    def _calculate_confidence(
        self,
        classification: str,
        file_count: int,
        language_counts: dict[str, int]
    ) -> float:
        """Calculate confidence score for the classification."""
        if classification == "generated":
            return 0.95

        if classification == "code":
            # More code files = higher confidence
            total_code_files = sum(language_counts.values())
            if total_code_files > 50:
                return 0.95
            elif total_code_files > 10:
                return 0.85
            elif total_code_files > 3:
                return 0.75
            else:
                return 0.6

        if classification == "docs":
            return 0.8

        if classification == "config":
            return 0.75

        # Unknown
        return 0.5

    def _walk_limited(self, path: Path, max_depth: int, max_files: int):
        """Walk directory with depth and file limits."""
        count = 0

        def _walk(current: Path, depth: int):
            nonlocal count
            if depth > max_depth or count >= max_files:
                return

            try:
                for item in current.iterdir():
                    if count >= max_files:
                        return

                    # Skip excluded
                    if item.name in self.config.exclude_paths:
                        continue

                    yield item
                    count += 1

                    if item.is_dir() and depth < max_depth:
                        yield from _walk(item, depth + 1)
            except PermissionError:
                pass

        yield from _walk(path, 0)

    def get_summary(self, domains: list[DetectedDomain]) -> str:
        """Generate a human-readable summary of detected domains."""
        if not domains:
            return "No domains detected."

        lines = ["Detected domains:", ""]

        # Group by classification
        by_class: dict[str, list[DetectedDomain]] = {}
        for d in domains:
            by_class.setdefault(d.classification, []).append(d)

        class_labels = {
            "code": "Code",
            "config": "Configuration",
            "docs": "Documentation",
            "generated": "Generated (excluded)",
            "unknown": "Unknown",
        }

        for cls in ["code", "config", "docs", "unknown", "generated"]:
            if cls not in by_class:
                continue

            lines.append(f"  {class_labels.get(cls, cls)}:")
            for d in by_class[cls]:
                langs = f" [{', '.join(d.detected_languages)}]" if d.detected_languages else ""
                files = f"{d.file_count} files" if d.file_count else "empty"
                lines.append(f"    - {d.name}/{langs} ({files})")

            lines.append("")

        return "\n".join(lines)


def detect_project_domains(project_root: Path) -> list[DetectedDomain]:
    """Convenience function to detect domains in a project."""
    scanner = DomainScanner(project_root)
    return scanner.detect_domains()
