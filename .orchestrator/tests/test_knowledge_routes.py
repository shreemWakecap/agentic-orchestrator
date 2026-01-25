"""Tests for knowledge API routes.

These tests use a mock knowledge repository to test the knowledge endpoints
without requiring a real database.
"""
import pytest
from typing import Dict, List, Optional
from fastapi.testclient import TestClient


class MockKnowledgeRepository:
    """Mock knowledge repository for testing."""

    def __init__(self):
        self._knowledge: Optional[Dict] = None
        self._expert_index: Optional[Dict] = None
        self._scan_meta: Optional[Dict] = None
        self._coding_rules: List[Dict] = []

    def exists(self) -> bool:
        return self._knowledge is not None

    def has_expert_index(self) -> bool:
        return self._expert_index is not None

    def load_knowledge(self) -> Optional[Dict]:
        return self._knowledge

    def load_expert_index(self) -> Optional[Dict]:
        return self._expert_index

    def load_scan_meta(self) -> Optional[Dict]:
        return self._scan_meta

    def get_coding_rules(
        self, category: Optional[str] = None, min_confidence: float = 0.0
    ) -> List[Dict]:
        rules = self._coding_rules
        if category:
            rules = [r for r in rules if r.get("category") == category]
        rules = [r for r in rules if r.get("confidence", 0) >= min_confidence]
        return rules

    def clear(self) -> None:
        self._knowledge = None
        self._expert_index = None
        self._scan_meta = None
        self._coding_rules = []

    def set_knowledge(self, knowledge: Dict) -> None:
        """Test helper to set knowledge data."""
        self._knowledge = knowledge

    def set_expert_index(self, index: Dict) -> None:
        """Test helper to set expert index."""
        self._expert_index = index

    def set_scan_meta(self, meta: Dict) -> None:
        """Test helper to set scan metadata."""
        self._scan_meta = meta

    def set_coding_rules(self, rules: List[Dict]) -> None:
        """Test helper to set coding rules."""
        self._coding_rules = rules


@pytest.fixture
def mock_knowledge_repo():
    """Create a mock knowledge repository."""
    return MockKnowledgeRepository()


@pytest.fixture
def knowledge_test_client(mock_knowledge_repo, mock_run_repo):
    """Create a test client with mocked knowledge dependencies."""
    import sys
    from pathlib import Path

    orchestrator_dir = Path(__file__).parent.parent
    sys.path.insert(0, str(orchestrator_dir))

    from portal.app import app
    from portal.dependencies import get_knowledge_repo, get_run_repo

    app.dependency_overrides[get_knowledge_repo] = lambda: mock_knowledge_repo
    app.dependency_overrides[get_run_repo] = lambda: mock_run_repo

    client = TestClient(app)
    yield client

    app.dependency_overrides.clear()


@pytest.fixture
def sample_knowledge():
    """Sample knowledge data for testing."""
    return {
        "project": {
            "name": "test-project",
            "type": "web-application",
            "primary_language": "Python",
        },
        "last_updated": "2025-01-25T10:00:00Z",
        "technologies": {
            "languages": [
                {"name": "Python", "confidence": 0.95},
                {"name": "TypeScript", "confidence": 0.75},
            ],
            "frameworks": [
                {"name": "FastAPI", "confidence": 0.9},
                {"name": "React", "confidence": 0.8},
            ],
            "tools": [
                {"name": "Docker", "confidence": 0.85},
            ],
        },
        "architecture": {
            "pattern": "layered",
            "modules": [
                {"name": "api", "path": "src/api", "purpose": "API endpoints"},
                {"name": "core", "path": "src/core", "purpose": "Core logic"},
            ],
        },
        "domains": [
            {"name": "authentication", "keywords": ["auth", "login"], "files": ["auth.py"]},
            {"name": "users", "keywords": ["user", "profile"], "files": ["users.py", "profiles.py"]},
        ],
    }


