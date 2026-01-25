"""Tests for project API routes.

These tests cover the multi-project management endpoints including
list, create, switch, and delete operations.
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


class MockProjectEntry:
    """Mock project entry for testing."""

    def __init__(self, **kwargs):
        self.id = kwargs.get("id", "test-uuid-123")
        self.name = kwargs.get("name", "Test Project")
        self.slug = kwargs.get("slug", "test-project")
        self.path = kwargs.get("path", "/path/to/project")
        self.status = kwargs.get("status", "active")
        self.source_type = kwargs.get("source_type", "local")
        self.git_url = kwargs.get("git_url")
        self.git_branch = kwargs.get("git_branch")
        self.description = kwargs.get("description")
        self.added_at = kwargs.get("added_at")
        self.last_accessed = kwargs.get("last_accessed")
        self.indexed_at = kwargs.get("indexed_at")


class MockProjectInfo:
    """Mock project info for testing."""

    def __init__(self, entry, **kwargs):
        self.entry = entry
        self.git_status = kwargs.get("git_status")
        self.knowledge_exists = kwargs.get("knowledge_exists", False)
        self.expert_count = kwargs.get("expert_count", 0)


class MockProjectResult:
    """Mock project operation result."""

    def __init__(self, success=True, project=None, error=None):
        self.success = success
        self.project = project
        self.error = error


class MockProjectService:
    """Mock project service for testing."""

    def __init__(self):
        self.projects = {}
        self.active_project = None
        self.repository = MagicMock()

    def add_project(self, **kwargs):
        """Add a project to the mock service."""
        project = MockProjectEntry(**kwargs)
        self.projects[project.slug] = project
        return project

    def list_projects(self, include_archived=False):
        """List all projects."""
        projects = list(self.projects.values())
        if not include_archived:
            projects = [p for p in projects if p.status != "archived"]
        return projects

    def get_active(self):
        """Get active project."""
        return self.active_project

    def get_info(self, slug_or_id):
        """Get project info."""
        project = self.projects.get(slug_or_id)
        if project:
            return MockProjectInfo(project)
        return None

    def add_local(self, path, name=None, description=None, auto_index=False):
        """Add local project."""
        project = MockProjectEntry(
            id="new-uuid-456",
            name=name or "New Project",
            slug="new-project",
            path=path,
            description=description,
            source_type="local",
        )
        self.projects[project.slug] = project
        return MockProjectResult(success=True, project=project)

    def add_git(self, url, destination, name=None, branch=None, description=None, auto_index=False):
        """Add git project."""
        project = MockProjectEntry(
            id="git-uuid-789",
            name=name or "Git Project",
            slug="git-project",
            path=destination,
            description=description,
            source_type="git",
            git_url=url,
            git_branch=branch,
        )
        self.projects[project.slug] = project
        return MockProjectResult(success=True, project=project)

    def switch(self, slug_or_id):
        """Switch active project."""
        project = self.projects.get(slug_or_id)
        if project:
            self.active_project = project
            return project
        return None

    def archive(self, slug_or_id):
        """Archive a project."""
        project = self.projects.get(slug_or_id)
        if project:
            project.status = "archived"
            return project
        return None

    def restore(self, slug_or_id):
        """Restore an archived project."""
        project = self.projects.get(slug_or_id)
        if project:
            project.status = "active"
            return project
        return None

    def remove(self, slug_or_id, delete_files=False):
        """Remove a project."""
        if slug_or_id in self.projects:
            del self.projects[slug_or_id]
            return True
        return False

    def get_git_status(self, slug_or_id):
        """Get git status for project."""
        project = self.projects.get(slug_or_id)
        if project:
            status = MagicMock()
            status.error = None
            status.to_dict = lambda: {
                "branch": "main",
                "clean": True,
                "modified_files": [],
            }
            return status
        return None

    def fetch(self, slug_or_id):
        """Git fetch for project."""
        if slug_or_id in self.projects:
            return {"success": True, "output": "Already up to date."}
        return None

    def pull(self, slug_or_id):
        """Git pull for project."""
        if slug_or_id in self.projects:
            return {"success": True, "output": "Already up to date."}
        return None


@pytest.fixture
def mock_project_service():
    """Create a mock project service."""
    return MockProjectService()


@pytest.fixture
def mock_multi_project_mode():
    """Mock the multi-project mode check."""
    with patch("portal.routes.projects._check_multi_project_mode") as mock:
        yield mock


@pytest.fixture
def project_test_client(mock_project_service, mock_multi_project_mode):
    """Create a test client with mocked project service."""
    import sys
    from pathlib import Path

    orchestrator_dir = Path(__file__).parent.parent
    sys.path.insert(0, str(orchestrator_dir))

    from portal.app import app

    with patch("portal.routes.projects._get_project_service", return_value=mock_project_service):
        client = TestClient(app)
        yield client


class TestProjectRoutes:
    """Tests for project API routes."""

    def test_list_projects_empty(self, project_test_client, mock_project_service):
        """Should return empty list when no projects exist."""
        response = project_test_client.get("/api/projects/")
        assert response.status_code == 200
        data = response.json()
        assert data["projects"] == []
        assert data["total"] == 0
        assert data["active_project"] is None

    def test_list_projects_with_data(self, project_test_client, mock_project_service):
        """Should return list of projects."""
        mock_project_service.add_project(
            id="proj-1",
            name="Project One",
            slug="project-one",
            path="/path/one",
        )
        mock_project_service.add_project(
            id="proj-2",
            name="Project Two",
            slug="project-two",
            path="/path/two",
        )

        response = project_test_client.get("/api/projects/")
        assert response.status_code == 200
        data = response.json()
        assert len(data["projects"]) == 2
        assert data["total"] == 2

    def test_list_projects_excludes_archived(self, project_test_client, mock_project_service):
        """Should exclude archived projects by default."""
        mock_project_service.add_project(slug="active-proj", status="active")
        mock_project_service.add_project(slug="archived-proj", status="archived")

        response = project_test_client.get("/api/projects/")
        assert response.status_code == 200
        data = response.json()
        assert len(data["projects"]) == 1
        assert data["projects"][0]["slug"] == "active-proj"

    def test_list_projects_include_archived(self, project_test_client, mock_project_service):
        """Should include archived projects when requested."""
        mock_project_service.add_project(slug="active-proj", status="active")
        mock_project_service.add_project(slug="archived-proj", status="archived")

        response = project_test_client.get("/api/projects/?include_archived=true")
        assert response.status_code == 200
        data = response.json()
        assert len(data["projects"]) == 2

    def test_get_active_project_none(self, project_test_client, mock_project_service):
        """Should return null when no active project."""
        response = project_test_client.get("/api/projects/active")
        assert response.status_code == 200
        assert response.json() is None

    def test_get_active_project(self, project_test_client, mock_project_service):
        """Should return active project."""
        project = mock_project_service.add_project(slug="my-project", name="My Project")
        mock_project_service.active_project = project

        response = project_test_client.get("/api/projects/active")
        assert response.status_code == 200
        data = response.json()
        assert data["slug"] == "my-project"
        assert data["name"] == "My Project"

    def test_get_project_by_slug(self, project_test_client, mock_project_service):
        """Should return project details by slug."""
        mock_project_service.add_project(
            slug="my-project",
            name="My Project",
            path="/path/to/project",
            description="Test description",
        )

        response = project_test_client.get("/api/projects/my-project")
        assert response.status_code == 200
        data = response.json()
        assert data["project"]["slug"] == "my-project"
        assert data["project"]["name"] == "My Project"
        assert data["knowledge_exists"] is False

    def test_get_project_not_found(self, project_test_client, mock_project_service):
        """Should return 404 for non-existent project."""
        response = project_test_client.get("/api/projects/nonexistent")
        assert response.status_code == 404

    def test_add_local_project(self, project_test_client, mock_project_service):
        """Should add a local project."""
        response = project_test_client.post(
            "/api/projects/local",
            json={
                "path": "/path/to/new/project",
                "name": "New Local Project",
                "description": "A test project",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Project"
        assert data["source_type"] == "local"

    def test_add_git_project(self, project_test_client, mock_project_service):
        """Should add a git project."""
        response = project_test_client.post(
            "/api/projects/git",
            json={
                "url": "https://github.com/example/repo.git",
                "destination": "/path/to/clone",
                "name": "Git Project",
                "branch": "main",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["source_type"] == "git"
        assert data["git_url"] == "https://github.com/example/repo.git"

    def test_activate_project(self, project_test_client, mock_project_service):
        """Should activate/switch to a project."""
        mock_project_service.add_project(slug="target-project", name="Target Project")

        response = project_test_client.post("/api/projects/target-project/activate")
        assert response.status_code == 200
        data = response.json()
        assert data["slug"] == "target-project"

    def test_activate_project_not_found(self, project_test_client, mock_project_service):
        """Should return 404 when activating non-existent project."""
        response = project_test_client.post("/api/projects/nonexistent/activate")
        assert response.status_code == 404

    def test_archive_project(self, project_test_client, mock_project_service):
        """Should archive a project."""
        mock_project_service.add_project(slug="to-archive", status="active")

        response = project_test_client.post("/api/projects/to-archive/archive")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "archived"

    def test_restore_project(self, project_test_client, mock_project_service):
        """Should restore an archived project."""
        mock_project_service.add_project(slug="to-restore", status="archived")

        response = project_test_client.post("/api/projects/to-restore/restore")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"

    def test_delete_project(self, project_test_client, mock_project_service):
        """Should delete a project."""
        mock_project_service.add_project(slug="to-delete", name="To Delete")
        mock_project_service.repository.get_by_slug_or_id.return_value = {
            "name": "To Delete",
            "slug": "to-delete",
        }

        response = project_test_client.delete("/api/projects/to-delete")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "To Delete" in data["message"]

    def test_delete_project_not_found(self, project_test_client, mock_project_service):
        """Should return 404 when deleting non-existent project."""
        mock_project_service.repository.get_by_slug_or_id.return_value = None

        response = project_test_client.delete("/api/projects/nonexistent")
        assert response.status_code == 404

    def test_get_git_status(self, project_test_client, mock_project_service):
        """Should return git status for a project."""
        mock_project_service.add_project(slug="git-project", source_type="git")

        response = project_test_client.get("/api/projects/git-project/git/status")
        assert response.status_code == 200
        data = response.json()
        assert data["branch"] == "main"
        assert data["clean"] is True

    def test_git_fetch(self, project_test_client, mock_project_service):
        """Should perform git fetch for a project."""
        mock_project_service.add_project(slug="git-project", source_type="git")

        response = project_test_client.post("/api/projects/git-project/git/fetch")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_git_pull(self, project_test_client, mock_project_service):
        """Should perform git pull for a project."""
        mock_project_service.add_project(slug="git-project", source_type="git")

        response = project_test_client.post("/api/projects/git-project/git/pull")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_index_project(self, project_test_client, mock_project_service):
        """Should start indexing for a project."""
        mock_project_service.add_project(slug="to-index", name="To Index")
        mock_project_service.repository.get_by_slug_or_id.return_value = {
            "name": "To Index",
            "slug": "to-index",
        }

        response = project_test_client.post("/api/projects/to-index/index")
        assert response.status_code == 200
        data = response.json()
        assert "Indexing started" in data["message"]


class TestProjectRoutesMultiProjectDisabled:
    """Tests for project routes when multi-project mode is disabled."""

    def test_list_projects_multi_project_disabled(self, test_client):
        """Should return 400 when multi-project mode is disabled."""
        with patch("portal.routes.projects._check_multi_project_mode") as mock_check:
            from fastapi import HTTPException
            mock_check.side_effect = HTTPException(
                status_code=400,
                detail="Multi-project mode is not enabled."
            )

            response = test_client.get("/api/projects/")
            assert response.status_code == 400
            assert "Multi-project mode" in response.json()["detail"]
