"""
Portal Configuration.

DEPRECATED: This module now delegates to the unified config module.
Import from `config` directly for new code.

Backward compatibility is maintained for existing code.
"""
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List

# Ensure orchestrator directory is in path for unified config import
PORTAL_DIR = Path(__file__).parent
ORCHESTRATOR_DIR = PORTAL_DIR.parent
if str(ORCHESTRATOR_DIR) not in sys.path:
    sys.path.insert(0, str(ORCHESTRATOR_DIR))

# Import from unified config (this also loads dotenv)
from config import get_config as _get_unified_config, get_database_config as _get_db_config


def get_project_root() -> Path:
    """Get the project root directory."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / ".orchestrator").exists():
            return current
        if current.name == ".orchestrator":
            return current.parent
        current = current.parent
    return Path.cwd()


PROJECT_ROOT = get_project_root()


@dataclass
class DatabaseConfig:
    """Database configuration - delegates to unified config."""
    url: str = field(default_factory=lambda: _get_db_config().async_url)
    echo: bool = field(default_factory=lambda: _get_db_config().echo)
    pool_size: int = field(default_factory=lambda: _get_db_config().pool_min)
    pool_recycle: int = field(default_factory=lambda: _get_db_config().pool_recycle)


@dataclass
class WorkerConfig:
    """Worker pool configuration - delegates to unified config."""
    max_workers: int = field(default_factory=lambda: _get_unified_config().worker.max_workers)
    max_queue_size: int = field(default_factory=lambda: _get_unified_config().worker.max_queue_size)
    default_timeout: int = field(default_factory=lambda: _get_unified_config().worker.default_timeout)
    graceful_timeout: float = field(default_factory=lambda: _get_unified_config().worker.graceful_timeout)


@dataclass
class CLIConfig:
    """CLI execution configuration - delegates to unified config."""
    command: str = field(default_factory=lambda: _get_unified_config().cli.command)
    project_root: Path = field(default_factory=lambda: _get_unified_config().cli.project_root)
    working_directory: Optional[Path] = field(default_factory=lambda: _get_unified_config().cli.working_directory)


@dataclass
class StreamingConfig:
    """SSE streaming configuration - delegates to unified config."""
    max_connections_per_job: int = field(default_factory=lambda: _get_unified_config().streaming.max_connections_per_job)
    heartbeat_interval: float = field(default_factory=lambda: _get_unified_config().streaming.heartbeat_interval)
    buffer_size: int = field(default_factory=lambda: _get_unified_config().streaming.buffer_size)
    batch_size: int = field(default_factory=lambda: _get_unified_config().streaming.batch_size)
    flush_interval: float = field(default_factory=lambda: _get_unified_config().streaming.flush_interval)


@dataclass
class ServerConfig:
    """HTTP server configuration - delegates to unified config."""
    host: str = field(default_factory=lambda: _get_unified_config().server.host)
    port: int = field(default_factory=lambda: _get_unified_config().server.port)
    reload: bool = field(default_factory=lambda: _get_unified_config().server.reload)
    log_level: str = field(default_factory=lambda: _get_unified_config().server.log_level)
    cors_origins: List[str] = field(default_factory=lambda: list(_get_unified_config().server.cors_origins))


@dataclass
class Config:
    """
    Main configuration container - delegates to unified config.

    For new code, use:
        from config import get_config
    """
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    worker: WorkerConfig = field(default_factory=WorkerConfig)
    cli: CLIConfig = field(default_factory=CLIConfig)
    streaming: StreamingConfig = field(default_factory=StreamingConfig)
    server: ServerConfig = field(default_factory=ServerConfig)

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.cli.project_root.exists():
            self.cli.project_root = Path.cwd()

    def as_dict(self) -> dict:
        """Convert configuration to dictionary."""
        return {
            "database": {
                "url": self.database.url,
                "echo": self.database.echo,
                "pool_size": self.database.pool_size,
            },
            "worker": {
                "max_workers": self.worker.max_workers,
                "max_queue_size": self.worker.max_queue_size,
                "default_timeout": self.worker.default_timeout,
                "graceful_timeout": self.worker.graceful_timeout,
            },
            "cli": {
                "command": self.cli.command,
                "project_root": str(self.cli.project_root),
            },
            "streaming": {
                "max_connections_per_job": self.streaming.max_connections_per_job,
                "heartbeat_interval": self.streaming.heartbeat_interval,
                "buffer_size": self.streaming.buffer_size,
            },
            "server": {
                "host": self.server.host,
                "port": self.server.port,
                "log_level": self.server.log_level,
            },
        }


# Global config instance - lazily initialized
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def reload_config() -> Config:
    """Reload configuration from environment variables."""
    global _config
    _config = Config()
    return _config


# Convenience alias
config = get_config()
