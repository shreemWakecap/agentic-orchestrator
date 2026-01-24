"""
Project Registry - Quick lookup cache for projects.

The registry provides fast project lookups without hitting the database.
It's synchronized with the database but serves as a local cache.

DATABASE IS THE SOURCE OF TRUTH. The registry.json file is just a cache
that is synced from the database on load.

Registry structure (registry.json):
{
    "version": "1.0",
    "created_at": "2024-01-01T00:00:00Z",
    "active_project": "project-slug",
    "projects": {
        "project-slug": {
            "id": "uuid",
            "name": "Project Name",
            "slug": "project-slug",
            "path": "/path/to/project",
            "status": "ready",
            "source_type": "local|git",
            "git_url": null,
            "added_at": "2024-01-01T00:00:00Z",
            "last_accessed": "2024-01-01T00:00:00Z"
        }
    }
}
"""
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
import re
import uuid
import threading

logger = logging.getLogger(__name__)


class ProjectStatus(str, Enum):
    """Project lifecycle status."""
    PENDING = "pending"      # Validating/cloning
    INDEXING = "indexing"    # Running scout
    READY = "ready"          # Available for use
    ACTIVE = "active"        # Currently selected
    ARCHIVED = "archived"    # Archived but not deleted


class ProjectSourceType(str, Enum):
    """Project source type."""
    LOCAL = "local"          # Local directory
    GIT = "git"              # Git repository (cloned)


@dataclass
class ProjectEntry:
    """A project entry in the registry."""
    id: str
    name: str
    slug: str
    path: str
    status: ProjectStatus
    source_type: ProjectSourceType
    git_url: Optional[str] = None
    git_branch: Optional[str] = None
    added_at: Optional[str] = None
    last_accessed: Optional[str] = None
    indexed_at: Optional[str] = None
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "path": self.path,
            "status": self.status.value if isinstance(self.status, ProjectStatus) else self.status,
            "source_type": self.source_type.value if isinstance(self.source_type, ProjectSourceType) else self.source_type,
            "git_url": self.git_url,
            "git_branch": self.git_branch,
            "added_at": self.added_at,
            "last_accessed": self.last_accessed,
            "indexed_at": self.indexed_at,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectEntry":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            slug=data["slug"],
            path=data["path"],
            status=ProjectStatus(data["status"]),
            source_type=ProjectSourceType(data["source_type"]),
            git_url=data.get("git_url"),
            git_branch=data.get("git_branch"),
            added_at=data.get("added_at"),
            last_accessed=data.get("last_accessed"),
            indexed_at=data.get("indexed_at"),
            description=data.get("description"),
        )


