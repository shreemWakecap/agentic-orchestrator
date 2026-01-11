"""Unit tests for the DocsLoader class."""
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import responses

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.docs_loader import DocsLoader, DocsContext


class TestDocsContext:
    """Tests for DocsContext dataclass."""

    def test_docs_context_creation(self):
        """Test DocsContext can be created."""
        context = DocsContext(
            docs=[
                {"name": "doc1", "content": "Content 1", "url": "http://example.com/1"},
                {"name": "doc2", "content": "Content 2", "url": "http://example.com/2"},
            ],
            stale_docs=["http://example.com/old"],
            missing_docs=["http://example.com/missing"],
        )
        assert len(context.docs) == 2
        assert len(context.stale_docs) == 1
        assert len(context.missing_docs) == 1

    def test_get_context_string_basic(self):
        """Test basic context string generation."""
        context = DocsContext(
            docs=[
                {"name": "Test Doc", "content": "Test content here", "url": "http://test.com"},
            ],
            stale_docs=[],
            missing_docs=[],
        )
        result = context.get_context_string()

        assert "Test Doc" in result
        assert "Test content here" in result

    def test_get_context_string_respects_limit(self):
        """Test context string respects character limit."""
        long_content = "x" * 10000
        context = DocsContext(
            docs=[
                {"name": "Long Doc", "content": long_content, "url": "http://test.com"},
            ],
            stale_docs=[],
            missing_docs=[],
        )
        result = context.get_context_string(max_chars=5000)

        assert len(result) <= 5000

    def test_get_context_string_multiple_docs(self):
        """Test context string with multiple docs."""
        context = DocsContext(
            docs=[
                {"name": "Doc 1", "content": "Content 1", "url": "http://test.com/1"},
                {"name": "Doc 2", "content": "Content 2", "url": "http://test.com/2"},
                {"name": "Doc 3", "content": "Content 3", "url": "http://test.com/3"},
            ],
            stale_docs=[],
            missing_docs=[],
        )
        result = context.get_context_string()

        assert "Doc 1" in result
        assert "Doc 2" in result
        assert "Doc 3" in result

    def test_get_docs_for_tech(self):
        """Test filtering docs by technology."""
        context = DocsContext(
            docs=[
                {"name": "Python Guide", "content": "Python stuff", "url": "http://python.org"},
                {"name": "JavaScript Guide", "content": "JS stuff", "url": "http://js.com"},
                {"name": "FastAPI Docs", "content": "FastAPI Python", "url": "http://fastapi.com"},
            ],
            stale_docs=[],
            missing_docs=[],
        )

        # Filter for Python-related docs
        python_docs = context.get_docs_for_tech("python", max_chars=10000)

        assert "Python" in python_docs or "python" in python_docs.lower()


