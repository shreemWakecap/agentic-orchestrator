"""
Docs Loader - Simple documentation fetcher for .orchestrator/docs/.

Fetches URLs from .orchestrator/docs/README.md, saves as markdown files.
Uses file modification time for staleness (>2 days = stale).
"""
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import httpx

# Config
MAX_AGE_DAYS = 2
RATE_LIMIT_SECONDS = 1.0
TIMEOUT_SECONDS = 30

# Keywords for documentation filtering (Python-focused)
PYTHON_DOC_KEYWORDS = ["python", "pip", "pytest", "pep", "typing", "asyncio", "fastapi", "django", "flask"]


def strip_html(html: str) -> str:
    """Strip HTML tags, keep text content."""
    # Remove script/style blocks
    html = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
    # Remove all tags
    text = re.sub(r'<[^>]+>', ' ', html)
    # Clean whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def url_to_filename(url: str) -> str:
    """Convert URL to safe filename."""
    parsed = urlparse(url)
    # Use path parts for readable name
    parts = [p for p in parsed.path.strip('/').split('/') if p][-3:]
    name = '-'.join(parts) if parts else 'index'
    name = re.sub(r'[^\w\-]', '-', name)
    return f"{name}.md"


def parse_urls(readme_path: Path) -> list[str]:
    """Extract URLs from README.md."""
    if not readme_path.exists():
        return []
    content = readme_path.read_text(encoding='utf-8')
    urls = re.findall(r'https?://[^\s\)>\]"\']+', content)
    # Strip trailing punctuation
    return [url.rstrip('.,;:!?') for url in urls]


def is_stale(file_path: Path) -> bool:
    """Check if file is older than MAX_AGE_DAYS."""
    if not file_path.exists():
        return True
    age = datetime.now() - datetime.fromtimestamp(file_path.stat().st_mtime)
    return age > timedelta(days=MAX_AGE_DAYS)


def fetch_url(url: str) -> str | None:
    """Fetch URL content, return text or None on error."""
    try:
        with httpx.Client(timeout=TIMEOUT_SECONDS, follow_redirects=True) as client:
            resp = client.get(url, headers={'User-Agent': 'DocsLoader/1.0'})
            resp.raise_for_status()
            content = resp.text
            # Convert HTML to plain text if needed
            if 'html' in resp.headers.get('content-type', ''):
                content = strip_html(content)
            return content
    except Exception as e:
        print(f"  [!] Failed to fetch {url}: {e}")
        return None


