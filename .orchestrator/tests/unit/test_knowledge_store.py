"""
Unit tests for KnowledgeStore class.
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime


class TestKnowledgeStoreInit:
    """Tests for KnowledgeStore initialization."""

    @pytest.fixture
    def mock_repo(self):
        """Create a mocked knowledge repository."""
        return Mock()

    def test_initialization_with_project_root(self, tmp_path, mock_repo):
        """Test KnowledgeStore initializes with project root."""
        with patch('core.knowledge_store.get_knowledge_repository', return_value=mock_repo):
            from core.knowledge_store import KnowledgeStore

            store = KnowledgeStore(tmp_path)

            assert store.project_root == tmp_path.resolve()

    def test_initialization_with_project_id(self, tmp_path, mock_repo):
        """Test KnowledgeStore initializes with explicit project ID."""
        with patch('core.knowledge_store.get_knowledge_repository', return_value=mock_repo):
            from core.knowledge_store import KnowledgeStore

            store = KnowledgeStore(tmp_path, project_id="test-project-123")

            assert store._project_id == "test-project-123"

    def test_project_id_property_returns_explicit_id(self, tmp_path, mock_repo):
        """Test project_id property returns explicit ID when set."""
        with patch('core.knowledge_store.get_knowledge_repository', return_value=mock_repo):
            from core.knowledge_store import KnowledgeStore

            store = KnowledgeStore(tmp_path, project_id="explicit-id")

            assert store.project_id == "explicit-id"

    def test_project_id_property_returns_context_id(self, tmp_path, mock_repo):
        """Test project_id property returns context ID when no explicit ID."""
        with patch('core.knowledge_store.get_knowledge_repository', return_value=mock_repo):
            with patch('core.knowledge_store.get_optional_project_id', return_value="context-id"):
                from core.knowledge_store import KnowledgeStore

                store = KnowledgeStore(tmp_path)

                assert store.project_id == "context-id"


class TestKnowledgeStoreExists:
    """Tests for KnowledgeStore.exists() method."""

    @pytest.fixture
    def mock_repo(self):
        """Create a mocked knowledge repository."""
        return Mock()

    def test_exists_returns_true_when_knowledge_exists(self, tmp_path, mock_repo):
        """Test exists returns True when repository has knowledge."""
        mock_repo.exists.return_value = True

        with patch('core.knowledge_store.get_knowledge_repository', return_value=mock_repo):
            from core.knowledge_store import KnowledgeStore

            store = KnowledgeStore(tmp_path)

            assert store.exists() is True
            mock_repo.exists.assert_called_once()

    def test_exists_returns_false_when_no_knowledge(self, tmp_path, mock_repo):
        """Test exists returns False when repository has no knowledge."""
        mock_repo.exists.return_value = False

        with patch('core.knowledge_store.get_knowledge_repository', return_value=mock_repo):
            from core.knowledge_store import KnowledgeStore

            store = KnowledgeStore(tmp_path)

            assert store.exists() is False


class TestKnowledgeStoreLoad:
    """Tests for KnowledgeStore.load() method."""

    @pytest.fixture
    def mock_repo(self):
        """Create a mocked knowledge repository."""
        return Mock()

    @pytest.fixture
    def sample_knowledge_data(self):
        """Create sample knowledge data for testing."""
        return {
            "version": "1.0",
            "last_updated": "2024-01-15T10:00:00",
            "project": {
                "name": "test-project",
                "type": "web_api",
                "primary_language": "Python",
            },
            "technologies": {
                "languages": [{"name": "Python", "confidence": 0.9, "version": "3.11"}],
                "frameworks": [{"name": "FastAPI", "confidence": 0.85, "version": "0.100"}],
                "tools": [{"name": "pytest", "confidence": 0.8}],
            },
            "architecture": {
                "pattern": "layered",
                "modules": [
                    {"name": "api", "path": "src/api", "purpose": "REST endpoints", "depends_on": ["services"]},
                ],
                "entry_points": ["src/main.py"],
            },
            "domains": [
                {
                    "name": "users",
                    "keywords": ["user", "auth", "login"],
                    "files": ["src/users.py"],
                    "models": ["User"],
                    "routes": ["/users"],
                }
            ],
            "patterns": {
                "naming": {"files": "snake_case", "classes": "PascalCase"},
                "structure": {"routes_in": "src/api"},
                "conventions": ["Type hints required"],
            },
            "statistics": {"total_files": 50, "total_lines": 5000},
        }

    def test_load_returns_knowledge_when_exists(self, tmp_path, mock_repo, sample_knowledge_data):
        """Test load returns CodebaseKnowledge when data exists."""
        mock_repo.load_knowledge.return_value = sample_knowledge_data

        with patch('core.knowledge_store.get_knowledge_repository', return_value=mock_repo):
            from core.knowledge_store import KnowledgeStore, CodebaseKnowledge

            store = KnowledgeStore(tmp_path)
            knowledge = store.load()

            assert knowledge is not None
            assert isinstance(knowledge, CodebaseKnowledge)
            assert knowledge.project.name == "test-project"
            assert knowledge.project.type == "web_api"
            assert knowledge.project.primary_language == "Python"
            assert knowledge.architecture.pattern == "layered"
            assert len(knowledge.technologies.languages) == 1
            assert knowledge.technologies.languages[0].name == "Python"

    def test_load_returns_none_when_no_data(self, tmp_path, mock_repo):
        """Test load returns None when no knowledge exists."""
        mock_repo.load_knowledge.return_value = None

        with patch('core.knowledge_store.get_knowledge_repository', return_value=mock_repo):
            from core.knowledge_store import KnowledgeStore

            store = KnowledgeStore(tmp_path)
            knowledge = store.load()

            assert knowledge is None

    def test_load_handles_exception_gracefully(self, tmp_path, mock_repo):
        """Test load handles exceptions and returns None."""
        mock_repo.load_knowledge.return_value = {"invalid": "data structure"}

        with patch('core.knowledge_store.get_knowledge_repository', return_value=mock_repo):
            from core.knowledge_store import KnowledgeStore

            store = KnowledgeStore(tmp_path)
            # Invalid structure should be handled gracefully
            knowledge = store.load()

            # Either returns None or a partial knowledge object
            assert knowledge is None or hasattr(knowledge, 'project')


class TestKnowledgeStoreSave:
    """Tests for KnowledgeStore.save() method."""

    @pytest.fixture
    def mock_repo(self):
        """Create a mocked knowledge repository."""
        return Mock()

    @pytest.fixture
    def sample_knowledge(self):
        """Create sample CodebaseKnowledge for testing."""
        with patch('core.knowledge_store.get_knowledge_repository'):
            from core.knowledge_store import (
                CodebaseKnowledge,
                ProjectInfo,
                TechnologiesInfo,
                ArchitectureInfo,
                TechInfo,
                ModuleInfo,
                DomainInfo,
                PatternInfo,
            )

            return CodebaseKnowledge(
                version="1.0",
                project=ProjectInfo(
                    name="test-project",
                    type="web_api",
                    primary_language="Python",
                ),
                technologies=TechnologiesInfo(
                    languages=[TechInfo(name="Python", confidence=0.9, version="3.11")],
                    frameworks=[TechInfo(name="FastAPI", confidence=0.85)],
                    tools=[TechInfo(name="pytest", confidence=0.8)],
                ),
                architecture=ArchitectureInfo(
                    pattern="layered",
                    modules=[
                        ModuleInfo(name="api", path="src/api", purpose="REST endpoints", depends_on=["services"])
                    ],
                    entry_points=["src/main.py"],
                ),
                domains=[
                    DomainInfo(
                        name="users",
                        keywords=["user", "auth"],
                        files=["src/users.py"],
                        models=["User"],
                        routes=["/users"],
                    )
                ],
                patterns=PatternInfo(
                    naming={"files": "snake_case"},
                    structure={"routes_in": "src/api"},
                    conventions=["Type hints required"],
                ),
                statistics={"total_files": 50},
            )

    def test_save_returns_true_on_success(self, tmp_path, mock_repo, sample_knowledge):
        """Test save returns True on successful save."""
        mock_repo.save_knowledge.return_value = None

        with patch('core.knowledge_store.get_knowledge_repository', return_value=mock_repo):
            from core.knowledge_store import KnowledgeStore

            store = KnowledgeStore(tmp_path)
            result = store.save(sample_knowledge)

            assert result is True
            mock_repo.save_knowledge.assert_called_once()

    def test_save_updates_last_updated(self, tmp_path, mock_repo, sample_knowledge):
        """Test save updates last_updated timestamp."""
        mock_repo.save_knowledge.return_value = None
        original_timestamp = sample_knowledge.last_updated

        with patch('core.knowledge_store.get_knowledge_repository', return_value=mock_repo):
            from core.knowledge_store import KnowledgeStore

            store = KnowledgeStore(tmp_path)
            store.save(sample_knowledge)

            # Timestamp should be updated
            assert sample_knowledge.last_updated != original_timestamp
            assert sample_knowledge.last_updated != ""

    def test_save_calls_repository_with_correct_data(self, tmp_path, mock_repo, sample_knowledge):
        """Test save calls repository with correctly formatted data."""
        mock_repo.save_knowledge.return_value = None

        with patch('core.knowledge_store.get_knowledge_repository', return_value=mock_repo):
            from core.knowledge_store import KnowledgeStore

            store = KnowledgeStore(tmp_path)
            store.save(sample_knowledge)

            call_kwargs = mock_repo.save_knowledge.call_args.kwargs
            assert call_kwargs['project_name'] == "test-project"
            assert call_kwargs['project_type'] == "web_api"
            assert call_kwargs['primary_language'] == "Python"
            assert call_kwargs['architecture_pattern'] == "layered"
            assert len(call_kwargs['languages']) == 1
            assert call_kwargs['languages'][0]['name'] == "Python"

    def test_save_returns_false_on_exception(self, tmp_path, mock_repo, sample_knowledge):
        """Test save returns False when repository raises exception."""
        mock_repo.save_knowledge.side_effect = Exception("Database error")

        with patch('core.knowledge_store.get_knowledge_repository', return_value=mock_repo):
            from core.knowledge_store import KnowledgeStore

            store = KnowledgeStore(tmp_path)
            result = store.save(sample_knowledge)

            assert result is False


class TestKnowledgeStoreUpdate:
    """Tests for KnowledgeStore update operations (load + save)."""

    @pytest.fixture
    def mock_repo(self):
        """Create a mocked knowledge repository."""
        return Mock()

    @pytest.fixture
    def sample_knowledge_data(self):
        """Create sample knowledge data for testing."""
        return {
            "version": "1.0",
            "last_updated": "2024-01-15T10:00:00",
            "project": {
                "name": "test-project",
                "type": "web_api",
                "primary_language": "Python",
            },
            "technologies": {
                "languages": [{"name": "Python", "confidence": 0.9}],
                "frameworks": [],
                "tools": [],
            },
            "architecture": {
                "pattern": "unknown",
                "modules": [],
                "entry_points": [],
            },
            "domains": [],
            "patterns": {
                "naming": {},
                "structure": {},
                "conventions": [],
            },
            "statistics": {},
        }

    def test_update_workflow_load_modify_save(self, tmp_path, mock_repo, sample_knowledge_data):
        """Test typical update workflow: load, modify, save."""
        mock_repo.load_knowledge.return_value = sample_knowledge_data
        mock_repo.save_knowledge.return_value = None

        with patch('core.knowledge_store.get_knowledge_repository', return_value=mock_repo):
            from core.knowledge_store import KnowledgeStore, TechInfo

            store = KnowledgeStore(tmp_path)

            # Load existing knowledge
            knowledge = store.load()
            assert knowledge is not None

            # Modify it
            knowledge.technologies.frameworks.append(
                TechInfo(name="Django", confidence=0.7)
            )

            # Save it back
            result = store.save(knowledge)

            assert result is True
            mock_repo.save_knowledge.assert_called_once()

            # Verify the save included the new framework
            call_kwargs = mock_repo.save_knowledge.call_args.kwargs
            assert any(fw['name'] == 'Django' for fw in call_kwargs['frameworks'])


class TestKnowledgeStoreHasIndex:
    """Tests for KnowledgeStore.has_index() method."""

    @pytest.fixture
    def mock_repo(self):
        """Create a mocked knowledge repository."""
        return Mock()

    def test_has_index_returns_true_when_index_exists(self, tmp_path, mock_repo):
        """Test has_index returns True when expert index exists."""
        mock_repo.has_expert_index.return_value = True

        with patch('core.knowledge_store.get_knowledge_repository', return_value=mock_repo):
            from core.knowledge_store import KnowledgeStore

            store = KnowledgeStore(tmp_path)

            assert store.has_index() is True

    def test_has_index_returns_false_when_no_index(self, tmp_path, mock_repo):
        """Test has_index returns False when no expert index."""
        mock_repo.has_expert_index.return_value = False

        with patch('core.knowledge_store.get_knowledge_repository', return_value=mock_repo):
            from core.knowledge_store import KnowledgeStore

            store = KnowledgeStore(tmp_path)

            assert store.has_index() is False


class TestKnowledgeStoreClear:
    """Tests for KnowledgeStore.clear() method."""

    @pytest.fixture
    def mock_repo(self):
        """Create a mocked knowledge repository."""
        return Mock()

    def test_clear_calls_repository_clear(self, tmp_path, mock_repo):
        """Test clear delegates to repository."""
        with patch('core.knowledge_store.get_knowledge_repository', return_value=mock_repo):
            from core.knowledge_store import KnowledgeStore

            store = KnowledgeStore(tmp_path)
            store.clear()

            mock_repo.clear.assert_called_once()


class TestKnowledgeStoreExpertIndex:
    """Tests for KnowledgeStore expert index operations."""

    @pytest.fixture
    def mock_repo(self):
        """Create a mocked knowledge repository."""
        return Mock()

    @pytest.fixture
    def sample_index_data(self):
        """Create sample expert index data."""
        return {
            "version": "1.0",
            "last_updated": "2024-01-15T10:00:00",
            "experts": [
                {
                    "name": "python-expert",
                    "type": "tech",
                    "file": "experts/python.md",
                    "triggers": {
                        "keywords": ["python", "pip"],
                        "paths": ["*.py"],
                        "topics": ["python development"],
                    },
                    "weight": 1.0,
                }
            ],
            "keyword_map": {"python": ["python-expert"]},
            "path_map": {"*.py": ["python-expert"]},
        }

    def test_load_index_returns_expert_index(self, tmp_path, mock_repo, sample_index_data):
        """Test load_index returns ExpertIndex when data exists."""
        mock_repo.load_expert_index.return_value = sample_index_data

        with patch('core.knowledge_store.get_knowledge_repository', return_value=mock_repo):
            from core.knowledge_store import KnowledgeStore, ExpertIndex

            store = KnowledgeStore(tmp_path)
            index = store.load_index()

            assert index is not None
            assert isinstance(index, ExpertIndex)
            assert len(index.experts) == 1
            assert index.experts[0].name == "python-expert"

    def test_load_index_returns_none_when_no_data(self, tmp_path, mock_repo):
        """Test load_index returns None when no index exists."""
        mock_repo.load_expert_index.return_value = None

        with patch('core.knowledge_store.get_knowledge_repository', return_value=mock_repo):
            from core.knowledge_store import KnowledgeStore

            store = KnowledgeStore(tmp_path)
            index = store.load_index()

            assert index is None

    def test_save_index_returns_true_on_success(self, tmp_path, mock_repo):
        """Test save_index returns True on success."""
        mock_repo.save_expert_index.return_value = None

        with patch('core.knowledge_store.get_knowledge_repository', return_value=mock_repo):
            from core.knowledge_store import (
                KnowledgeStore,
                ExpertIndex,
                ExpertIndexEntry,
                ExpertTriggers,
            )

            index = ExpertIndex(
                version="1.0",
                experts=[
                    ExpertIndexEntry(
                        name="test-expert",
                        type="tech",
                        file="experts/test.md",
                        triggers=ExpertTriggers(keywords=["test"]),
                    )
                ],
            )

            store = KnowledgeStore(tmp_path)
            result = store.save_index(index)

            assert result is True
            mock_repo.save_expert_index.assert_called_once()


class TestKnowledgeStoreScanMeta:
    """Tests for KnowledgeStore scan metadata operations."""

    @pytest.fixture
    def mock_repo(self):
        """Create a mocked knowledge repository."""
        return Mock()

    @pytest.fixture
    def sample_meta_data(self):
        """Create sample scan metadata."""
        return {
            "scan_id": "scan-123",
            "started_at": "2024-01-15T10:00:00",
            "completed_at": "2024-01-15T10:05:00",
            "duration_seconds": 300,
            "files_scanned": 100,
            "scan_type": "full",
            "trigger_type": "manual",
            "experts_generated": ["python-expert", "fastapi-expert"],
        }

    def test_load_meta_returns_scan_meta(self, tmp_path, mock_repo, sample_meta_data):
        """Test load_meta returns ScanMeta when data exists."""
        mock_repo.load_scan_meta.return_value = sample_meta_data

        with patch('core.knowledge_store.get_knowledge_repository', return_value=mock_repo):
            from core.knowledge_store import KnowledgeStore, ScanMeta

            store = KnowledgeStore(tmp_path)
            meta = store.load_meta()

            assert meta is not None
            assert isinstance(meta, ScanMeta)
            assert meta.scan_id == "scan-123"
            assert meta.files_scanned == 100
            assert meta.scan_type == "full"

    def test_load_meta_returns_none_when_no_data(self, tmp_path, mock_repo):
        """Test load_meta returns None when no metadata exists."""
        mock_repo.load_scan_meta.return_value = None

        with patch('core.knowledge_store.get_knowledge_repository', return_value=mock_repo):
            from core.knowledge_store import KnowledgeStore

            store = KnowledgeStore(tmp_path)
            meta = store.load_meta()

            assert meta is None

    def test_save_meta_returns_true_on_success(self, tmp_path, mock_repo):
        """Test save_meta returns True on success."""
        mock_repo.save_scan_meta.return_value = None

        with patch('core.knowledge_store.get_knowledge_repository', return_value=mock_repo):
            from core.knowledge_store import KnowledgeStore, ScanMeta

            meta = ScanMeta(
                scan_id="scan-456",
                started_at="2024-01-15T11:00:00",
                completed_at="2024-01-15T11:05:00",
                duration_seconds=300,
                files_scanned=50,
                scan_type="incremental",
                trigger="auto",
            )

            store = KnowledgeStore(tmp_path)
            result = store.save_meta(meta)

            assert result is True
            mock_repo.save_scan_meta.assert_called_once()


class TestKnowledgeStorePlanningContext:
    """Tests for KnowledgeStore.get_planning_context() method."""

    @pytest.fixture
    def mock_repo(self):
        """Create a mocked knowledge repository."""
        return Mock()

    @pytest.fixture
    def sample_knowledge_data(self):
        """Create sample knowledge data for context testing."""
        return {
            "version": "1.0",
            "last_updated": "2024-01-15T10:00:00",
            "project": {
                "name": "test-project",
                "type": "web_api",
                "primary_language": "Python",
            },
            "technologies": {
                "languages": [{"name": "Python", "confidence": 0.9}],
                "frameworks": [{"name": "FastAPI", "confidence": 0.85, "entry_point": "main.py"}],
                "tools": [{"name": "pytest", "confidence": 0.8}],
            },
            "architecture": {
                "pattern": "layered",
                "modules": [
                    {"name": "api", "path": "src/api", "purpose": "REST endpoints", "depends_on": ["services"]},
                    {"name": "services", "path": "src/services", "purpose": "Business logic", "depends_on": []},
                ],
                "entry_points": ["src/main.py"],
            },
            "domains": [
                {
                    "name": "users",
                    "keywords": ["user", "auth", "login"],
                    "files": ["src/users.py", "src/auth.py"],
                    "models": ["User"],
                    "routes": ["/users"],
                }
            ],
            "patterns": {
                "naming": {"files": "snake_case"},
                "structure": {"routes_in": "src/api"},
                "conventions": ["Type hints required", "Use docstrings"],
            },
            "statistics": {"total_files": 50},
        }

    def test_get_planning_context_returns_formatted_string(self, tmp_path, mock_repo, sample_knowledge_data):
        """Test get_planning_context returns formatted context string."""
        mock_repo.load_knowledge.return_value = sample_knowledge_data

        with patch('core.knowledge_store.get_knowledge_repository', return_value=mock_repo):
            from core.knowledge_store import KnowledgeStore

            store = KnowledgeStore(tmp_path)
            context = store.get_planning_context()

            assert isinstance(context, str)
            assert "test-project" in context
            assert "Python" in context
            assert "FastAPI" in context

    def test_get_planning_context_respects_max_chars(self, tmp_path, mock_repo, sample_knowledge_data):
        """Test get_planning_context truncates at max_chars."""
        mock_repo.load_knowledge.return_value = sample_knowledge_data

        with patch('core.knowledge_store.get_knowledge_repository', return_value=mock_repo):
            from core.knowledge_store import KnowledgeStore

            store = KnowledgeStore(tmp_path)
            context = store.get_planning_context(max_chars=100)

            assert len(context) <= 100
            if len(context) == 100:
                assert context.endswith("...")

    def test_get_planning_context_returns_empty_when_no_knowledge(self, tmp_path, mock_repo):
        """Test get_planning_context returns empty string when no knowledge."""
        mock_repo.load_knowledge.return_value = None

        with patch('core.knowledge_store.get_knowledge_repository', return_value=mock_repo):
            from core.knowledge_store import KnowledgeStore

            store = KnowledgeStore(tmp_path)
            context = store.get_planning_context()

            assert context == ""

    def test_get_planning_context_includes_layered_integration_pattern(self, tmp_path, mock_repo, sample_knowledge_data):
        """Test get_planning_context includes integration pattern for layered architecture."""
        mock_repo.load_knowledge.return_value = sample_knowledge_data

        with patch('core.knowledge_store.get_knowledge_repository', return_value=mock_repo):
            from core.knowledge_store import KnowledgeStore

            store = KnowledgeStore(tmp_path)
            context = store.get_planning_context(max_chars=10000)

            # Should include integration pattern for layered architecture
            assert "Integration Pattern" in context or "layered" in context.lower()


class TestKnowledgeStoreDomainKeywords:
    """Tests for KnowledgeStore domain keyword methods."""

    @pytest.fixture
    def mock_repo(self):
        """Create a mocked knowledge repository."""
        return Mock()

    @pytest.fixture
    def sample_knowledge_data(self):
        """Create sample knowledge data with domains."""
        return {
            "version": "1.0",
            "last_updated": "2024-01-15T10:00:00",
            "project": {"name": "test", "type": "web_api", "primary_language": "Python"},
            "technologies": {"languages": [], "frameworks": [], "tools": []},
            "architecture": {"pattern": "unknown", "modules": [], "entry_points": []},
            "domains": [
                {"name": "users", "keywords": ["user", "auth"], "files": [], "models": [], "routes": []},
                {"name": "products", "keywords": ["product", "catalog"], "files": [], "models": [], "routes": []},
            ],
            "patterns": {"naming": {}, "structure": {}, "conventions": []},
            "statistics": {},
        }

    def test_get_domain_keywords_returns_mapping(self, tmp_path, mock_repo, sample_knowledge_data):
        """Test get_domain_keywords returns domain to keywords mapping."""
        mock_repo.load_knowledge.return_value = sample_knowledge_data

        with patch('core.knowledge_store.get_knowledge_repository', return_value=mock_repo):
            from core.knowledge_store import KnowledgeStore

            store = KnowledgeStore(tmp_path)
            keywords = store.get_domain_keywords()

            assert "users" in keywords
            assert "products" in keywords
            assert "user" in keywords["users"]
            assert "product" in keywords["products"]

    def test_get_domain_keywords_returns_empty_when_no_knowledge(self, tmp_path, mock_repo):
        """Test get_domain_keywords returns empty dict when no knowledge."""
        mock_repo.load_knowledge.return_value = None

        with patch('core.knowledge_store.get_knowledge_repository', return_value=mock_repo):
            from core.knowledge_store import KnowledgeStore

            store = KnowledgeStore(tmp_path)
            keywords = store.get_domain_keywords()

            assert keywords == {}

    def test_get_all_keywords_returns_set(self, tmp_path, mock_repo, sample_knowledge_data):
        """Test get_all_keywords returns set of all keywords."""
        mock_repo.load_knowledge.return_value = sample_knowledge_data

        with patch('core.knowledge_store.get_knowledge_repository', return_value=mock_repo):
            from core.knowledge_store import KnowledgeStore

            store = KnowledgeStore(tmp_path)
            keywords = store.get_all_keywords()

            assert isinstance(keywords, set)
            assert "user" in keywords
            assert "auth" in keywords
            assert "product" in keywords
            assert "catalog" in keywords

    def test_get_all_keywords_returns_empty_when_no_knowledge(self, tmp_path, mock_repo):
        """Test get_all_keywords returns empty set when no knowledge."""
        mock_repo.load_knowledge.return_value = None

        with patch('core.knowledge_store.get_knowledge_repository', return_value=mock_repo):
            from core.knowledge_store import KnowledgeStore

            store = KnowledgeStore(tmp_path)
            keywords = store.get_all_keywords()

            assert keywords == set()