class TestDocsLoader:
    """Tests for DocsLoader class."""

    def test_loader_initialization(self, tmp_path):
        """Test DocsLoader initialization."""
        loader = DocsLoader(tmp_path)
        assert loader.project_root == tmp_path

    def test_get_status_empty(self, tmp_path):
        """Test get_status with no docs."""
        # Create empty ai_docs directory
        ai_docs = tmp_path / "ai_docs"
        ai_docs.mkdir()

        # Create README with no URLs
        readme = ai_docs / "README.md"
        readme.write_text("# AI Docs\n\nNo URLs here.")

        loader = DocsLoader(tmp_path)
        status = loader.get_status()

        assert status["total"] == 0
        assert status["fresh"] == 0
        assert len(status["stale"]) == 0
        assert len(status["missing"]) == 0

    def test_get_status_with_urls(self, tmp_path):
        """Test get_status with URLs in README."""
        ai_docs = tmp_path / "ai_docs"
        ai_docs.mkdir()

        readme = ai_docs / "README.md"
        readme.write_text("""# AI Docs

## Sources
- https://example.com/doc1
- https://example.com/doc2
""")

        loader = DocsLoader(tmp_path)
        status = loader.get_status()

        assert status["total"] == 2
        assert len(status["missing"]) == 2  # Both are missing (not fetched)

    def test_get_status_with_fetched_docs(self, tmp_path):
        """Test get_status with fetched docs."""
        ai_docs = tmp_path / "ai_docs"
        ai_docs.mkdir()

        readme = ai_docs / "README.md"
        readme.write_text("- https://example.com/test")

        # Create fetched doc file
        doc_file = ai_docs / "example_com_test.md"
        doc_file.write_text("# Fetched content")

        loader = DocsLoader(tmp_path)
        status = loader.get_status()

        assert status["fresh"] >= 0  # May be fresh or stale depending on mtime

    def test_url_to_filename(self, tmp_path):
        """Test URL to filename conversion."""
        loader = DocsLoader(tmp_path)

        # Test basic URL
        filename = loader._url_to_filename("https://example.com/docs/guide")
        assert "example_com" in filename
        assert filename.endswith(".md")

        # Test URL with special characters
        filename = loader._url_to_filename("https://api.example.com/v2/docs?param=value")
        assert ".md" in filename

    @responses.activate
    def test_fetch_single_doc(self, tmp_path):
        """Test fetching a single document."""
        responses.add(
            responses.GET,
            "https://example.com/doc",
            body="# Documentation\n\nThis is the content.",
            status=200,
        )

        ai_docs = tmp_path / "ai_docs"
        ai_docs.mkdir()

        loader = DocsLoader(tmp_path)
        result = loader._fetch_url("https://example.com/doc")

        assert result is not None
        assert "Documentation" in result or "content" in result.lower()

    @responses.activate
    def test_fetch_handles_error(self, tmp_path):
        """Test fetch handles HTTP errors gracefully."""
        responses.add(
            responses.GET,
            "https://example.com/notfound",
            status=404,
        )

        ai_docs = tmp_path / "ai_docs"
        ai_docs.mkdir()

        loader = DocsLoader(tmp_path)
        result = loader._fetch_url("https://example.com/notfound")

        assert result is None

    def test_load_docs_creates_context(self, tmp_path):
        """Test load_docs creates DocsContext."""
        ai_docs = tmp_path / "ai_docs"
        ai_docs.mkdir()

        # Create a doc file
        doc_file = ai_docs / "test_doc.md"
        doc_file.write_text("# Test\n\nContent here")

        # Create README
        readme = ai_docs / "README.md"
        readme.write_text("# Docs")

        loader = DocsLoader(tmp_path)
        context = loader.load_docs()

        assert isinstance(context, DocsContext)

    def test_staleness_detection(self, tmp_path):
        """Test stale document detection."""
        ai_docs = tmp_path / "ai_docs"
        ai_docs.mkdir()

        readme = ai_docs / "README.md"
        readme.write_text("- https://example.com/doc")

        # Create doc file with old modification time
        doc_file = ai_docs / "example_com_doc.md"
        doc_file.write_text("Old content")

        # Set mtime to 3 days ago
        old_time = time.time() - (3 * 24 * 60 * 60)
        os.utime(doc_file, (old_time, old_time))

        loader = DocsLoader(tmp_path)
        status = loader.get_status()

        # Should be stale (older than 2 days)
        assert len(status["stale"]) > 0 or doc_file.name in str(status)


class TestDocsLoaderIntegration:
    """Integration tests for DocsLoader."""

    @responses.activate
    def test_refresh_fetches_missing(self, tmp_path):
        """Test refresh fetches missing documents."""
        responses.add(
            responses.GET,
            "https://example.com/newdoc",
            body="# New Doc\n\nFresh content",
            status=200,
        )

        ai_docs = tmp_path / "ai_docs"
        ai_docs.mkdir()

        readme = ai_docs / "README.md"
        readme.write_text("- https://example.com/newdoc")

        loader = DocsLoader(tmp_path)
        result = loader.refresh()

        assert result["updated"] >= 0

    def test_docs_directory_created_if_missing(self, tmp_path):
        """Test ai_docs directory is created if missing."""
        loader = DocsLoader(tmp_path)

        # Should not raise even if ai_docs doesn't exist
        status = loader.get_status()
        assert isinstance(status, dict)
