"""
File Scouting Workflow.

Analyzes a single file to build targeted knowledge.

Flow:
    Manual Trigger → File Path → Scout Agent → FileKnowledge

The workflow:
1. Validates the file exists and is readable
2. Reads file content
3. Invokes scout agent with file-specific prompt
4. Parses response into FileKnowledge
5. Saves to FileKnowledgeStore
"""
import hashlib
import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from core import Agent, Workflow, WorkflowResult, get_agent_config
from core.knowledge_store import (
    FileKnowledgeStore,
    FileKnowledge,
    FileScanResult,
)


class FileScoutingWorkflow(Workflow):
    """
    File scouting workflow for targeted file analysis.

    Runs the scout agent to analyze a single file and populate
    the file knowledge store with structure, imports, exports,
    classes, functions, and dependencies.
    """

    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()
        self._config = get_agent_config(project_root)

        # File knowledge store
        self.file_knowledge_store = FileKnowledgeStore(project_root)

        # Output dir for any artifacts
        output_dir = project_root / ".orchestrator" / "knowledge"
        output_dir.mkdir(parents=True, exist_ok=True)

        super().__init__(name="File Scouting Workflow", output_dir=output_dir)

        # Load the scout agent
        self._load_agents()

    def _load_agents(self):
        """Load required agents."""
        try:
            self.register_agent(Agent.load("scout", self.project_root))
        except FileNotFoundError:
            self.console.print("[red]Error: scout agent not found[/red]")
            raise

    def _validate_file(self, file_path: Path) -> tuple[bool, Optional[str]]:
        """
        Validate that the file exists and is readable.

        No restrictions on directory - any file within the project is allowed.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not file_path.exists():
            return False, f"File does not exist: {file_path}"

        if not file_path.is_file():
            return False, f"Path is not a file: {file_path}"

        try:
            # Try to read the file to ensure it's readable
            file_path.read_bytes()
        except PermissionError:
            return False, f"Permission denied: {file_path}"
        except Exception as e:
            return False, f"Cannot read file: {file_path} - {e}"

        return True, None

    def _get_file_content(self, file_path: Path) -> tuple[str, int]:
        """
        Read file content with line count.

        Returns:
            Tuple of (content, line_count)
        """
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            line_count = content.count("\n") + 1 if content else 0
            return content, line_count
        except Exception:
            # Binary file or encoding issue, return empty
            return "", 0

    def _compute_content_hash(self, content: str) -> str:
        """Compute SHA-256 hash of file content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def _detect_language(self, file_path: Path) -> str:
        """Detect programming language from file extension."""
        ext_to_lang = {
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
            ".scala": "scala",
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
            ".sh": "bash",
            ".bash": "bash",
            ".zsh": "zsh",
            ".ps1": "powershell",
        }
        return ext_to_lang.get(file_path.suffix.lower(), "unknown")

    def execute(self, file_path: str) -> WorkflowResult:
        """
        Execute the file scouting workflow for a single file.

        Args:
            file_path: Path to the file to scout (relative or absolute)

        Returns:
            WorkflowResult with the file knowledge stored
        """
        from core.symbols import CHECK, CROSS, ARROW_RIGHT

        # Resolve file path
        path = Path(file_path)
        if not path.is_absolute():
            path = self.project_root / path
        path = path.resolve()

        # Make path relative for storage
        try:
            relative_path = path.relative_to(self.project_root)
        except ValueError:
            # Path is outside project root
            relative_path = path

        self.console.print(f"\n[bold]Scouting file[/bold]: {relative_path}")

        # Start timing
        scan_id = str(uuid.uuid4())[:8]
        started_at = datetime.now()

        # Validate file
        is_valid, error = self._validate_file(path)
        if not is_valid:
            self.console.print(f"  [red]{CROSS}[/red] {error}")
            return WorkflowResult(
                success=False,
                error=error
            )

        # Read file content
        content, line_count = self._get_file_content(path)
        file_size = path.stat().st_size
        last_modified = datetime.fromtimestamp(path.stat().st_mtime).isoformat()
        content_hash = self._compute_content_hash(content)
        language = self._detect_language(path)

        # Build scout prompt for file analysis
        scout_prompt = f"""Analyze this single file and extract structured information.

FILE: {relative_path}
LANGUAGE: {language}
SIZE: {file_size} bytes
LINES: {line_count}

CONTENT:
```{language}
{content[:50000]}
```

Analyze the file structure and output JSON with:
{{
    "imports": ["list of imported modules/packages"],
    "exports": ["list of exported symbols (functions, classes, variables)"],
    "classes": [
        {{"name": "ClassName", "methods": ["method1", "method2"], "docstring": "class description"}}
    ],
    "functions": [
        {{"name": "function_name", "params": ["param1", "param2"], "docstring": "function description"}}
    ],
    "dependencies": ["external packages this file depends on"],
    "domain_hints": ["business domains this file relates to (e.g., auth, payments, api)"],
    "notes": "Brief summary of what this file does"
}}

Focus on:
1. IMPORTS - What modules/packages are imported
2. EXPORTS - What symbols are exported/public
3. CLASSES - Class names, their methods, and purpose
4. FUNCTIONS - Function names, parameters, and purpose
5. DEPENDENCIES - External packages used
6. DOMAIN - Business domain hints (auth, payments, users, etc.)

Output the JSON only, no additional text.
"""

        # Run scout agent
        self.console.print(f"\n[cyan]{ARROW_RIGHT}[/cyan] Analyzing file structure...")

        result = self.run_agent(
            "scout",
            message=scout_prompt,
            show_progress=True
        )

        if not result.success:
            self.console.print(f"  [red]{CROSS}[/red] Scout failed: {result.error}")

            # Save failed scan result
            scan_result = FileScanResult(
                scan_id=scan_id,
                file_path=str(relative_path),
                success=False,
                started_at=started_at.isoformat(),
                completed_at=datetime.now().isoformat(),
                duration_seconds=(datetime.now() - started_at).total_seconds(),
                error=result.error,
            )
            self.file_knowledge_store.save_scan_result(scan_result)

            return WorkflowResult(
                success=False,
                error=f"Scout failed: {result.error}"
            )

        # Extract JSON from response
        analysis_data = self._extract_json(result.content)

        if not analysis_data:
            self.console.print(f"  [red]{CROSS}[/red] No valid JSON found in scout response")

            # Save failed scan result
            scan_result = FileScanResult(
                scan_id=scan_id,
                file_path=str(relative_path),
                success=False,
                started_at=started_at.isoformat(),
                completed_at=datetime.now().isoformat(),
                duration_seconds=(datetime.now() - started_at).total_seconds(),
                error="Scout did not produce valid JSON",
            )
            self.file_knowledge_store.save_scan_result(scan_result)

            return WorkflowResult(
                success=False,
                error="Scout did not produce valid JSON"
            )

        # Build FileKnowledge
        file_knowledge = self._parse_file_knowledge(
            analysis_data,
            file_path=str(relative_path),
            file_name=path.name,
            language=language,
            size_bytes=file_size,
            line_count=line_count,
            last_modified=last_modified,
            content_hash=content_hash,
        )

        # Save to file knowledge store
        if not self.file_knowledge_store.save(file_knowledge):
            self.console.print(f"  [red]{CROSS}[/red] Failed to save file knowledge")
            return WorkflowResult(
                success=False,
                error="Failed to save file knowledge"
            )

        # Calculate statistics
        completed_at = datetime.now()
        duration = (completed_at - started_at).total_seconds()

        # Save successful scan result
        scan_result = FileScanResult(
            scan_id=scan_id,
            file_path=str(relative_path),
            success=True,
            started_at=started_at.isoformat(),
            completed_at=completed_at.isoformat(),
            duration_seconds=duration,
        )
        self.file_knowledge_store.save_scan_result(scan_result)

        # Print summary
        self.console.print(f"\n[green]{CHECK}[/green] File scouting complete!")
        self.console.print(f"  [dim]Duration: {duration:.1f}s | Lines: {line_count}[/dim]")

        if file_knowledge.imports:
            self.console.print(f"  Imports: [cyan]{len(file_knowledge.imports)}[/cyan]")

        if file_knowledge.classes:
            class_names = ", ".join(c.get("name", "?") for c in file_knowledge.classes[:3])
            self.console.print(f"  Classes: [cyan]{class_names}[/cyan]")

        if file_knowledge.functions:
            func_count = len(file_knowledge.functions)
            self.console.print(f"  Functions: [cyan]{func_count}[/cyan]")

        if file_knowledge.dependencies:
            deps = ", ".join(file_knowledge.dependencies[:5])
            self.console.print(f"  Dependencies: [cyan]{deps}[/cyan]")

        if file_knowledge.domain_hints:
            domains = ", ".join(file_knowledge.domain_hints)
            self.console.print(f"  Domains: [cyan]{domains}[/cyan]")

        return WorkflowResult(
            success=True,
            data={
                "scan_id": scan_id,
                "file_path": str(relative_path),
                "language": language,
                "duration": duration,
                "line_count": line_count,
                "imports_count": len(file_knowledge.imports),
                "classes_count": len(file_knowledge.classes),
                "functions_count": len(file_knowledge.functions),
                "dependencies_count": len(file_knowledge.dependencies),
            }
        )

    def _extract_json(self, response: str) -> Optional[dict]:
        """Extract JSON from scout response."""
        # Look for OUTPUT_JSON: marker
        json_match = re.search(
            r"OUTPUT_JSON:\s*(\{.*\})",
            response,
            re.DOTALL
        )
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find JSON in code block
        code_match = re.search(
            r"```(?:json)?\s*(\{.*?\})\s*```",
            response,
            re.DOTALL
        )
        if code_match:
            try:
                return json.loads(code_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find raw JSON
        brace_match = re.search(r"(\{[\s\S]*\})", response)
        if brace_match:
            try:
                return json.loads(brace_match.group(1))
            except json.JSONDecodeError:
                pass

        return None

    def _parse_file_knowledge(
        self,
        data: dict,
        file_path: str,
        file_name: str,
        language: str,
        size_bytes: int,
        line_count: int,
        last_modified: str,
        content_hash: str,
    ) -> FileKnowledge:
        """Parse JSON data into FileKnowledge."""
        return FileKnowledge(
            file_path=file_path,
            file_name=file_name,
            language=language,
            size_bytes=size_bytes,
            line_count=line_count,
            last_modified=last_modified,
            content_hash=content_hash,
            imports=data.get("imports", []),
            exports=data.get("exports", []),
            classes=data.get("classes", []),
            functions=data.get("functions", []),
            dependencies=data.get("dependencies", []),
            domain_hints=data.get("domain_hints", []),
            notes=data.get("notes", ""),
        )


def run(args=None) -> int:
    """Run file scouting action from CLI."""
    import argparse

    parser = argparse.ArgumentParser(description="Scout a single file")
    parser.add_argument(
        "file_path",
        help="Path to the file to scout (relative or absolute)"
    )

    parsed = parser.parse_args(args or [])
    project_root = Path(__file__).parent.parent.parent

    workflow = FileScoutingWorkflow(project_root=project_root)
    result = workflow.run(parsed.file_path)

    return 0 if result.success else 1


if __name__ == "__main__":
    import sys
    sys.exit(run(sys.argv[1:]))
