"""
Docs Loader: Manages AI documentation with freshness checking.

Loads documentation from ai_docs/ directory:
- Reads README.md for list of doc URLs
- Checks file freshness (warns if older than 2 days)
- Fetches and caches docs as needed
- Provides docs context to agents
"""
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from rich.console import Console


@dataclass
class DocFile:
    """Represents a documentation file."""
    name: str
    path: Path
    source_url: str
    last_modified: datetime
    is_fresh: bool
    content: str = ""


@dataclass
class DocsContext:
    """Documentation context to pass to agents."""
    docs: list[DocFile]
    stale_docs: list[str]
    missing_docs: list[str]
    summary: str

    def get_context_string(self, max_length: int = 10000) -> str:
        """Get docs as a context string for agents."""
        if not self.docs:
            return "No documentation available."

        parts = ["## Available Documentation\n"]

        for doc in self.docs:
            freshness = "fresh" if doc.is_fresh else "STALE"
            parts.append(f"### {doc.name} ({freshness})")
            # Truncate long docs
            content = doc.content[:2000] if len(doc.content) > 2000 else doc.content
            parts.append(content)
            parts.append("\n---\n")

        result = "\n".join(parts)
        if len(result) > max_length:
            result = result[:max_length] + "\n... (truncated)"

        return result


