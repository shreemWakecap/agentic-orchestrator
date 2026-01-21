"""
Database Configuration - loads from environment variables.
"""
import os


class DatabaseConfig:
    """
    PostgreSQL configuration from environment variables.

    Environment variables:
        ORCH_DB_HOST     - Database host (default: localhost)
        ORCH_DB_PORT     - Database port (default: 5432)
        ORCH_DB_NAME     - Database name (default: orchestrator)
        ORCH_DB_USER     - Database user (default: postgres)
        ORCH_DB_PASSWORD - Database password (default: postgres)
        ORCH_DB_POOL_MIN - Min pool connections (default: 1)
        ORCH_DB_POOL_MAX - Max pool connections (default: 10)
    """

    def __init__(self):
        self.host = os.getenv("ORCH_DB_HOST", "localhost")
        self.port = int(os.getenv("ORCH_DB_PORT", "5432"))
        self.name = os.getenv("ORCH_DB_NAME", "orchestrator")
        self.user = os.getenv("ORCH_DB_USER", "postgres")
        self.password = os.getenv("ORCH_DB_PASSWORD", "postgres")
        self.pool_min = int(os.getenv("ORCH_DB_POOL_MIN", "1"))
        self.pool_max = int(os.getenv("ORCH_DB_POOL_MAX", "10"))

    @property
    def connection_string(self) -> str:
        """Build PostgreSQL connection string."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

    @classmethod
    def load(cls) -> "DatabaseConfig":
        """Load configuration from environment."""
        return cls()
