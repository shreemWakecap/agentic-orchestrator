"""
Unified Configuration Module for Agentic Orchestrator.

This is the SINGLE SOURCE OF TRUTH for all configuration.
All other modules should import from here.

Usage:
    from config import get_config, get_database_config

    config = get_config()
    db_config = get_database_config()

Multi-Project Mode:
    Set SDLC_ORCHESTRATOR_HOME to enable multi-project mode.
    In this mode, projects are managed centrally and isolated from each other.
"""
import os
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

# =============================================================================
# LOAD ENVIRONMENT VARIABLES - THIS IS THE ONLY PLACE IT SHOULD HAPPEN
# =============================================================================

# Determine paths
ORCHESTRATOR_DIR = Path(__file__).parent
PROJECT_ROOT = ORCHESTRATOR_DIR.parent

# Orchestrator home (for multi-project mode)
ORCHESTRATOR_HOME_ENV = "SDLC_ORCHESTRATOR_HOME"

# .env file is always in the .orchestrator directory
ENV_FILE = ORCHESTRATOR_DIR / ".env"

# Load dotenv ONCE at module import
from dotenv import load_dotenv
_env_loaded = load_dotenv(ENV_FILE)

logger = logging.getLogger(__name__)

# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================

@dataclass(frozen=True)
class DatabaseConfig:
    """
    Unified database configuration.

    Provides both sync and async connection URLs from the same base settings.
    This eliminates the duplication between db/config.py and portal/config.py.
    """
    host: str
    port: int
    name: str
    user: str
    password: str
    pool_min: int
    pool_max: int
    pool_recycle: int
    echo: bool

    @property
    def sync_url(self) -> str:
        """PostgreSQL URL for synchronous operations (psycopg2)."""
        password_encoded = quote_plus(self.password)
        return f"postgresql+psycopg2://{self.user}:{password_encoded}@{self.host}:{self.port}/{self.name}"

    @property
    def async_url(self) -> str:
        """PostgreSQL URL for asynchronous operations (asyncpg)."""
        password_encoded = quote_plus(self.password)
        return f"postgresql+asyncpg://{self.user}:{password_encoded}@{self.host}:{self.port}/{self.name}"

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Load configuration from environment variables."""
        return cls(
            host=os.getenv("ORCH_DB_HOST", "localhost"),
            port=int(os.getenv("ORCH_DB_PORT", "5432")),
            name=os.getenv("ORCH_DB_NAME", "orchestrator"),
            user=os.getenv("ORCH_DB_USER", "postgres"),
            password=os.getenv("ORCH_DB_PASSWORD", "postgres"),
            pool_min=int(os.getenv("ORCH_DB_POOL_MIN", "1")),
            pool_max=int(os.getenv("ORCH_DB_POOL_MAX", "10")),
            pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "3600")),
            echo=os.getenv("SQL_ECHO", "false").lower() == "true",
        )


# =============================================================================
# WORKER CONFIGURATION
# =============================================================================

@dataclass(frozen=True)
class WorkerConfig:
    """Worker pool configuration."""
    max_workers: int
    max_queue_size: int
    default_timeout: int
    graceful_timeout: float

    @classmethod
    def from_env(cls) -> "WorkerConfig":
        return cls(
            max_workers=int(os.getenv("MAX_WORKERS", "4")),
            max_queue_size=int(os.getenv("MAX_QUEUE_SIZE", "100")),
            default_timeout=int(os.getenv("DEFAULT_JOB_TIMEOUT", "3600")),
            graceful_timeout=float(os.getenv("GRACEFUL_TIMEOUT", "30.0")),
        )


# =============================================================================
# SERVER CONFIGURATION
# =============================================================================

@dataclass(frozen=True)
class ServerConfig:
    """HTTP server configuration."""
    host: str
    port: int
    reload: bool
    log_level: str
    cors_origins: tuple

    @classmethod
    def from_env(cls) -> "ServerConfig":
        origins = os.getenv("CORS_ORIGINS", "*").split(",")
        return cls(
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "8000")),
            reload=os.getenv("RELOAD", "false").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            cors_origins=tuple(origins),
        )


# =============================================================================
# STREAMING CONFIGURATION
# =============================================================================

@dataclass(frozen=True)
class StreamingConfig:
    """SSE streaming configuration."""
    max_connections_per_job: int
    heartbeat_interval: float
    buffer_size: int
    batch_size: int
    flush_interval: float

    @classmethod
    def from_env(cls) -> "StreamingConfig":
        return cls(
            max_connections_per_job=int(os.getenv("MAX_SSE_CONNECTIONS", "100")),
            heartbeat_interval=float(os.getenv("SSE_HEARTBEAT", "30")),
            buffer_size=int(os.getenv("EVENT_BUFFER_SIZE", "1000")),
            batch_size=int(os.getenv("EVENT_BATCH_SIZE", "10")),
            flush_interval=float(os.getenv("EVENT_FLUSH_INTERVAL", "1.0")),
        )


# =============================================================================
# CLI CONFIGURATION
# =============================================================================

@dataclass(frozen=True)
class CLIConfig:
    """CLI execution configuration."""
    command: str
    project_root: Path
    working_directory: Optional[Path]

    @classmethod
    def from_env(cls) -> "CLIConfig":
        working_dir = os.getenv("CLI_WORKING_DIR")
        return cls(
            command=os.getenv("CLI_COMMAND", "uv run cli.py"),
            project_root=Path(os.getenv("PROJECT_ROOT", str(PROJECT_ROOT))),
            working_directory=Path(working_dir) if working_dir else None,
        )


# =============================================================================
# ORCHESTRATOR HOME CONFIGURATION (Multi-Project Mode)
# =============================================================================

@dataclass(frozen=True)
class OrchestratorHomeConfig:
    """
    Orchestrator home configuration for multi-project mode.

    When enabled, projects are managed in a central location and
    data is isolated per-project.
    """
    enabled: bool
    home_path: Optional[Path]
    projects_dir: Optional[Path]
    config_dir: Optional[Path]
    logs_dir: Optional[Path]

    @property
    def registry_file(self) -> Optional[Path]:
        """Path to project registry file."""
        if self.projects_dir:
            return self.projects_dir / "registry.json"
        return None

    def get_project_dir(self, project_slug: str) -> Optional[Path]:
        """Get data directory for a specific project."""
        if self.projects_dir:
            return self.projects_dir / project_slug
        return None

    @classmethod
    def from_env(cls) -> "OrchestratorHomeConfig":
        """Load from environment variables.

        Multi-project mode is ALWAYS enabled. If SDLC_ORCHESTRATOR_HOME is set,
        use that path. Otherwise, use the .orchestrator directory as home.
        """
        home_path_str = os.getenv(ORCHESTRATOR_HOME_ENV)

        if home_path_str:
            home_path = Path(home_path_str).resolve()
        else:
            # Default: use .orchestrator directory as home
            home_path = ORCHESTRATOR_DIR

        return cls(
            enabled=True,  # ALWAYS ENABLED
            home_path=home_path,
            projects_dir=home_path / "projects",
            config_dir=home_path / "config",
            logs_dir=home_path / "logs",
        )

    def require_enabled(self) -> None:
        """
        Verify multi-project mode is enabled.

        This is now a no-op since multi-project mode is always enabled.
        Kept for backward compatibility.
        """
        # Multi-project mode is always enabled now
        pass


# =============================================================================
# UNIFIED CONFIG
# =============================================================================

@dataclass(frozen=True)
class Config:
    """
    Main configuration container.

    All configuration is immutable (frozen) to prevent accidental modification.
    """
    database: DatabaseConfig
    worker: WorkerConfig
    server: ServerConfig
    streaming: StreamingConfig
    cli: CLIConfig
    orchestrator_home: OrchestratorHomeConfig

    # Path constants
    orchestrator_dir: Path = field(default=ORCHESTRATOR_DIR)
    project_root: Path = field(default=PROJECT_ROOT)

    @property
    def is_multi_project_mode(self) -> bool:
        """Check if multi-project mode is enabled."""
        return self.orchestrator_home.enabled

    @classmethod
    def from_env(cls) -> "Config":
        """Create configuration from environment variables."""
        return cls(
            database=DatabaseConfig.from_env(),
            worker=WorkerConfig.from_env(),
            server=ServerConfig.from_env(),
            streaming=StreamingConfig.from_env(),
            cli=CLIConfig.from_env(),
            orchestrator_home=OrchestratorHomeConfig.from_env(),
        )


# =============================================================================
# SINGLETON ACCESSORS
# =============================================================================

@lru_cache(maxsize=1)
def get_config() -> Config:
    """
    Get the global configuration instance (singleton).

    Uses lru_cache for thread-safe lazy initialization.
    """
    config = Config.from_env()
    logger.info(f"Configuration loaded: database={config.database.host}:{config.database.port}/{config.database.name}")
    return config


@lru_cache(maxsize=1)
def get_database_config() -> DatabaseConfig:
    """Get database configuration (convenience accessor)."""
    return get_config().database


def reload_config() -> Config:
    """
    Reload configuration from environment.

    Clears the cache and returns fresh config.
    Use sparingly - configuration should generally be immutable.
    """
    get_config.cache_clear()
    get_database_config.cache_clear()
    return get_config()


# =============================================================================
# BACKWARD COMPATIBILITY
# =============================================================================

# These provide compatibility with existing code that imports from db.config or portal.config
# They will be deprecated and removed in future versions.

def get_sync_database_url() -> str:
    """Get synchronous database URL (for db/ package)."""
    return get_database_config().sync_url


def get_async_database_url() -> str:
    """Get asynchronous database URL (for portal/ package)."""
    return get_database_config().async_url


@lru_cache(maxsize=1)
def get_orchestrator_home_config() -> OrchestratorHomeConfig:
    """Get orchestrator home configuration (convenience accessor)."""
    return get_config().orchestrator_home


def is_multi_project_mode() -> bool:
    """Check if multi-project mode is enabled."""
    return get_config().is_multi_project_mode


def require_multi_project_mode() -> OrchestratorHomeConfig:
    """
    Get orchestrator home config, raising if not enabled.

    Returns:
        OrchestratorHomeConfig: The home configuration.

    Raises:
        EnvironmentError: If SDLC_ORCHESTRATOR_HOME is not set.
    """
    config = get_orchestrator_home_config()
    config.require_enabled()
    return config