class DocsLoader:
    """
    Manages AI documentation with freshness checking.

    Usage:
        loader = DocsLoader(project_root)
        context = loader.load_docs()

        # Check freshness
        if context.stale_docs:
            loader.refresh_stale_docs()
    """

    MAX_AGE_DAYS = 2  # Docs older than this are stale

    def __init__(self, project_root: Path, docs_dir: Optional[Path] = None):
        self.project_root = project_root
        self.docs_dir = docs_dir or project_root / "ai_docs"
        self.cache_dir = self.docs_dir / ".cache"
        self.cache_file = self.cache_dir / "freshness.json"
        self.console = Console()

        # Ensure directories exist
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _load_cache(self) -> dict:
        """Load the freshness cache."""
        if self.cache_file.exists():
            try:
                return json.loads(self.cache_file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_cache(self, cache: dict):
        """Save the freshness cache."""
        self.cache_file.write_text(
            json.dumps(cache, indent=2, default=str),
            encoding="utf-8"
        )

    def _url_to_filename(self, url: str) -> str:
        """Convert URL to a safe filename."""
        parsed = urlparse(url)
        # Get path parts
        path_parts = parsed.path.strip("/").split("/")
        # Use last 2-3 meaningful parts
        meaningful = [p for p in path_parts if p and p != "docs"][-3:]
        name = "-".join(meaningful) or hashlib.md5(url.encode()).hexdigest()[:8]
        # Clean up
        name = re.sub(r'[^\w\-]', '-', name)
        return f"{name}.md"

    def _get_file_age(self, file_path: Path) -> timedelta:
        """Get the age of a file."""
        if not file_path.exists():
            return timedelta(days=999)
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        return datetime.now() - mtime

    def _is_fresh(self, file_path: Path) -> bool:
        """Check if a file is fresh (less than MAX_AGE_DAYS old)."""
        age = self._get_file_age(file_path)
        return age < timedelta(days=self.MAX_AGE_DAYS)

    def parse_readme(self) -> list[str]:
        """Parse README.md to extract documentation URLs."""
        readme_path = self.docs_dir / "README.md"
        if not readme_path.exists():
            return []

        content = readme_path.read_text(encoding="utf-8")
        # Find all URLs (http/https)
        urls = re.findall(r'https?://[^\s\)>\]]+', content)
        return urls

    def load_docs(self, refresh_stale: bool = False) -> DocsContext:
        """
        Load all documentation files.

        Args:
            refresh_stale: If True, attempt to refresh stale docs

        Returns:
            DocsContext with loaded docs and freshness info
        """
        urls = self.parse_readme()
        docs = []
        stale_docs = []
        missing_docs = []

        self.console.print(f"[dim]Loading docs from {self.docs_dir}...[/dim]")

        for url in urls:
            filename = self._url_to_filename(url)
            file_path = self.docs_dir / filename

            if not file_path.exists():
                missing_docs.append(url)
                continue

            is_fresh = self._is_fresh(file_path)
            age = self._get_file_age(file_path)

            if not is_fresh:
                stale_docs.append(url)
                self.console.print(
                    f"  [yellow]⚠ Stale ({age.days}d old):[/yellow] {filename}"
                )

            try:
                content = file_path.read_text(encoding="utf-8")
                docs.append(DocFile(
                    name=filename,
                    path=file_path,
                    source_url=url,
                    last_modified=datetime.fromtimestamp(file_path.stat().st_mtime),
                    is_fresh=is_fresh,
                    content=content
                ))
            except Exception as e:
                self.console.print(f"  [red]Error reading {filename}: {e}[/red]")

        # Summary
        fresh_count = len([d for d in docs if d.is_fresh])
        summary = f"Loaded {len(docs)} docs ({fresh_count} fresh, {len(stale_docs)} stale, {len(missing_docs)} missing)"
        self.console.print(f"[dim]{summary}[/dim]")

        # Optionally refresh stale docs
        if refresh_stale and (stale_docs or missing_docs):
            self.refresh_docs(stale_docs + missing_docs)
            # Reload after refresh
            return self.load_docs(refresh_stale=False)

        return DocsContext(
            docs=docs,
            stale_docs=stale_docs,
            missing_docs=missing_docs,
            summary=summary
        )

    def refresh_docs(self, urls: list[str]):
        """
        Refresh documentation from URLs.

        Uses Claude CLI to fetch and process docs.
        """
        self.console.print(f"[cyan]Refreshing {len(urls)} docs...[/cyan]")

        for url in urls:
            filename = self._url_to_filename(url)
            file_path = self.docs_dir / filename

            self.console.print(f"  Fetching: {url[:60]}...")

            try:
                # Use Claude CLI to fetch and summarize the doc
                prompt = f"""Fetch and summarize this documentation URL for AI consumption:
{url}

Output a clean markdown document with:
1. Title and source URL
2. Key concepts and usage
3. Important code examples
4. Common patterns

Keep it concise but comprehensive."""

                result = subprocess.run(
                    ["claude", "--print", "-p", prompt],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    cwd=str(self.project_root)
                )

                if result.returncode == 0 and result.stdout.strip():
                    # Add metadata header
                    content = f"""---
source: {url}
fetched: {datetime.now().isoformat()}
---

{result.stdout.strip()}
"""
                    file_path.write_text(content, encoding="utf-8")
                    self.console.print(f"  [green]✓[/green] {filename}")
                else:
                    self.console.print(f"  [red]✗[/red] Failed to fetch {filename}")

            except subprocess.TimeoutExpired:
                self.console.print(f"  [red]✗[/red] Timeout fetching {filename}")
            except Exception as e:
                self.console.print(f"  [red]✗[/red] Error: {e}")

        # Update cache
        cache = self._load_cache()
        cache["last_refresh"] = datetime.now().isoformat()
        cache["refreshed_urls"] = urls
        self._save_cache(cache)

    def get_docs_for_tech(self, tech: str) -> list[DocFile]:
        """Get docs relevant to a specific technology."""
        context = self.load_docs()
        relevant = []

        tech_lower = tech.lower()
        for doc in context.docs:
            # Check if doc is relevant to this tech
            if (tech_lower in doc.name.lower() or
                tech_lower in doc.source_url.lower() or
                tech_lower in doc.content.lower()[:500]):
                relevant.append(doc)

        return relevant

    def check_freshness(self) -> dict:
        """
        Check freshness of all docs and return status.

        Returns dict with status and recommendations.
        """
        context = self.load_docs()

        return {
            "total_docs": len(context.docs),
            "fresh_docs": len([d for d in context.docs if d.is_fresh]),
            "stale_docs": context.stale_docs,
            "missing_docs": context.missing_docs,
            "needs_refresh": len(context.stale_docs) + len(context.missing_docs) > 0,
            "recommendation": (
                "All docs are fresh" if not context.stale_docs and not context.missing_docs
                else f"Run refresh to update {len(context.stale_docs)} stale and fetch {len(context.missing_docs)} missing docs"
            )
        }


# Convenience function for workflows
def load_docs_context(project_root: Path, refresh: bool = False) -> DocsContext:
    """Load docs context for use in workflows."""
    loader = DocsLoader(project_root)
    return loader.load_docs(refresh_stale=refresh)