@dataclass
class DocsContext:
    """
    Context object for loaded documentation.

    Provides methods for:
    - Getting all docs as a context string
    - Filtering docs by technology relevance
    - Smart truncation that preserves section boundaries
    """
    docs: list[dict] = field(default_factory=list)
    stale_docs: list[str] = field(default_factory=list)
    missing_docs: list[str] = field(default_factory=list)

    def get_context_string(self, max_chars: int = 10000) -> str:
        """
        Get all documentation as a context string.

        Args:
            max_chars: Maximum characters to return (default 10000)

        Returns:
            Formatted documentation string with smart truncation
        """
        if not self.docs:
            return ""

        sections = []
        total_chars = 0

        for doc in self.docs:
            doc_header = f"### {doc['name']}\n"
            doc_content = doc.get('content', '')[:3000]  # Cap individual docs
            section = doc_header + doc_content

            if total_chars + len(section) > max_chars:
                # Add what fits, truncating at paragraph boundary
                remaining = max_chars - total_chars
                if remaining > 200:
                    truncated = self._smart_truncate(section, remaining)
                    sections.append(truncated)
                break

            sections.append(section)
            total_chars += len(section)

        return "\n\n".join(sections)

    def get_docs_for_tech(self, tech: str, max_chars: int = 8000) -> str:
        """
        Get documentation filtered by relevance (Python-focused).

        Args:
            tech: Technology name (currently only python supported)
            max_chars: Maximum characters for output

        Returns:
            Relevant documentation up to max_chars
        """
        # Score docs by Python keyword relevance
        scored_docs = []
        for doc in self.docs:
            content_lower = (doc.get('content', '') + doc.get('name', '')).lower()
            score = sum(1 for kw in PYTHON_DOC_KEYWORDS if kw in content_lower)
            if score > 0:
                scored_docs.append((score, doc))

        # Sort by relevance (highest first)
        scored_docs.sort(key=lambda x: -x[0])

        # Build context with relevant docs first
        sections = []
        total_chars = 0

        for _, doc in scored_docs:
            doc_header = f"### {doc['name']}\n"
            doc_content = doc.get('content', '')[:4000]
            section = doc_header + doc_content

            if total_chars + len(section) > max_chars:
                remaining = max_chars - total_chars
                if remaining > 300:
                    sections.append(self._smart_truncate(section, remaining))
                break

            sections.append(section)
            total_chars += len(section)

        if not sections:
            return self.get_context_string(max_chars=max_chars // 2)

        return "\n\n".join(sections)

    def _smart_truncate(self, text: str, max_chars: int) -> str:
        """Truncate text at a natural boundary (paragraph or sentence)."""
        if len(text) <= max_chars:
            return text

        truncated = text[:max_chars]

        # Try to truncate at paragraph boundary
        last_para = truncated.rfind('\n\n')
        if last_para > max_chars * 0.6:
            return truncated[:last_para] + "\n\n[...truncated...]"

        # Try to truncate at sentence boundary
        last_sentence = max(
            truncated.rfind('. '),
            truncated.rfind('.\n'),
            truncated.rfind('? '),
            truncated.rfind('! ')
        )
        if last_sentence > max_chars * 0.6:
            return truncated[:last_sentence + 1] + "\n\n[...truncated...]"

        return truncated + "\n\n[...truncated...]"


class DocsLoader:
    """Simple docs loader for .orchestrator/docs/."""

    def __init__(self, project_root: Path):
        self.docs_dir = project_root / '.orchestrator' / 'docs'
        self.readme = self.docs_dir / 'README.md'
        self._last_fetch = 0.0

    def _rate_limit(self):
        """Simple rate limiting."""
        elapsed = time.time() - self._last_fetch
        if elapsed < RATE_LIMIT_SECONDS:
            time.sleep(RATE_LIMIT_SECONDS - elapsed)
        self._last_fetch = time.time()

    def get_urls(self) -> list[str]:
        """Get documentation URLs from README."""
        return parse_urls(self.readme)

    def get_status(self) -> dict:
        """Get docs status: total, fresh, stale, missing."""
        urls = self.get_urls()
        fresh, stale, missing = [], [], []

        for url in urls:
            path = self.docs_dir / url_to_filename(url)
            if not path.exists():
                missing.append(url)
            elif is_stale(path):
                stale.append(url)
            else:
                fresh.append(url)

        return {
            'total': len(urls),
            'fresh': len(fresh),
            'stale': stale,
            'missing': missing,
        }

    def load(self) -> list[dict]:
        """Load all existing doc files."""
        docs = []
        for url in self.get_urls():
            path = self.docs_dir / url_to_filename(url)
            if path.exists():
                docs.append({
                    'name': path.name,
                    'url': url,
                    'content': path.read_text(encoding='utf-8'),
                    'fresh': not is_stale(path),
                })
        return docs

    def load_docs(self, refresh_stale: bool = False) -> DocsContext:
        """
        Load documentation and return a DocsContext object.

        Args:
            refresh_stale: If True, refresh stale/missing docs before loading

        Returns:
            DocsContext with loaded docs and status info
        """
        status = self.get_status()

        if refresh_stale and (status['stale'] or status['missing']):
            self.refresh(status['stale'] + status['missing'])
            status = self.get_status()

        docs = self.load()

        return DocsContext(
            docs=docs,
            stale_docs=status['stale'],
            missing_docs=status['missing']
        )

    def refresh(self, urls: list[str] | None = None) -> dict:
        """Fetch and save docs. Returns {updated, failed} counts."""
        if urls is None:
            status = self.get_status()
            urls = status['stale'] + status['missing']

        if not urls:
            return {'updated': 0, 'failed': 0}

        updated, failed = 0, 0
        for url in urls:
            self._rate_limit()
            print(f"  Fetching: {url[:60]}...")

            content = fetch_url(url)
            if content is None:
                failed += 1
                continue

            # Save with metadata header
            path = self.docs_dir / url_to_filename(url)
            header = f"---\nsource: {url}\nfetched: {datetime.now().isoformat()}\n---\n\n"
            path.write_text(header + content, encoding='utf-8')
            updated += 1
            print(f"  [+] {path.name}")

        return {'updated': updated, 'failed': failed}


# Convenience function
def load_docs(project_root: Path) -> list[dict]:
    """Load docs from .orchestrator/docs/."""
    return DocsLoader(project_root).load()