@pytest.fixture
def sample_expert_index():
    """Sample expert index for testing."""
    return {
        "experts": [
            {
                "name": "auth-expert",
                "type": "domain",
                "triggers": {
                    "keywords": ["auth", "login", "oauth"],
                    "paths": ["src/auth"],
                    "topics": ["authentication", "security"],
                },
            },
            {
                "name": "api-expert",
                "type": "framework",
                "triggers": {
                    "keywords": ["endpoint", "route"],
                    "paths": ["src/api"],
                    "topics": ["REST", "API"],
                },
            },
        ],
        "keyword_map": {"auth": ["auth-expert"], "api": ["api-expert"]},
        "path_map": {"src/auth": ["auth-expert"], "src/api": ["api-expert"]},
    }


@pytest.fixture
def sample_scan_meta():
    """Sample scan metadata for testing."""
    return {
        "scan_id": "scan-001",
        "started_at": "2025-01-25T09:00:00Z",
        "completed_at": "2025-01-25T09:05:00Z",
        "duration_seconds": 300,
        "files_scanned": 150,
        "scan_type": "full",
        "trigger_type": "manual",
        "experts_generated": ["auth-expert", "api-expert"],
    }


class TestKnowledgeRoutes:
    """Tests for knowledge API routes."""

    def test_get_knowledge_overview_empty(self, knowledge_test_client):
        """Should return empty overview when no knowledge exists."""
        response = knowledge_test_client.get("/api/knowledge")
        assert response.status_code == 200
        data = response.json()
        assert data["has_knowledge"] is False
        assert data["has_expert_index"] is False
        assert data["project_name"] == ""
        assert data["languages_count"] == 0

    def test_get_knowledge_overview_with_data(
        self, knowledge_test_client, mock_knowledge_repo, sample_knowledge, sample_scan_meta
    ):
        """Should return knowledge overview with counts."""
        mock_knowledge_repo.set_knowledge(sample_knowledge)
        mock_knowledge_repo.set_scan_meta(sample_scan_meta)

        response = knowledge_test_client.get("/api/knowledge")
        assert response.status_code == 200
        data = response.json()

        assert data["has_knowledge"] is True
        assert data["project_name"] == "test-project"
        assert data["project_type"] == "web-application"
        assert data["primary_language"] == "Python"
        assert data["languages_count"] == 2
        assert data["frameworks_count"] == 2
        assert data["tools_count"] == 1
        assert data["modules_count"] == 2
        assert data["domains_count"] == 2
        assert data["last_scan"] is not None
        assert data["last_scan"]["scan_id"] == "scan-001"

    def test_get_full_knowledge_empty(self, knowledge_test_client):
        """Should return message when no knowledge available."""
        response = knowledge_test_client.get("/api/knowledge/full")
        assert response.status_code == 200
        data = response.json()
        assert data["knowledge"] is None
        assert "No knowledge available" in data["message"]

    def test_get_full_knowledge_with_data(
        self, knowledge_test_client, mock_knowledge_repo, sample_knowledge
    ):
        """Should return full knowledge data."""
        mock_knowledge_repo.set_knowledge(sample_knowledge)

        response = knowledge_test_client.get("/api/knowledge/full")
        assert response.status_code == 200
        data = response.json()

        assert data["knowledge"] is not None
        assert data["knowledge"]["project"]["name"] == "test-project"
        assert len(data["knowledge"]["technologies"]["languages"]) == 2

    def test_get_expert_index_empty(self, knowledge_test_client):
        """Should return message when no expert index available."""
        response = knowledge_test_client.get("/api/knowledge/expert-index")
        assert response.status_code == 200
        data = response.json()
        assert data["expert_index"] is None
        assert "No expert index available" in data["message"]

    def test_get_expert_index_with_data(
        self, knowledge_test_client, mock_knowledge_repo, sample_expert_index
    ):
        """Should return expert index data."""
        mock_knowledge_repo.set_expert_index(sample_expert_index)

        response = knowledge_test_client.get("/api/knowledge/expert-index")
        assert response.status_code == 200
        data = response.json()

        assert data["expert_index"] is not None
        assert len(data["expert_index"]["experts"]) == 2
        assert "auth-expert" in [e["name"] for e in data["expert_index"]["experts"]]

    def test_get_scan_metadata_empty(self, knowledge_test_client):
        """Should return message when no scan history available."""
        response = knowledge_test_client.get("/api/knowledge/scan-meta")
        assert response.status_code == 200
        data = response.json()
        assert data["scan_meta"] is None
        assert "No scan history available" in data["message"]

    def test_get_scan_metadata_with_data(
        self, knowledge_test_client, mock_knowledge_repo, sample_scan_meta
    ):
        """Should return scan metadata."""
        mock_knowledge_repo.set_scan_meta(sample_scan_meta)

        response = knowledge_test_client.get("/api/knowledge/scan-meta")
        assert response.status_code == 200
        data = response.json()

        assert data["scan_meta"] is not None
        assert data["scan_meta"]["scan_id"] == "scan-001"
        assert data["scan_meta"]["files_scanned"] == 150
        assert data["scan_meta"]["scan_type"] == "full"

    def test_get_coding_rules_empty(self, knowledge_test_client):
        """Should return empty rules list when none exist."""
        response = knowledge_test_client.get("/api/knowledge/coding-rules")
        assert response.status_code == 200
        data = response.json()
        assert data["rules"] == []
        assert data["count"] == 0

    def test_get_coding_rules_with_data(
        self, knowledge_test_client, mock_knowledge_repo
    ):
        """Should return coding rules."""
        rules = [
            {"rule": "snake_case", "category": "naming", "confidence": 0.9},
            {"rule": "max_line_length", "category": "structure", "confidence": 0.8},
        ]
        mock_knowledge_repo.set_coding_rules(rules)

        response = knowledge_test_client.get("/api/knowledge/coding-rules")
        assert response.status_code == 200
        data = response.json()

        assert data["count"] == 2
        assert len(data["rules"]) == 2
        assert "naming" in data["categories"]
        assert "structure" in data["categories"]

    def test_get_coding_rules_filter_by_category(
        self, knowledge_test_client, mock_knowledge_repo
    ):
        """Should filter coding rules by category."""
        rules = [
            {"rule": "snake_case", "category": "naming", "confidence": 0.9},
            {"rule": "max_line_length", "category": "structure", "confidence": 0.8},
        ]
        mock_knowledge_repo.set_coding_rules(rules)

        response = knowledge_test_client.get("/api/knowledge/coding-rules?category=naming")
        assert response.status_code == 200
        data = response.json()

        assert data["count"] == 1
        assert data["rules"][0]["category"] == "naming"

    def test_get_coding_rules_filter_by_confidence(
        self, knowledge_test_client, mock_knowledge_repo
    ):
        """Should filter coding rules by minimum confidence."""
        rules = [
            {"rule": "snake_case", "category": "naming", "confidence": 0.9},
            {"rule": "max_line_length", "category": "structure", "confidence": 0.5},
        ]
        mock_knowledge_repo.set_coding_rules(rules)

        response = knowledge_test_client.get("/api/knowledge/coding-rules?min_confidence=0.7")
        assert response.status_code == 200
        data = response.json()

        assert data["count"] == 1
        assert data["rules"][0]["confidence"] >= 0.7

    def test_clear_knowledge(
        self, knowledge_test_client, mock_knowledge_repo, sample_knowledge
    ):
        """Should clear all knowledge data."""
        mock_knowledge_repo.set_knowledge(sample_knowledge)
        assert mock_knowledge_repo.exists() is True

        response = knowledge_test_client.delete("/api/knowledge")
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "cleared"
        assert mock_knowledge_repo.exists() is False
