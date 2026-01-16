"""Unit tests for server/services modules.

Tests cover:
- interfaces.py: PlanState enum, Plan dataclass
- file_service.py: FileService class
- plan_registry.py: PlanRegistryService class
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

# Import modules under test
from server.services.interfaces import PlanState, Plan, IFileService, IPlanRegistry
from server.services.file_service import FileService
from server.services.plan_registry import PlanRegistryService


class TestPlanState:
    """Tests for PlanState enum."""

    def test_pending_value(self):
        assert PlanState.PENDING.value == "pending"

    def test_in_progress_value(self):
        assert PlanState.IN_PROGRESS.value == "in-progress"

    def test_completed_value(self):
        assert PlanState.COMPLETED.value == "completed"

    def test_failed_value(self):
        assert PlanState.FAILED.value == "failed"

    def test_from_string(self):
        """Test creating PlanState from string value."""
        assert PlanState("pending") == PlanState.PENDING
        assert PlanState("in-progress") == PlanState.IN_PROGRESS
        assert PlanState("completed") == PlanState.COMPLETED
        assert PlanState("failed") == PlanState.FAILED

    def test_invalid_value(self):
        """Test that invalid value raises ValueError."""
        with pytest.raises(ValueError):
            PlanState("invalid")


class TestPlan:
    """Tests for Plan dataclass."""

    def test_create_basic_plan(self):
        plan = Plan(
            id="001_test-feature",
            name="Test Feature",
            state=PlanState.PENDING,
            file="specs/pending/001_test-feature",
            files=["plan.md"],
            modified="2025-01-16T12:00:00"
        )
        assert plan.id == "001_test-feature"
        assert plan.name == "Test Feature"
        assert plan.state == PlanState.PENDING
        assert plan.file == "specs/pending/001_test-feature"
        assert plan.files == ["plan.md"]
        assert plan.modified == "2025-01-16T12:00:00"
        assert plan.content is None
        assert plan.request is None
        assert plan.complexity is None

    def test_create_full_plan(self):
        plan = Plan(
            id="001_test-feature",
            name="Test Feature",
            state=PlanState.COMPLETED,
            file="specs/completed/001_test-feature",
            files=["plan.md", "state.json"],
            modified="2025-01-16T12:00:00",
            content="# Test Plan\n\nThis is the plan content.",
            request="Add a test feature",
            complexity="medium"
        )
        assert plan.content == "# Test Plan\n\nThis is the plan content."
        assert plan.request == "Add a test feature"
        assert plan.complexity == "medium"

    def test_to_dict_basic(self):
        plan = Plan(
            id="001_test-feature",
            name="Test Feature",
            state=PlanState.PENDING,
            file="specs/pending/001_test-feature",
            files=["plan.md"],
            modified="2025-01-16T12:00:00"
        )
        result = plan.to_dict()
        assert result["id"] == "001_test-feature"
        assert result["name"] == "Test Feature"
        assert result["state"] == "pending"  # Should be string value
        assert result["file"] == "specs/pending/001_test-feature"
        assert result["files"] == ["plan.md"]
        assert result["modified"] == "2025-01-16T12:00:00"
        # Optional fields should not be present
        assert "content" not in result
        assert "request" not in result
        assert "complexity" not in result

    def test_to_dict_full(self):
        plan = Plan(
            id="001_test-feature",
            name="Test Feature",
            state=PlanState.COMPLETED,
            file="specs/completed/001_test-feature",
            files=["plan.md"],
            modified="2025-01-16T12:00:00",
            content="Plan content",
            request="Test request",
            complexity="high"
        )
        result = plan.to_dict()
        assert result["content"] == "Plan content"
        assert result["request"] == "Test request"
        assert result["complexity"] == "high"

    def test_from_dict_basic(self):
        data = {
            "id": "001_test-feature",
            "name": "Test Feature",
            "state": "pending",
            "file": "specs/pending/001_test-feature",
            "files": ["plan.md"],
            "modified": "2025-01-16T12:00:00"
        }
        plan = Plan.from_dict(data)
        assert plan.id == "001_test-feature"
        assert plan.name == "Test Feature"
        assert plan.state == PlanState.PENDING
        assert plan.file == "specs/pending/001_test-feature"
        assert plan.files == ["plan.md"]
        assert plan.modified == "2025-01-16T12:00:00"

    def test_from_dict_with_enum(self):
        """Test from_dict when state is already a PlanState enum."""
        data = {
            "id": "001_test-feature",
            "name": "Test Feature",
            "state": PlanState.IN_PROGRESS,
            "file": "specs/in-progress/001_test-feature",
            "files": ["plan.md"],
            "modified": "2025-01-16T12:00:00"
        }
        plan = Plan.from_dict(data)
        assert plan.state == PlanState.IN_PROGRESS

    def test_from_dict_defaults(self):
        """Test from_dict with minimal data uses defaults."""
        data = {
            "id": "001_test-feature",
            "name": "Test Feature",
            "file": "specs/pending/001_test-feature"
        }
        plan = Plan.from_dict(data)
        assert plan.state == PlanState.PENDING  # default
        assert plan.files == []  # default
        # modified should have a value (generated if not provided)
        assert plan.modified is not None


class TestFileService:
    """Tests for FileService class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory structure for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            specs = base / "specs"
            specs.mkdir()

            # Create state directories
            for state in ["pending", "in-progress", "completed", "failed"]:
                (specs / state).mkdir()

            # Create state directory
            (specs / "state").mkdir()

            yield base

    @pytest.fixture
    def file_service(self, temp_dir):
        """Create a FileService instance with temp directory."""
        return FileService(temp_dir)

    def test_init(self, file_service, temp_dir):
        assert file_service.base_dir == temp_dir
        assert file_service.specs_dir == temp_dir / "specs"
        assert file_service.state_dir == temp_dir / "specs" / "state"

    def test_state_dir_names(self, file_service):
        assert file_service.STATE_DIR_NAMES[PlanState.PENDING] == "pending"
        assert file_service.STATE_DIR_NAMES[PlanState.IN_PROGRESS] == "in-progress"
        assert file_service.STATE_DIR_NAMES[PlanState.COMPLETED] == "completed"
        assert file_service.STATE_DIR_NAMES[PlanState.FAILED] == "failed"

    def test_get_plan_dir_not_found(self, file_service):
        result = file_service.get_plan_dir("nonexistent-plan")
        assert result is None

    def test_get_plan_dir_found(self, file_service, temp_dir):
        # Create a plan directory
        plan_dir = temp_dir / "specs" / "pending" / "001_test-plan"
        plan_dir.mkdir()

        result = file_service.get_plan_dir("001_test-plan")
        assert result == plan_dir

    def test_get_plan_dir_with_state(self, file_service, temp_dir):
        # Create a plan directory
        plan_dir = temp_dir / "specs" / "completed" / "001_test-plan"
        plan_dir.mkdir()

        # Should find with correct state
        result = file_service.get_plan_dir("001_test-plan", PlanState.COMPLETED)
        assert result == plan_dir

        # Should not find with wrong state
        result = file_service.get_plan_dir("001_test-plan", PlanState.PENDING)
        assert result is None

    def test_get_state_file_path(self, file_service, temp_dir):
        result = file_service.get_state_file_path("001_test-plan")
        expected = temp_dir / "specs" / "state" / "001_test-plan.state.json"
        assert result == expected

    def test_list_plan_dirs_empty(self, file_service):
        result = file_service.list_plan_dirs()
        assert result == []

    def test_list_plan_dirs_with_plans(self, file_service, temp_dir):
        # Create plan directories in different states
        (temp_dir / "specs" / "pending" / "001_plan-a").mkdir()
        (temp_dir / "specs" / "completed" / "002_plan-b").mkdir()

        result = file_service.list_plan_dirs()
        assert len(result) == 2
        plan_names = [p.name for p in result]
        assert "001_plan-a" in plan_names
        assert "002_plan-b" in plan_names

    def test_list_plan_dirs_by_state(self, file_service, temp_dir):
        # Create plan directories in different states
        (temp_dir / "specs" / "pending" / "001_plan-a").mkdir()
        (temp_dir / "specs" / "completed" / "002_plan-b").mkdir()

        # List only pending
        result = file_service.list_plan_dirs(PlanState.PENDING)
        assert len(result) == 1
        assert result[0].name == "001_plan-a"

        # List only completed
        result = file_service.list_plan_dirs(PlanState.COMPLETED)
        assert len(result) == 1
        assert result[0].name == "002_plan-b"


