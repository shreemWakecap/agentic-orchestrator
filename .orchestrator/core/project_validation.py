"""Project validation utilities for workflow execution.

Provides functions to validate project state before starting
workflow execution, catching issues early with clear errors.

This module complements core/exceptions.py by providing:
- Comprehensive project validation for workflows
- ValidatedProject dataclass for type-safe project info
- Per-workflow validation requirements
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import logging

from core.exceptions import ProjectNotFoundError, ProjectPathError, ProjectArchivedError

logger = logging.getLogger(__name__)


# Re-export for convenience
__all__ = [
    "ProjectNotFoundError",
    "ProjectPathError",
    "ProjectArchivedError",
    "ValidatedProject",
    "WORKFLOW_VALIDATION",
    "validate_project_for_workflow",
    "validate_for_workflow_type",
    "validate_project_quick",
]


@dataclass
class ValidatedProject:
    """Result of successful project validation.

    Contains all project details needed for workflow execution.
    """

    project_id: str
    slug: str
    name: str
    path: Path
    status: str

    @property
    def is_git_repo(self) -> bool:
        """Check if project path is a git repository."""
        return (self.path / ".git").exists()

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/serialization."""
        return {
            "project_id": self.project_id,
            "slug": self.slug,
            "name": self.name,
            "path": str(self.path),
            "status": self.status,
            "is_git_repo": self.is_git_repo,
        }


# Validation requirements by workflow type
WORKFLOW_VALIDATION = {
    "planning": {
        "require_git": False,
        "require_writable": True,
    },
    "building": {
        "require_git": False,
        "require_writable": True,
    },
    "scouting": {
        "require_git": False,
        "require_writable": False,  # Scout only reads
    },
    "syncing": {
        "require_git": True,  # Must be git repo
        "require_writable": True,
    },
    "reviewing": {
        "require_git": False,
        "require_writable": False,
    },
}


def validate_project_for_workflow(
    project_id: str,
    require_git: bool = False,
    require_writable: bool = True,
) -> ValidatedProject:
    """Validate project is ready for workflow execution.

    Performs comprehensive validation:
    1. Project exists in database
    2. Project is not archived
    3. Project path exists on filesystem
    4. Project path is a directory
    5. (Optional) Project is a git repository
    6. (Optional) Project path is writable

    Args:
        project_id: Project ID to validate
        require_git: If True, validates path is a git repo
        require_writable: If True, validates path is writable

    Returns:
        ValidatedProject with all project details

    Raises:
        ProjectNotFoundError: Project doesn't exist
        ProjectArchivedError: Project is archived
        ProjectPathError: Path issues (missing, not dir, not writable, etc.)
    """
    from db.repositories.project import get_project_repository
    from db.models import ProjectStatus

    repo = get_project_repository()
    project = repo.get_by_slug_or_id(project_id, as_dict=True)

    # Check existence
    if not project:
        raise ProjectNotFoundError(project_id)

    # Check archived status
    project_status = project.get("status", "")
    if project_status == ProjectStatus.ARCHIVED.value:
        raise ProjectArchivedError(project_id, project.get("name"))

    # Validate path exists
    path_str = project.get("path")
    if not path_str:
        raise ProjectPathError(project_id, reason="Project has no path configured")

    path = Path(path_str)

    if not path.exists():
        raise ProjectPathError(
            project_id,
            path=path_str,
            reason="Path does not exist on filesystem"
        )

    if not path.is_dir():
        raise ProjectPathError(
            project_id,
            path=path_str,
            reason="Path is not a directory"
        )

    # Optional: Git repository check
    if require_git:
        git_dir = path / ".git"
        if not git_dir.exists():
            raise ProjectPathError(
                project_id,
                path=path_str,
                reason="Path is not a git repository"
            )

    # Optional: Writable check
    if require_writable:
        test_file = path / ".orchestrator_write_test"
        try:
            test_file.touch()
            test_file.unlink()
        except (PermissionError, OSError) as e:
            raise ProjectPathError(
                project_id,
                path=path_str,
                reason=f"Path is not writable: {e}"
            )

    logger.debug(f"Project validated: {project.get('name')} ({project_id})")

    return ValidatedProject(
        project_id=project["id"],
        slug=project.get("slug", ""),
        name=project.get("name", "Unknown"),
        path=path,
        status=project_status,
    )


def validate_for_workflow_type(project_id: str, workflow_type: str) -> ValidatedProject:
    """Validate project for specific workflow type.

    Uses WORKFLOW_VALIDATION config to determine requirements.

    Args:
        project_id: Project ID to validate
        workflow_type: Type of workflow (planning, building, scouting, syncing)

    Returns:
        ValidatedProject with all project details

    Raises:
        ProjectNotFoundError: Project doesn't exist
        ProjectArchivedError: Project is archived
        ProjectPathError: Path issues based on workflow requirements
    """
    config = WORKFLOW_VALIDATION.get(workflow_type, {})
    return validate_project_for_workflow(
        project_id,
        require_git=config.get("require_git", False),
        require_writable=config.get("require_writable", True),
    )


def validate_project_quick(project_id: str) -> bool:
    """Quick validation - just checks existence and non-archived status.

    Use for fast checks where full path validation is not needed.

    Args:
        project_id: Project ID to validate

    Returns:
        True if project exists and is not archived
    """
    from db.repositories.project import get_project_repository
    from db.models import ProjectStatus

    try:
        repo = get_project_repository()
        project = repo.get_by_slug_or_id(project_id, as_dict=True)

        if not project:
            return False

        if project.get("status") == ProjectStatus.ARCHIVED.value:
            return False

        return True
    except Exception as e:
        logger.warning(f"Quick validation failed for {project_id}: {e}")
        return False
