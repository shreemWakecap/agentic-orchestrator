"""
Application Configuration

All configuration is loaded from environment variables with sensible defaults.
Provides centralized configuration management for the Orchestrator Portal.

Usage:
    from .config import config

    # Access settings
    max_workers = config.worker.max_workers
    db_url = config.database.url
"""
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List


def get_project_root() -> Path:
    """Get the project root directory."""
    # Start from current file and go up to find .orchestrator
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
    """Database configuration settings."""
    url: str = field(default_factory=lambda: os.getenv(
        "DATABASE_URL",
        f"sqlite+aiosqlite:///{PROJECT_ROOT / '.orchestrator' / 'jobs.db'}"
    ))
    echo: bool = field(default_factory=lambda: os.getenv("SQL_ECHO", "false").lower() == "true")
    pool_size: int = field(default_factory=lambda: int(os.getenv("DB_POOL_SIZE", "5")))
    pool_recycle: int = field(default_factory=lambda: int(os.getenv("DB_POOL_RECYCLE", "3600")))


@dataclass
class WorkerConfig:
    """Worker pool configuration settings."""
    max_workers: int = field(default_factory=lambda: int(os.getenv("MAX_WORKERS", "4")))
    max_queue_size: int = field(default_factory=lambda: int(os.getenv("MAX_QUEUE_SIZE", "100")))
    default_timeout: int = field(default_factory=lambda: int(os.getenv("DEFAULT_JOB_TIMEOUT", "3600")))
    graceful_timeout: float = field(default_factory=lambda: float(os.getenv("GRACEFUL_TIMEOUT", "30.0")))


@dataclass
class CLIConfig:
    """CLI execution configuration settings."""
    command: str = field(default_factory=lambda: os.getenv("CLI_COMMAND", "uv run cli.py"))
    project_root: Path = field(default_factory=lambda: Path(os.getenv("PROJECT_ROOT", str(PROJECT_ROOT))))
    working_directory: Optional[Path] = field(default_factory=lambda: (
        Path(os.getenv("CLI_WORKING_DIR")) if os.getenv("CLI_WORKING_DIR") else None
    ))


@dataclass
class StreamingConfig:
    """SSE streaming configuration settings."""
    max_connections_per_job: int = field(default_factory=lambda: int(os.getenv("MAX_SSE_CONNECTIONS", "100")))
    heartbeat_interval: float = field(default_factory=lambda: float(os.getenv("SSE_HEARTBEAT", "30")))
    buffer_size: int = field(default_factory=lambda: int(os.getenv("EVENT_BUFFER_SIZE", "1000")))
    batch_size: int = field(default_factory=lambda: int(os.getenv("EVENT_BATCH_SIZE", "10")))
    flush_interval: float = field(default_factory=lambda: float(os.getenv("EVENT_FLUSH_INTERVAL", "1.0")))


@dataclass
class ServerConfig:
    """HTTP server configuration settings."""
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    reload: bool = field(default_factory=lambda: os.getenv("RELOAD", "false").lower() == "true")
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    cors_origins: List[str] = field(default_factory=lambda: os.getenv("CORS_ORIGINS", "*").split(","))


@dataclass
class Config:
    """
    Main configuration container.

    Provides access to all configuration subsections.

    Example:
        from .config import config

        # Database settings
        print(config.database.url)

        # Worker settings
        print(config.worker.max_workers)

        # Server settings
        print(config.server.port)
    """
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    worker: WorkerConfig = field(default_factory=WorkerConfig)
    cli: CLIConfig = field(default_factory=CLIConfig)
    streaming: StreamingConfig = field(default_factory=StreamingConfig)
    server: ServerConfig = field(default_factory=ServerConfig)

    def __post_init__(self):
        """Validate configuration after initialization."""
        # Ensure project root exists
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