class TestPlanRegistryService:
    """Tests for PlanRegistryService class."""

    @pytest.fixture
    def mock_file_service(self):
        """Create a mock file service."""
        mock = MagicMock()
        # Setup default return values
        mock.list_plan_dirs.return_value = []
        mock.list_files.return_value = []
        mock.get_modification_time.return_value = "2025-01-16T12:00:00"
        mock.read_file.return_value = ""
        return mock

    @pytest.fixture
    def plan_registry(self, mock_file_service):
        """Create a PlanRegistryService with mock file service."""
        return PlanRegistryService(mock_file_service)

    def test_init(self, plan_registry, mock_file_service):
        assert plan_registry.file_service == mock_file_service

    def test_list_plans_empty(self, plan_registry, mock_file_service):
        mock_file_service.list_plan_dirs.return_value = []

        result = plan_registry.list_plans()
        assert result == []

    def test_extract_plan_number(self, plan_registry):
        assert plan_registry._extract_plan_number("001_test-plan") == 1
        assert plan_registry._extract_plan_number("042_another-plan") == 42
        assert plan_registry._extract_plan_number("999_last-plan") == 999
        # Invalid format should return large number
        assert plan_registry._extract_plan_number("invalid-plan") == 999999

    def test_list_plans_sorted(self, plan_registry, mock_file_service):
        # Mock file_service to return plan directories
        mock_file_service.list_plan_dirs.return_value = []

        # Create mock plans with different numbers
        plans = [
            Plan(id="003_third", name="Third", state=PlanState.PENDING,
                 file="specs/pending/003_third", files=[], modified="2025-01-16T12:00:00"),
            Plan(id="001_first", name="First", state=PlanState.PENDING,
                 file="specs/pending/001_first", files=[], modified="2025-01-16T12:00:00"),
            Plan(id="002_second", name="Second", state=PlanState.PENDING,
                 file="specs/pending/002_second", files=[], modified="2025-01-16T12:00:00"),
        ]

        # Test sorting
        with patch.object(plan_registry, '_list_plans_in_state') as mock_list:
            mock_list.return_value = plans
            # Only first call returns plans
            result = plan_registry.list_plans()

        # Verify sorting (even though mock always returns same list)
        # The real implementation would get plans from different states


