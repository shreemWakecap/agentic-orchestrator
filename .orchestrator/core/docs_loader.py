"""
Docs Loader - Simple documentation fetcher for ai_docs/.

Fetches URLs from ai_docs/README.md, saves as markdown files.
Uses file modification time for staleness (>2 days = stale).
"""
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import httpx

# Config
MAX_AGE_DAYS = 2
RATE_LIMIT_SECONDS = 1.0
TIMEOUT_SECONDS = 30


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


class DocsLoader:
    """Simple docs loader for ai_docs/."""

    def __init__(self, project_root: Path):
        self.docs_dir = project_root / 'ai_docs'
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
    """Load docs from ai_docs/."""
    return DocsLoader(project_root).load()
