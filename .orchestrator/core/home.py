"""
Orchestrator Home Directory Management.

This module manages the orchestrator home directory structure,
which is the central location for all orchestrator data and projects.

The home directory defaults to .orchestrator/ but can be overridden
by setting SDLC_ORCHESTRATOR_HOME environment variable.

The home directory structure:
    {home}/
    ├── .env            (database credentials)
    ├── config/         (global configuration)
    ├── projects/       (per-project data)
    │   ├── registry.json
    │   └── {project-slug}/
    │       ├── knowledge/
    │       ├── experts/
    │       └── config/
    └── logs/           (global logs)
"""
import os
import json
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

# Environment variable name
ORCHESTRATOR_HOME_ENV = "SDLC_ORCHESTRATOR_HOME"


class OrchestratorHomeError(Exception):
    """Raised when orchestrator home is not configured or invalid."""
    pass


@dataclass(frozen=True)
class OrchestratorHome:
    """
    Represents the orchestrator home directory structure.

    All paths are resolved lazily and validated on access.
    """
    root: Path

    @property
    def config_dir(self) -> Path:
        """Global configuration directory."""
        return self.root / "config"

    @property
    def projects_dir(self) -> Path:
        """Projects data directory."""
        return self.root / "projects"

    @property
    def logs_dir(self) -> Path:
        """Global logs directory."""
        return self.root / "logs"

    @property
    def registry_file(self) -> Path:
        """Project registry file."""
        return self.projects_dir / "registry.json"

    @property
    def global_config_file(self) -> Path:
        """Global configuration file."""
        return self.config_dir / "config.json"

    def project_dir(self, project_slug: str) -> Path:
        """Get the data directory for a specific project."""
        return self.projects_dir / project_slug

    def project_knowledge_dir(self, project_slug: str) -> Path:
        """Get the knowledge directory for a specific project."""
        return self.project_dir(project_slug) / "knowledge"

    def project_experts_dir(self, project_slug: str) -> Path:
        """Get the experts directory for a specific project."""
        return self.project_dir(project_slug) / "experts"

    def project_config_dir(self, project_slug: str) -> Path:
        """Get the config directory for a specific project."""
        return self.project_dir(project_slug) / "config"

    def ensure_structure(self) -> None:
        """Create the directory structure if it doesn't exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Initialize registry if it doesn't exist
        if not self.registry_file.exists():
            self._init_registry()

        # Initialize global config if it doesn't exist
        if not self.global_config_file.exists():
            self._init_global_config()

    def ensure_project_structure(self, project_slug: str) -> None:
        """Create the directory structure for a project."""
        self.project_knowledge_dir(project_slug).mkdir(parents=True, exist_ok=True)
        self.project_experts_dir(project_slug).mkdir(parents=True, exist_ok=True)
        self.project_config_dir(project_slug).mkdir(parents=True, exist_ok=True)

    def _init_registry(self) -> None:
        """Initialize an empty project registry."""
        registry = {
            "version": "1.0",
            "created_at": datetime.utcnow().isoformat(),
            "active_project": None,
            "projects": {}
        }
        self.registry_file.write_text(json.dumps(registry, indent=2))
        logger.info(f"Initialized project registry at {self.registry_file}")

    def _init_global_config(self) -> None:
        """Initialize global configuration with defaults."""
        config = {
            "version": "1.0",
            "created_at": datetime.utcnow().isoformat(),
            "defaults": {
                "scout_mode": "smart",
                "auto_index_on_add": True,
                "expert_generation": True
            }
        }
        self.global_config_file.write_text(json.dumps(config, indent=2))
        logger.info(f"Initialized global config at {self.global_config_file}")

    def is_initialized(self) -> bool:
        """Check if the orchestrator home is properly initialized."""
        return (
            self.root.exists() and
            self.config_dir.exists() and
            self.projects_dir.exists() and
            self.registry_file.exists()
        )

    @classmethod
    def from_env(cls) -> "OrchestratorHome":
        """
        Create OrchestratorHome from environment variable or default.

        If SDLC_ORCHESTRATOR_HOME is set, use that path.
        Otherwise, use the .orchestrator directory as the default home.
        """
        home_path = os.environ.get(ORCHESTRATOR_HOME_ENV)

        if home_path:
            root = Path(home_path).resolve()
        else:
            # Default: use .orchestrator directory as home
            root = Path(__file__).parent.parent  # .orchestrator directory

        # Validate the path is not a file
        if root.exists() and root.is_file():
            raise OrchestratorHomeError(
                f"Orchestrator home points to a file, not a directory: {root}"
            )

        return cls(root=root)


# Singleton instance
_orchestrator_home: Optional[OrchestratorHome] = None


def get_orchestrator_home() -> OrchestratorHome:
    """
    Get the orchestrator home instance (singleton).

    Returns:
        OrchestratorHome: The orchestrator home configuration.
        Uses SDLC_ORCHESTRATOR_HOME if set, otherwise defaults to .orchestrator directory.
    """
    global _orchestrator_home

    if _orchestrator_home is None:
        _orchestrator_home = OrchestratorHome.from_env()

    return _orchestrator_home


def reset_orchestrator_home() -> None:
    """Reset the singleton (useful for testing)."""
    global _orchestrator_home
    _orchestrator_home = None


def require_initialized_home() -> OrchestratorHome:
    """
    Get orchestrator home and ensure it's initialized.

    Returns:
        OrchestratorHome: The initialized orchestrator home.

    Raises:
        OrchestratorHomeError: If home is not configured or not initialized.
    """
    home = get_orchestrator_home()

    if not home.is_initialized():
        raise OrchestratorHomeError(
            f"Orchestrator home is not initialized at {home.root}.\n"
            f"Run 'orch init' to initialize it."
        )

    return home