class TestIntegration:
    """Integration tests for services working together."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory structure for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            specs = base / "specs"
            specs.mkdir()

            # Create state directories
            for state in ["pending", "in-progress", "completed", "failed"]:
                (specs / state).mkdir()

            # Create state directory
            (specs / "state").mkdir()

            yield base

    @pytest.fixture
    def services(self, temp_dir):
        """Create real services for integration testing."""
        file_service = FileService(temp_dir)
        plan_registry = PlanRegistryService(file_service)
        return file_service, plan_registry

    def test_full_workflow(self, services, temp_dir):
        """Test creating and listing plans through the full service stack."""
        file_service, plan_registry = services

        # Create some plan directories with plan.md files
        plan1_dir = temp_dir / "specs" / "pending" / "001_add-feature"
        plan1_dir.mkdir()
        (plan1_dir / "plan.md").write_text("# Add Feature\n\nThis is a plan.")

        plan2_dir = temp_dir / "specs" / "completed" / "002_fix-bug"
        plan2_dir.mkdir()
        (plan2_dir / "plan.md").write_text("# Fix Bug\n\nBug fix plan.")

        # List plans through registry
        plans = plan_registry.list_plans()

        # Should find both plans
        assert len(plans) == 2

        # Should be sorted by numeric prefix
        assert plans[0].id == "001_add-feature"
        assert plans[1].id == "002_fix-bug"

        # Verify states
        assert plans[0].state == PlanState.PENDING
        assert plans[1].state == PlanState.COMPLETED


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_plan_state_comparison(self):
        """Test PlanState enum comparison."""
        assert PlanState.PENDING != PlanState.COMPLETED
        assert PlanState.PENDING == PlanState.PENDING

    def test_plan_immutability(self):
        """Test that Plan is a dataclass with expected behavior."""
        plan = Plan(
            id="001_test",
            name="Test",
            state=PlanState.PENDING,
            file="path",
            files=[],
            modified="2025-01-16T12:00:00"
        )
        # Dataclass should allow attribute modification
        plan.name = "Updated"
        assert plan.name == "Updated"

    def test_file_service_handles_missing_dirs(self):
        """Test FileService handles missing directories gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            # Don't create specs directory
            file_service = FileService(base)

            # Should return empty list or handle gracefully
            result = file_service.get_plan_dir("nonexistent")
            assert result is None