class ProjectRegistry:
    """
    Manages the project registry cache.

    Thread-safe with file locking for concurrent access.
    The database is the source of truth - registry.json is just a cache.
    """

    def __init__(self, registry_file: Path):
        """
        Initialize the registry.

        Args:
            registry_file: Path to the registry.json file.
        """
        self.registry_file = registry_file
        self._lock = threading.RLock()
        self._db_synced = False

    def _sync_from_db(self) -> None:
        """
        Sync registry cache from database (source of truth).

        Called automatically on first load. If database is unavailable,
        falls back to local cache.
        """
        if self._db_synced:
            return

        try:
            from db.repositories.project import get_project_repository
            repo = get_project_repository()

            # Get all projects from database as dicts (avoids detached session issues)
            db_projects = repo.list_all(include_archived=True, as_dict=True)

            if not db_projects:
                self._db_synced = True
                return

            # Get active project as dict
            active_project = repo.get_active(as_dict=True)

            # Build registry data from database (already dicts)
            projects_dict = {}
            for project_dict in db_projects:
                projects_dict[project_dict["slug"]] = project_dict

            # Update local cache
            data = self._load_from_file()
            data["projects"] = projects_dict
            data["active_project"] = active_project["slug"] if active_project else None
            self._save(data)

            self._db_synced = True
            logger.debug(f"Synced {len(db_projects)} projects from database")

        except Exception as e:
            # Database unavailable - use local cache
            logger.debug(f"Database sync failed, using local cache: {e}")
            self._db_synced = True

    def _load_from_file(self) -> Dict[str, Any]:
        """Load registry from file only (no DB sync)."""
        if not self.registry_file.exists():
            return self._create_empty_registry()

        try:
            with open(self.registry_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid registry file: {e}")
            return self._create_empty_registry()

    def _load(self) -> Dict[str, Any]:
        """Load registry from file, syncing from DB first."""
        self._sync_from_db()
        return self._load_from_file()

    def _save(self, data: Dict[str, Any]) -> None:
        """Save registry to file."""
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.registry_file, 'w') as f:
            json.dump(data, f, indent=2)

    def _create_empty_registry(self) -> Dict[str, Any]:
        """Create empty registry structure."""
        return {
            "version": "1.0",
            "created_at": datetime.utcnow().isoformat(),
            "active_project": None,
            "projects": {}
        }

    @staticmethod
    def generate_slug(name: str, existing_slugs: List[str] = None) -> str:
        """
        Generate a URL-safe slug from a name.

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

    def list_projects(self, include_archived: bool = False) -> List[ProjectEntry]:
        """
        List all projects.

        Args:
            include_archived: Include archived projects.

        Returns:
            List of project entries.
        """
        with self._lock:
            data = self._load()
            projects = []

            for entry_data in data.get("projects", {}).values():
                entry = ProjectEntry.from_dict(entry_data)
                if include_archived or entry.status != ProjectStatus.ARCHIVED:
                    projects.append(entry)

            # Sort by last accessed, then added
            return sorted(
                projects,
                key=lambda p: p.last_accessed or p.added_at or "",
                reverse=True
            )

    def get_project(self, slug_or_id: str) -> Optional[ProjectEntry]:
        """
        Get a project by slug or ID.

        Args:
            slug_or_id: Project slug or ID.

        Returns:
            Project entry or None.
        """
        with self._lock:
            data = self._load()
            projects = data.get("projects", {})

            # Try slug first
            if slug_or_id in projects:
                return ProjectEntry.from_dict(projects[slug_or_id])

            # Try ID
            for entry_data in projects.values():
                if entry_data.get("id") == slug_or_id:
                    return ProjectEntry.from_dict(entry_data)

            return None

    def get_active_project(self) -> Optional[ProjectEntry]:
        """
        Get the currently active project.

        Returns:
            Active project entry or None.
        """
        with self._lock:
            data = self._load()
            active_slug = data.get("active_project")

            if not active_slug:
                return None

            return self.get_project(active_slug)

    def add_project(
        self,
        name: str,
        path: str,
        source_type: ProjectSourceType,
        git_url: Optional[str] = None,
        git_branch: Optional[str] = None,
        description: Optional[str] = None,
    ) -> ProjectEntry:
        """
        Add a new project to the registry and database.

        Args:
            name: Project name.
            path: Path to project directory.
            source_type: Source type (local or git).
            git_url: Git repository URL (for git projects).
            git_branch: Git branch name.
            description: Project description.

        Returns:
            The created project entry.

        Raises:
            ValueError: If the path is already registered.
        """
        with self._lock:
            # Check for duplicate path
            existing = self.get_project_by_path(path)
            if existing:
                raise ValueError(f"Path already registered as '{existing.name}' ({existing.slug})")

            data = self._load()
            existing_slugs = list(data.get("projects", {}).keys())
            slug = self.generate_slug(name, existing_slugs)
            project_id = str(uuid.uuid4())
            resolved_path = str(Path(path).resolve())

            # Create the entry object first (we'll need it either way)
            entry = ProjectEntry(
                id=project_id,
                name=name,
                slug=slug,
                path=resolved_path,
                status=ProjectStatus.PENDING,
                source_type=source_type,
                git_url=git_url,
                git_branch=git_branch,
                added_at=datetime.utcnow().isoformat(),
                last_accessed=None,
                description=description,
            )

            # Write to database first (source of truth)
            try:
                from db.repositories.project import get_project_repository
                from db.models import ProjectSourceType as DBSourceType

                repo = get_project_repository()
                db_source_type = DBSourceType(source_type.value)

                db_project = repo.create(
                    name=name,
                    slug=slug,
                    path=resolved_path,
                    source_type=db_source_type,
                    description=description,
                    git_url=git_url,
                    git_branch=git_branch,
                )

                # Update entry with DB-generated ID
                if db_project:
                    entry = ProjectEntry(
                        id=db_project.project_id,
                        name=db_project.name,
                        slug=db_project.slug,
                        path=db_project.path,
                        status=ProjectStatus(db_project.status.value) if db_project.status else ProjectStatus.PENDING,
                        source_type=source_type,
                        git_url=db_project.git_url,
                        git_branch=db_project.git_branch,
                        added_at=db_project.created_at.isoformat() if db_project.created_at else datetime.utcnow().isoformat(),
                        last_accessed=db_project.last_accessed_at.isoformat() if db_project.last_accessed_at else None,
                        description=db_project.description,
                    )

                logger.info(f"Added project to database: {entry.name} ({entry.slug})")

            except Exception as e:
                logger.warning(f"Database write failed, using local cache only: {e}")

            # Always save to local cache
            data["projects"][entry.slug] = entry.to_dict()
            self._save(data)

            logger.info(f"Added project: {entry.name} ({entry.slug})")
            return entry

    def update_project(self, slug: str, **updates) -> Optional[ProjectEntry]:
        """
        Update a project's fields.

        Args:
            slug: Project slug.
            **updates: Fields to update.

        Returns:
            Updated project entry or None.
        """
        with self._lock:
            data = self._load()

            if slug not in data.get("projects", {}):
                return None

            entry_data = data["projects"][slug]

            # Update fields
            for key, value in updates.items():
                if key in entry_data:
                    if isinstance(value, Enum):
                        entry_data[key] = value.value
                    else:
                        entry_data[key] = value

            self._save(data)
            return ProjectEntry.from_dict(entry_data)

    def set_active(self, slug: str) -> Optional[ProjectEntry]:
        """
        Set a project as active in registry and database.

        Args:
            slug: Project slug to activate.

        Returns:
            The activated project entry or None.
        """
        with self._lock:
            data = self._load()

            if slug not in data.get("projects", {}):
                return None

            # Write to database first (source of truth)
            try:
                from db.repositories.project import get_project_repository
                repo = get_project_repository()

                # Lookup project_id by slug (avoids detached session issues)
                project_id = repo.get_project_id_by_slug(slug)
                if project_id:
                    repo.set_active(project_id)

                # Re-sync from database
                self._db_synced = False
                self._sync_from_db()

                return self.get_project(slug)

            except Exception as e:
                logger.warning(f"Database write failed, using local cache: {e}")
                # Fallback to local-only operation
                # Deactivate current active project
                old_active = data.get("active_project")
                if old_active and old_active in data["projects"]:
                    if data["projects"][old_active]["status"] == ProjectStatus.ACTIVE.value:
                        data["projects"][old_active]["status"] = ProjectStatus.READY.value

                # Activate new project
                data["projects"][slug]["status"] = ProjectStatus.ACTIVE.value
                data["projects"][slug]["last_accessed"] = datetime.utcnow().isoformat()
                data["active_project"] = slug

                self._save(data)
                logger.info(f"Activated project: {slug}")

                return ProjectEntry.from_dict(data["projects"][slug])

    def set_status(self, slug: str, status: ProjectStatus) -> Optional[ProjectEntry]:
        """
        Set a project's status.

        Args:
            slug: Project slug.
            status: New status.

        Returns:
            Updated project entry or None.
        """
        return self.update_project(slug, status=status)

    def archive_project(self, slug: str) -> Optional[ProjectEntry]:
        """
        Archive a project in registry and database.

        Args:
            slug: Project slug.

        Returns:
            Archived project entry or None.
        """
        with self._lock:
            data = self._load()

            if slug not in data.get("projects", {}):
                return None

            project_id = data["projects"][slug].get("id")

            # Write to database first (source of truth)
            try:
                from db.repositories.project import get_project_repository
                repo = get_project_repository()

                if project_id:
                    repo.archive(project_id)

                # Re-sync from database
                self._db_synced = False
                self._sync_from_db()

                logger.info(f"Archived project: {slug}")
                return self.get_project(slug)

            except Exception as e:
                logger.warning(f"Database write failed, using local cache: {e}")
                # Fallback to local-only operation
                # If it's the active project, clear active
                if data.get("active_project") == slug:
                    data["active_project"] = None

                data["projects"][slug]["status"] = ProjectStatus.ARCHIVED.value
                self._save(data)

                logger.info(f"Archived project: {slug}")
                return ProjectEntry.from_dict(data["projects"][slug])

    def restore_project(self, slug: str) -> Optional[ProjectEntry]:
        """
        Restore an archived project in registry and database.

        Args:
            slug: Project slug.

        Returns:
            Restored project entry or None.
        """
        with self._lock:
            data = self._load()

            if slug not in data.get("projects", {}):
                return None

            project_id = data["projects"][slug].get("id")

            # Write to database first (source of truth)
            try:
                from db.repositories.project import get_project_repository
                repo = get_project_repository()

                if project_id:
                    repo.restore(project_id)

                # Re-sync from database
                self._db_synced = False
                self._sync_from_db()

                logger.info(f"Restored project: {slug}")
                return self.get_project(slug)

            except Exception as e:
                logger.warning(f"Database write failed, using local cache: {e}")
                # Fallback to local-only operation
                return self.set_status(slug, ProjectStatus.READY)

    def remove_project(self, slug: str) -> bool:
        """
        Remove a project from registry and database.

        Note: This soft-deletes by archiving in DB, but removes from registry.

        Args:
            slug: Project slug.

        Returns:
            True if removed, False if not found.
        """
        with self._lock:
            data = self._load()

            if slug not in data.get("projects", {}):
                return False

            project_id = data["projects"][slug].get("id")

            # Archive in database (soft delete) then remove from cache
            try:
                from db.repositories.project import get_project_repository
                repo = get_project_repository()

                if project_id:
                    # Soft delete: archive in database
                    repo.archive(project_id)

            except Exception as e:
                logger.warning(f"Database archive failed: {e}")

            # Remove from local cache regardless
            if data.get("active_project") == slug:
                data["active_project"] = None

            del data["projects"][slug]
            self._save(data)

            logger.info(f"Removed project: {slug}")
            return True

    def get_project_by_path(self, path: str) -> Optional[ProjectEntry]:
        """
        Find a project by its path.

        Args:
            path: Project path to search for.

        Returns:
            Project entry or None.
        """
        resolved_path = str(Path(path).resolve())

        with self._lock:
            data = self._load()

            for entry_data in data.get("projects", {}).values():
                if entry_data.get("path") == resolved_path:
                    return ProjectEntry.from_dict(entry_data)

            return None

    def sync_from_database(self, db_projects: List[Dict[str, Any]]) -> None:
        """
        Synchronize registry from database records.

        Args:
            db_projects: List of project records from database.
        """
        with self._lock:
            data = self._load()

            # Build a map of DB projects by ID
            db_map = {p["id"]: p for p in db_projects}

            # Update existing entries and add new ones
            for project in db_projects:
                slug = project.get("slug")
                if slug:
                    data["projects"][slug] = project

            # Remove entries not in database
            current_slugs = list(data["projects"].keys())
            db_slugs = {p.get("slug") for p in db_projects}

            for slug in current_slugs:
                if slug not in db_slugs:
                    del data["projects"][slug]

            # Clear active if no longer valid
            if data.get("active_project") not in data["projects"]:
                data["active_project"] = None

            self._save(data)
            logger.info(f"Synced registry with {len(db_projects)} projects from database")


def get_project_registry() -> ProjectRegistry:
    """
    Get the project registry instance.

    Returns:
        ProjectRegistry: The registry instance.

    Raises:
        OrchestratorHomeError: If orchestrator home is not configured.
    """
    from core.home import require_initialized_home

    home = require_initialized_home()
    return ProjectRegistry(home.registry_file)
