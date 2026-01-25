"""
Project Service: High-level project management operations.

This service uses the database repository directly for project management.
The database is the single source of truth - no file-based registry is needed.
"""
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from core.git_manager import GitManager, get_git_manager, GitStatus
from core.home import get_orchestrator_home, OrchestratorHome
from db.models import ProjectStatus, ProjectSourceType
from db.repositories.project import ProjectRepository, get_project_repository

logger = logging.getLogger(__name__)


@dataclass
class ProjectInfo:
    """Combined project information from database and git."""
    entry: Dict[str, Any]  # Project dict from repository
    git_status: Optional[GitStatus] = None
    knowledge_exists: bool = False
    expert_count: int = 0


@dataclass
class AddProjectResult:
    """Result of adding a project."""
    success: bool
    project: Optional[Dict[str, Any]] = None  # Project dict from repository
    error: Optional[str] = None


class ProjectService:
    """
    High-level project management service.

    Uses database repository directly for unified project management.
    The database is the single source of truth.

    Usage:
        service = ProjectService()

        # Add a local project
        result = service.add_local("/path/to/project", name="My Project")

        # Add a git project
        result = service.add_git(
            "https://github.com/user/repo",
            destination="/path/to/clone",
            branch="main"
        )

        # Switch projects
        project = service.switch("my-project")

        # Get project info
        info = service.get_info("my-project")

        # List projects
        projects = service.list_projects()
    """

    def __init__(
        self,
        repository: ProjectRepository = None,
        git_manager: GitManager = None,
        home: OrchestratorHome = None
    ):
        """
        Initialize ProjectService.

        Args:
            repository: Project repository (default: singleton).
            git_manager: Git manager (default: singleton).
            home: Orchestrator home (default: from env).
        """
        self._repository = repository
        self._git = git_manager or get_git_manager()
        self._home = home

    @property
    def repository(self) -> ProjectRepository:
        """Get the project repository (lazy load)."""
        if self._repository is None:
            self._repository = get_project_repository()
        return self._repository

    @property
    def home(self) -> OrchestratorHome:
        """Get orchestrator home (lazy load)."""
        if self._home is None:
            self._home = get_orchestrator_home()
        return self._home

    def add_local(
        self,
        path: str,
        name: str = None,
        description: str = None,
        auto_index: bool = False
    ) -> AddProjectResult:
        """
        Add a local project.

        Args:
            path: Path to existing project directory.
            name: Project name (default: directory name).
            description: Project description.
            auto_index: Automatically run scout after adding.

        Returns:
            AddProjectResult with status and project dict.
        """
        path = Path(path).resolve()

        # Validate path
        if not path.exists():
            return AddProjectResult(success=False, error=f"Path does not exist: {path}")

        if not path.is_dir():
            return AddProjectResult(success=False, error=f"Path is not a directory: {path}")

        # Check if already registered
        existing = self.repository.get_by_path(str(path), as_dict=True)
        if existing:
            return AddProjectResult(
                success=False,
                error=f"Project already registered as '{existing['name']}' ({existing['slug']})"
            )

        # Determine name
        if not name:
            name = path.name

        try:
            # Create project directly in database
            project = self.repository.create_with_auto_slug(
                name=name,
                path=str(path),
                source_type=ProjectSourceType.LOCAL,
                description=description,
            )

            # Create project data directory
            self.home.ensure_project_structure(project['slug'])

            # Set status to ready
            self.repository.update_status(project['id'], ProjectStatus.READY)

            logger.info(f"Added local project: {name} at {path}")

            return AddProjectResult(success=True, project=project)

        except Exception as e:
            logger.error(f"Failed to add project: {e}")
            return AddProjectResult(success=False, error=str(e))

    def add_git(
        self,
        url: str,
        destination: str,
        name: str = None,
        branch: str = None,
        description: str = None,
        auto_index: bool = False
    ) -> AddProjectResult:
        """
        Add a project by cloning a git repository.

        Args:
            url: Git repository URL.
            destination: Local destination path.
            name: Project name (default: from URL).
            branch: Branch to clone.
            description: Project description.
            auto_index: Automatically run scout after adding.

        Returns:
            AddProjectResult with status and project dict.
        """
        dest_path = Path(destination).resolve()

        # Validate destination
        if dest_path.exists():
            return AddProjectResult(
                success=False,
                error=f"Destination already exists: {dest_path}"
            )

        # Determine name from URL if not provided
        if not name:
            name = url.rstrip('/').split('/')[-1]
            if name.endswith('.git'):
                name = name[:-4]

        try:
            # Clone repository
            clone_result = self._git.clone(url, dest_path, branch=branch)

            if not clone_result.success:
                return AddProjectResult(
                    success=False,
                    error=clone_result.error or "Clone failed"
                )

            # Create project directly in database
            project = self.repository.create_with_auto_slug(
                name=name,
                path=str(dest_path),
                source_type=ProjectSourceType.GIT,
                git_url=url,
                git_branch=branch or clone_result.branch,
                description=description,
            )

            # Create project data directory
            self.home.ensure_project_structure(project['slug'])

            # Set status to ready
            self.repository.update_status(project['id'], ProjectStatus.READY)

            logger.info(f"Added git project: {name} from {url}")

            return AddProjectResult(success=True, project=project)

        except Exception as e:
            # Clean up on failure
            if dest_path.exists():
                import shutil
                shutil.rmtree(dest_path, ignore_errors=True)

            logger.error(f"Failed to add git project: {e}")
            return AddProjectResult(success=False, error=str(e))

    def switch(self, slug_or_id: str) -> Optional[Dict[str, Any]]:
        """
        Switch to a project.

        Args:
            slug_or_id: Project slug or ID.

        Returns:
            The activated project dict or None if not found.
        """
        project = self.repository.get_by_slug_or_id(slug_or_id)

        if not project:
            return None

        if project.status == ProjectStatus.ARCHIVED:
            logger.warning(f"Cannot switch to archived project: {project.name}")
            return None

        self.repository.set_active(project.project_id)
        logger.info(f"Switched to project: {project.name}")

        return self.repository.get_active(as_dict=True)

    def get_active(self) -> Optional[Dict[str, Any]]:
        """Get the currently active project."""
        return self.repository.get_active(as_dict=True)

    def list_projects(self, include_archived: bool = False) -> List[Dict[str, Any]]:
        """List all projects."""
        return self.repository.list_all(include_archived=include_archived, as_dict=True)

    def get_info(self, slug_or_id: str = None) -> Optional[ProjectInfo]:
        """
        Get detailed project information.

        Args:
            slug_or_id: Project slug or ID (default: active project).

        Returns:
            ProjectInfo with database and git status.
        """
        if slug_or_id:
            project_orm = self.repository.get_by_slug_or_id(slug_or_id)
            project = self.repository.to_registry_dict(project_orm) if project_orm else None
        else:
            project = self.repository.get_active(as_dict=True)

        if not project:
            return None

        # Get git status
        git_status = None
        project_path = Path(project['path'])
        if self._git.is_git_repository(project_path):
            git_status = self._git.status(project_path)

        # Check knowledge
        knowledge_exists = False
        try:
            from core.knowledge_store import KnowledgeStore
            store = KnowledgeStore(project_path, project_id=project['id'])
            knowledge_exists = store.exists()
        except Exception:
            pass

        # Count experts
        expert_count = 0
        try:
            from core.expert_loader import ExpertLoader
            loader = ExpertLoader(project_path, project_slug=project['slug'])
            experts = loader.discover_experts()
            expert_count = len(experts)
        except Exception:
            pass

        return ProjectInfo(
            entry=project,
            git_status=git_status,
            knowledge_exists=knowledge_exists,
            expert_count=expert_count,
        )

    def archive(self, slug_or_id: str) -> Optional[Dict[str, Any]]:
        """Archive a project."""
        project = self.repository.get_by_slug_or_id(slug_or_id)
        if not project:
            return None

        self.repository.archive(project.project_id)
        logger.info(f"Archived project: {project.name}")

        updated = self.repository.get_by_id(project.project_id)
        return self.repository.to_registry_dict(updated) if updated else None

    def restore(self, slug_or_id: str) -> Optional[Dict[str, Any]]:
        """Restore an archived project."""
        project = self.repository.get_by_slug_or_id(slug_or_id)
        if not project:
            return None

        self.repository.restore(project.project_id)
        logger.info(f"Restored project: {project.name}")

        updated = self.repository.get_by_id(project.project_id)
        return self.repository.to_registry_dict(updated) if updated else None

    def remove(
        self,
        slug_or_id: str,
        delete_files: bool = False
    ) -> bool:
        """
        Remove a project.

        Args:
            slug_or_id: Project slug or ID.
            delete_files: Also delete the project files.

        Returns:
            True if removed, False if not found.
        """
        project = self.repository.get_by_slug_or_id(slug_or_id)
        if not project:
            return False

        project_slug = project.slug
        project_id = project.project_id
        project_name = project.name
        project_path = project.path

        # Remove project data directory
        project_data_dir = self.home.project_dir(project_slug)
        if project_data_dir.exists():
            import shutil
            shutil.rmtree(project_data_dir, ignore_errors=True)
            logger.info(f"Removed project data: {project_data_dir}")

        # Optionally delete project files
        if delete_files:
            file_path = Path(project_path)
            if file_path.exists():
                import shutil
                shutil.rmtree(file_path, ignore_errors=True)
                logger.info(f"Removed project files: {file_path}")

        # Remove from database
        self.repository.delete(project_id)
        logger.info(f"Removed project: {project_name}")

        return True

    def fetch(self, slug_or_id: str = None) -> Optional[Dict[str, Any]]:
        """
        Fetch updates for a project.

        Args:
            slug_or_id: Project slug or ID (default: active project).

        Returns:
            Dict with fetch result or None if not a git project.
        """
        if slug_or_id:
            project_orm = self.repository.get_by_slug_or_id(slug_or_id)
            project = self.repository.to_registry_dict(project_orm) if project_orm else None
        else:
            project = self.repository.get_active(as_dict=True)

        if not project:
            return None

        project_path = Path(project['path'])
        if not self._git.is_git_repository(project_path):
            return {"error": "Not a git repository"}

        result = self._git.fetch(project_path, all_remotes=True)
        return {
            "success": result.success,
            "output": result.output,
            "error": result.error,
        }

    def pull(self, slug_or_id: str = None) -> Optional[Dict[str, Any]]:
        """
        Pull updates for a project.

        Args:
            slug_or_id: Project slug or ID (default: active project).

        Returns:
            Dict with pull result or None if not a git project.
        """
        if slug_or_id:
            project_orm = self.repository.get_by_slug_or_id(slug_or_id)
            project = self.repository.to_registry_dict(project_orm) if project_orm else None
        else:
            project = self.repository.get_active(as_dict=True)

        if not project:
            return None

        project_path = Path(project['path'])
        if not self._git.is_git_repository(project_path):
            return {"error": "Not a git repository"}

        result = self._git.pull(project_path)
        return {
            "success": result.success,
            "output": result.output,
            "error": result.error,
            "changed_files": result.changed_files,
        }

    def get_git_status(self, slug_or_id: str = None) -> Optional[GitStatus]:
        """
        Get git status for a project.

        Args:
            slug_or_id: Project slug or ID (default: active project).

        Returns:
            GitStatus or None if not a git project.
        """
        if slug_or_id:
            project_orm = self.repository.get_by_slug_or_id(slug_or_id)
            project = self.repository.to_registry_dict(project_orm) if project_orm else None
        else:
            project = self.repository.get_active(as_dict=True)

        if not project:
            return None

        project_path = Path(project['path'])
        if not self._git.is_git_repository(project_path):
            return GitStatus(error="Not a git repository")

        return self._git.status(project_path)


# Singleton instance
_project_service: Optional[ProjectService] = None


def get_project_service() -> ProjectService:
    """Get the project service singleton."""
    global _project_service
    if _project_service is None:
        _project_service = ProjectService()
    return _project_service
