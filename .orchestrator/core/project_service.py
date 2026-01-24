"""
Project Service: High-level project management operations.

This service combines project registry, database, and git operations
to provide a unified interface for project management.
"""
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from core.git_manager import GitManager, get_git_manager, GitStatus
from core.project_registry import (
    ProjectRegistry,
    ProjectEntry,
    ProjectStatus,
    ProjectSourceType,
    get_project_registry,
)
from core.home import get_orchestrator_home, OrchestratorHome

logger = logging.getLogger(__name__)


@dataclass
class ProjectInfo:
    """Combined project information from registry and git."""
    entry: ProjectEntry
    git_status: Optional[GitStatus] = None
    knowledge_exists: bool = False
    expert_count: int = 0


@dataclass
class AddProjectResult:
    """Result of adding a project."""
    success: bool
    project: Optional[ProjectEntry] = None
    error: Optional[str] = None


class ProjectService:
    """
    High-level project management service.

    Combines registry, database, and git operations for unified
    project management.

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
        registry: ProjectRegistry = None,
        git_manager: GitManager = None,
        home: OrchestratorHome = None
    ):
        """
        Initialize ProjectService.

        Args:
            registry: Project registry (default: get from orchestrator home).
            git_manager: Git manager (default: singleton).
            home: Orchestrator home (default: from env).
        """
        self._registry = registry
        self._git = git_manager or get_git_manager()
        self._home = home

    @property
    def registry(self) -> ProjectRegistry:
        """Get the project registry (lazy load)."""
        if self._registry is None:
            self._registry = get_project_registry()
        return self._registry

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
            AddProjectResult with status and project entry.
        """
        path = Path(path).resolve()

        # Validate path
        if not path.exists():
            return AddProjectResult(success=False, error=f"Path does not exist: {path}")

        if not path.is_dir():
            return AddProjectResult(success=False, error=f"Path is not a directory: {path}")

        # Check if already registered
        existing = self.registry.get_project_by_path(str(path))
        if existing:
            return AddProjectResult(
                success=False,
                error=f"Project already registered as '{existing.name}' ({existing.slug})"
            )

        # Determine name
        if not name:
            name = path.name

        try:
            # Create project in registry
            entry = self.registry.add_project(
                name=name,
                path=str(path),
                source_type=ProjectSourceType.LOCAL,
                description=description,
            )

            # Create project data directory
            self.home.ensure_project_structure(entry.slug)

            # Set status to ready
            self.registry.set_status(entry.slug, ProjectStatus.READY)

            # Sync to database
            self._sync_to_database(entry)

            logger.info(f"Added local project: {name} at {path}")

            return AddProjectResult(success=True, project=entry)

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
            AddProjectResult with status and project entry.
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

            # Create project in registry
            entry = self.registry.add_project(
                name=name,
                path=str(dest_path),
                source_type=ProjectSourceType.GIT,
                git_url=url,
                git_branch=branch or clone_result.branch,
                description=description,
            )

            # Create project data directory
            self.home.ensure_project_structure(entry.slug)

            # Set status to ready
            self.registry.set_status(entry.slug, ProjectStatus.READY)

            # Sync to database
            self._sync_to_database(entry)

            logger.info(f"Added git project: {name} from {url}")

            return AddProjectResult(success=True, project=entry)

        except Exception as e:
            # Clean up on failure
            if dest_path.exists():
                import shutil
                shutil.rmtree(dest_path, ignore_errors=True)

            logger.error(f"Failed to add git project: {e}")
            return AddProjectResult(success=False, error=str(e))

    def switch(self, slug_or_id: str) -> Optional[ProjectEntry]:
        """
        Switch to a project.

        Args:
            slug_or_id: Project slug or ID.

        Returns:
            The activated project entry or None if not found.
        """
        project = self.registry.get_project(slug_or_id)

        if not project:
            return None

        if project.status == ProjectStatus.ARCHIVED:
            logger.warning(f"Cannot switch to archived project: {project.name}")
            return None

        self.registry.set_active(project.slug)
        logger.info(f"Switched to project: {project.name}")

        return self.registry.get_project(project.slug)

    def get_active(self) -> Optional[ProjectEntry]:
        """Get the currently active project."""
        return self.registry.get_active_project()

    def list_projects(self, include_archived: bool = False) -> List[ProjectEntry]:
        """List all projects."""
        return self.registry.list_projects(include_archived=include_archived)

    def get_info(self, slug_or_id: str = None) -> Optional[ProjectInfo]:
        """
        Get detailed project information.

        Args:
            slug_or_id: Project slug or ID (default: active project).

        Returns:
            ProjectInfo with registry and git status.
        """
        if slug_or_id:
            project = self.registry.get_project(slug_or_id)
        else:
            project = self.registry.get_active_project()

        if not project:
            return None

        # Get git status
        git_status = None
        project_path = Path(project.path)
        if self._git.is_git_repository(project_path):
            git_status = self._git.status(project_path)

        # Check knowledge
        knowledge_exists = False
        try:
            from core.knowledge_store import KnowledgeStore
            store = KnowledgeStore(project_path, project_id=project.id)
            knowledge_exists = store.exists()
        except Exception:
            pass

        # Count experts
        expert_count = 0
        try:
            from core.expert_loader import ExpertLoader
            loader = ExpertLoader(project_path, project_slug=project.slug)
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

    def archive(self, slug_or_id: str) -> Optional[ProjectEntry]:
        """Archive a project."""
        project = self.registry.get_project(slug_or_id)
        if not project:
            return None

        self.registry.archive_project(project.slug)
        logger.info(f"Archived project: {project.name}")

        return self.registry.get_project(project.slug)

    def restore(self, slug_or_id: str) -> Optional[ProjectEntry]:
        """Restore an archived project."""
        project = self.registry.get_project(slug_or_id)
        if not project:
            return None

        self.registry.restore_project(project.slug)
        logger.info(f"Restored project: {project.name}")

        return self.registry.get_project(project.slug)

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
        project = self.registry.get_project(slug_or_id)
        if not project:
            return False

        # Remove project data directory
        project_data_dir = self.home.project_dir(project.slug)
        if project_data_dir.exists():
            import shutil
            shutil.rmtree(project_data_dir, ignore_errors=True)
            logger.info(f"Removed project data: {project_data_dir}")

        # Optionally delete project files
        if delete_files:
            project_path = Path(project.path)
            if project_path.exists():
                import shutil
                shutil.rmtree(project_path, ignore_errors=True)
                logger.info(f"Removed project files: {project_path}")

        # Remove from database
        self._remove_from_database(project.id)

        # Remove from registry
        self.registry.remove_project(project.slug)
        logger.info(f"Removed project: {project.name}")

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
            project = self.registry.get_project(slug_or_id)
        else:
            project = self.registry.get_active_project()

        if not project:
            return None

        project_path = Path(project.path)
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
            project = self.registry.get_project(slug_or_id)
        else:
            project = self.registry.get_active_project()

        if not project:
            return None

        project_path = Path(project.path)
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
            project = self.registry.get_project(slug_or_id)
        else:
            project = self.registry.get_active_project()

        if not project:
            return None

        project_path = Path(project.path)
        if not self._git.is_git_repository(project_path):
            return GitStatus(error="Not a git repository")

        return self._git.status(project_path)

    def _sync_to_database(self, entry: ProjectEntry) -> None:
        """Sync project entry to database."""
        try:
            from db.repositories.project import get_project_repository

            repo = get_project_repository()

            # Check if exists
            existing = repo.get_by_id(entry.id)
            if existing:
                repo.update(entry.id, **entry.to_dict())
            else:
                repo.create(
                    name=entry.name,
                    slug=entry.slug,
                    path=entry.path,
                    source_type=entry.source_type,
                    description=entry.description,
                    git_url=entry.git_url,
                    git_branch=entry.git_branch,
                )
        except Exception as e:
            logger.warning(f"Failed to sync project to database: {e}")

    def _remove_from_database(self, project_id: str) -> None:
        """Remove project from database."""
        try:
            from db.repositories.project import get_project_repository

            repo = get_project_repository()
            repo.delete(project_id)
        except Exception as e:
            logger.warning(f"Failed to remove project from database: {e}")


# Singleton instance
_project_service: Optional[ProjectService] = None


def get_project_service() -> ProjectService:
    """Get the project service singleton."""
    global _project_service
    if _project_service is None:
        _project_service = ProjectService()
    return _project_service
