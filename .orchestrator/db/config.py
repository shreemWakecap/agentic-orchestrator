"""
Database Configuration.

DEPRECATED: This module now delegates to the unified config module.
Import from `config` directly for new code.

Backward compatibility is maintained for existing code.
"""
import sys
from pathlib import Path

# Ensure orchestrator directory is in path for unified config import
ORCHESTRATOR_DIR = Path(__file__).parent.parent
if str(ORCHESTRATOR_DIR) not in sys.path:
    sys.path.insert(0, str(ORCHESTRATOR_DIR))

# Import from unified config (this also loads dotenv)
from config import get_database_config as _get_db_config


class DatabaseConfig:
    """
    PostgreSQL configuration - delegates to unified config.

    This class maintains backward compatibility with existing code
    that uses DatabaseConfig directly.

    For new code, use:
        from config import get_database_config
    """

    def __init__(self):
        self._config = _get_db_config()

    @property
    def host(self) -> str:
        return self._config.host

    @property
    def port(self) -> int:
        return self._config.port

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def user(self) -> str:
        return self._config.user

    @property
    def password(self) -> str:
        return self._config.password

    @property
    def pool_min(self) -> int:
        return self._config.pool_min

    @property
    def pool_max(self) -> int:
        return self._config.pool_max

    @property
    def connection_string(self) -> str:
        """Build PostgreSQL connection string for sync operations."""
        return self._config.sync_url

    @classmethod
    def load(cls) -> "DatabaseConfig":
        """Load configuration from environment."""
        return cls()
