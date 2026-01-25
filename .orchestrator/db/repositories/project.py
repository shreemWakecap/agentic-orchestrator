"""
Project Repository for CRUD operations on Project entities.

This repository is the single source of truth for project data.
The database is authoritative - no file-based registry is needed.
"""
import re
import uuid
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

from sqlalchemy import select, update, delete
from sqlalchemy.orm import Session

from db.models import Project, ProjectEvent, ProjectStatus, ProjectSourceType
from db.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class ProjectRepository(BaseRepository):
    """
    Repository for Project entities.

    Provides CRUD operations and specialized queries for projects.
    This is the single source of truth for project data.
    """

    model = Project
    table_name = "projects"

    @staticmethod
    def generate_slug(name: str, existing_slugs: List[str] = None) -> str:
        """
        Generate a URL-safe slug from a project name.

        Args:
            name: The project name.
            existing_slugs: List of existing slugs to avoid conflicts.

        Returns:
            A unique slug.
        """
        # Convert to lowercase and replace non-alphanumeric with hyphens
        slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')

        # Limit length
        if len(slug) > 50:
            slug = slug[:50].rsplit('-', 1)[0]

        # Ensure uniqueness
        if existing_slugs:
            base_slug = slug
            counter = 1
            while slug in existing_slugs:
                slug = f"{base_slug}-{counter}"
                counter += 1

        return slug

    def get_all_slugs(self) -> List[str]:
        """
        Get all existing project slugs.

        Returns:
            List of all project slugs in the database.
        """
        with self.session() as session:
            stmt = select(Project.slug)
            return [row[0] for row in session.execute(stmt).fetchall()]

    def create_with_auto_slug(
        self,
        name: str,
        path: str,
        source_type: ProjectSourceType = ProjectSourceType.LOCAL,
        description: str = None,
        git_url: str = None,
        git_branch: str = None,
    ) -> Dict[str, Any]:
        """
        Create a project with auto-generated unique slug.

        Args:
            name: Project name.
            path: Path to project directory.
            source_type: Source type (local or git).
            description: Project description.
            git_url: Git repository URL (for git projects).
            git_branch: Git branch name.

        Returns:
            Dictionary with the created project's data.
        """
        existing_slugs = self.get_all_slugs()
        slug = self.generate_slug(name, existing_slugs)
        return self.create(name, slug, path, source_type, description, git_url, git_branch)

    def create(
        self,
        name: str,
        slug: str,
        path: str,
        source_type: ProjectSourceType = ProjectSourceType.LOCAL,
        description: str = None,
        git_url: str = None,
        git_branch: str = None,
    ) -> Dict[str, Any]:
        """
        Create a new project.

        Args:
            name: Project name.
            slug: URL-safe project identifier.
            path: Path to project directory.
            source_type: Source type (local or git).
            description: Project description.
            git_url: Git repository URL (for git projects).
            git_branch: Git branch name.

        Returns:
            Dictionary with the created project's data (avoids detached session issues).
        """
        project_id = str(uuid.uuid4())

        with self.session() as session:
            project = Project(
                project_id=project_id,
                name=name,
                slug=slug,
                path=str(Path(path).resolve()),
                description=description,
                status=ProjectStatus.PENDING,
                source_type=source_type,
                git_url=git_url,
                git_branch=git_branch,
                created_at=datetime.utcnow(),
            )
            session.add(project)
            session.commit()
            session.refresh(project)

            # Log creation event
            self._log_event(session, project_id, "created", {
                "name": name,
                "path": str(path),
                "source_type": source_type.value,
            })

            # Convert to dict BEFORE session closes to avoid detached session issues
            result = self.to_registry_dict(project)

            logger.info(f"Created project: {name} ({project_id})")
            return result

    def get_by_id(self, project_id: str) -> Optional[Project]:
        """
        Get a project by its ID (UUID).

        Args:
            project_id: The project UUID.

        Returns:
            The Project or None if not found.
        """
        with self.session() as session:
            stmt = select(Project).where(Project.project_id == project_id)
            result = session.execute(stmt)
            return result.scalar_one_or_none()

    def get_by_slug(self, slug: str) -> Optional[Project]:
        """
        Get a project by its slug.

        Args:
            slug: The project slug.

        Returns:
            The Project or None if not found.
        """
        with self.session() as session:
            stmt = select(Project).where(Project.slug == slug)
            result = session.execute(stmt)
            return result.scalar_one_or_none()

    def get_project_id_by_slug(self, slug: str) -> Optional[str]:
        """
        Get a project's ID by its slug.

        Args:
            slug: The project slug.

        Returns:
            The project_id string or None if not found.
        """
        with self.session() as session:
            stmt = select(Project.project_id).where(Project.slug == slug)
            result = session.execute(stmt)
            row = result.scalar_one_or_none()
            return row

    def get_by_path(self, path: str, as_dict: bool = False):
        """
        Get a project by its path.

        Args:
            path: The project path.
            as_dict: If True, return as dictionary instead of ORM object.

        Returns:
            The Project (or dict if as_dict=True) or None if not found.
        """
        resolved_path = str(Path(path).resolve())
        with self.session() as session:
            stmt = select(Project).where(Project.path == resolved_path)
            result = session.execute(stmt)
            project = result.scalar_one_or_none()
            if project and as_dict:
                return self.to_registry_dict(project)
            return project

    def get_by_slug_or_id(self, slug_or_id: str, as_dict: bool = False):
        """
        Get a project by slug or ID.

        Args:
            slug_or_id: The project slug or UUID.
            as_dict: If True, return as dictionary instead of ORM object.

        Returns:
            The Project (or dict if as_dict=True) or None if not found.
        """
        with self.session() as session:
            # Try slug first (more common)
            stmt = select(Project).where(Project.slug == slug_or_id)
            result = session.execute(stmt)
            project = result.scalar_one_or_none()

            if not project:
                # Try ID
                stmt = select(Project).where(Project.project_id == slug_or_id)
                result = session.execute(stmt)
                project = result.scalar_one_or_none()

            if project and as_dict:
                return self.to_registry_dict(project)
            return project

    def list_all(self, include_archived: bool = False, as_dict: bool = False) -> List[Project]:
        """
        List all projects.

        Args:
            include_archived: Include archived projects.
            as_dict: Return dictionaries instead of ORM objects (avoids detached session issues).

        Returns:
            List of Project entities or dictionaries.
        """
        with self.session() as session:
            stmt = select(Project)
            if not include_archived:
                stmt = stmt.where(Project.status != ProjectStatus.ARCHIVED)
            stmt = stmt.order_by(Project.last_accessed_at.desc().nulls_last(), Project.created_at.desc())
            result = session.execute(stmt)
            projects = list(result.scalars().all())

            if as_dict:
                return [self.to_registry_dict(p) for p in projects]
            return projects

    def get_active(self, as_dict: bool = False) -> Optional[Project]:
        """
        Get the currently active project.

        Args:
            as_dict: Return dictionary instead of ORM object (avoids detached session issues).

        Returns:
            The active Project or None.
        """
        with self.session() as session:
            stmt = select(Project).where(Project.status == ProjectStatus.ACTIVE)
            result = session.execute(stmt)
            project = result.scalar_one_or_none()

            if project and as_dict:
                return self.to_registry_dict(project)
            return project

    def set_active(self, project_id: str) -> bool:
        """
        Set a project as active.

        This deactivates any currently active project.

        Args:
            project_id: The project ID to activate.

        Returns:
            True if successful, False if project not found.
        """
        with self.session() as session:
            # Deactivate current active project
            session.execute(
                update(Project)
                .where(Project.status == ProjectStatus.ACTIVE)
                .values(status=ProjectStatus.READY)
            )

            # Activate the specified project
            stmt = select(Project).where(Project.project_id == project_id)
            result = session.execute(stmt)
            project = result.scalar_one_or_none()

            if not project:
                return False

            project_name = project.name  # Capture before commit
            project.status = ProjectStatus.ACTIVE
            project.last_accessed_at = datetime.utcnow()
            session.commit()

            # Log activation event in separate transaction
            self._log_event(session, project_id, "activated")
            session.commit()

            logger.info(f"Activated project: {project_name}")
            return True

    def update_status(self, project_id: str, status: ProjectStatus) -> Optional[Project]:
        """
        Update a project's status.

        Args:
            project_id: The project ID.
            status: The new status.

        Returns:
            The updated Project or None if not found.
        """
        with self.session() as session:
            stmt = select(Project).where(Project.project_id == project_id)
            result = session.execute(stmt)
            project = result.scalar_one_or_none()

            if not project:
                return None

            old_status = project.status
            project.status = status
            project.updated_at = datetime.utcnow()

            if status == ProjectStatus.ARCHIVED:
                project.archived_at = datetime.utcnow()
            elif status == ProjectStatus.READY and old_status == ProjectStatus.INDEXING:
                project.indexed_at = datetime.utcnow()

            session.commit()

            # Log status change event
            self._log_event(session, project_id, "status_changed", {
                "old_status": old_status.value if old_status else None,
                "new_status": status.value,
            })

            return project

    def archive(self, project_id: str) -> Optional[Project]:
        """
        Archive a project.

        Args:
            project_id: The project ID.

        Returns:
            The archived Project or None if not found.
        """
        return self.update_status(project_id, ProjectStatus.ARCHIVED)

    def restore(self, project_id: str) -> Optional[Project]:
        """
        Restore an archived project.

        Args:
            project_id: The project ID.

        Returns:
            The restored Project or None if not found.
        """
        return self.update_status(project_id, ProjectStatus.READY)

    def delete(self, project_id: str) -> bool:
        """
        Delete a project.

        Args:
            project_id: The project ID.

        Returns:
            True if deleted, False if not found.
        """
        with self.session() as session:
            stmt = delete(Project).where(Project.project_id == project_id)
            result = session.execute(stmt)
            session.commit()

            if result.rowcount > 0:
                logger.info(f"Deleted project: {project_id}")
                return True
            return False

    def update(self, project_id: str, **updates) -> Optional[Project]:
        """
        Update project fields.

        Args:
            project_id: The project ID.
            **updates: Fields to update.

        Returns:
            The updated Project or None if not found.
        """
        with self.session() as session:
            stmt = select(Project).where(Project.project_id == project_id)
            result = session.execute(stmt)
            project = result.scalar_one_or_none()

            if not project:
                return None

            for key, value in updates.items():
                if hasattr(project, key):
                    setattr(project, key, value)

            project.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(project)

            return project

    def touch(self, project_id: str) -> None:
        """
        Update the last_accessed_at timestamp.

        Args:
            project_id: The project ID.
        """
        with self.session() as session:
            session.execute(
                update(Project)
                .where(Project.project_id == project_id)
                .values(last_accessed_at=datetime.utcnow())
            )
            session.commit()

    def _log_event(
        self,
        session: Session,
        project_id: str,
        event_type: str,
        event_data: Dict[str, Any] = None,
        triggered_by: str = "system"
    ) -> None:
        """
        Log a project event.

        Args:
            session: The database session.
            project_id: The project ID.
            event_type: The event type.
            event_data: Additional event data.
            triggered_by: Who triggered the event.
        """
        import json
        event = ProjectEvent(
            project_id=project_id,
            event_type=event_type,
            event_data_json=json.dumps(event_data or {}),
            triggered_by=triggered_by,
        )
        session.add(event)

    def get_events(self, project_id: str, limit: int = 50) -> List[ProjectEvent]:
        """
        Get recent events for a project.

        Args:
            project_id: The project ID.
            limit: Maximum number of events to return.

        Returns:
            List of ProjectEvent entities.
        """
        with self.session() as session:
            stmt = (
                select(ProjectEvent)
                .where(ProjectEvent.project_id == project_id)
                .order_by(ProjectEvent.timestamp.desc())
                .limit(limit)
            )
            result = session.execute(stmt)
            return list(result.scalars().all())

    def to_registry_dict(self, project: Project) -> Dict[str, Any]:
        """
        Convert a project to registry dictionary format.

        Args:
            project: The Project entity.

        Returns:
            Dictionary in registry format.
        """
        return {
            "id": project.project_id,
            "name": project.name,
            "slug": project.slug,
            "path": project.path,
            "status": project.status.value if project.status else "unknown",
            "source_type": project.source_type.value if project.source_type else "local",
            "git_url": project.git_url,
            "git_branch": project.git_branch,
            "added_at": project.created_at.isoformat() if project.created_at else None,
            "last_accessed": project.last_accessed_at.isoformat() if project.last_accessed_at else None,
            "indexed_at": project.indexed_at.isoformat() if project.indexed_at else None,
            "description": project.description,
        }


# Singleton instance
_project_repository: Optional[ProjectRepository] = None


def get_project_repository() -> ProjectRepository:
    """Get the project repository singleton."""
    global _project_repository
    if _project_repository is None:
        _project_repository = ProjectRepository()
    return _project_repository
