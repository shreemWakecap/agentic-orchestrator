"""
Database Configuration.

Provides configurable database settings loaded from db/config.json.
"""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# The db/ folder location
DB_DIR = Path(__file__).parent


@dataclass
class DatabaseConfig:
    """
    Database configuration with external file support.

    Settings can be loaded from db/config.json or use defaults.
    All database files live in the db/ folder.
    """
    db_name: str = "orchestrator.db"
    timeout: float = 30.0
    journal_mode: str = "WAL"           # WAL for better concurrency
    synchronous: str = "NORMAL"         # Balance between safety and speed
    foreign_keys: bool = True
    cache_size_kb: int = 64000          # 64MB cache
    check_same_thread: bool = False     # Allow multi-thread access

    @classmethod
    def load(cls) -> "DatabaseConfig":
        """
        Load configuration from db/config.json or use defaults.

        Returns:
            DatabaseConfig instance
        """
        config_file = DB_DIR / "config.json"
        if config_file.exists():
            try:
                data = json.loads(config_file.read_text(encoding="utf-8"))
                return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            except (json.JSONDecodeError, TypeError):
                pass  # Use defaults on error
        return cls()

    def get_db_path(self) -> Path:
        """
        Resolve full database path (in the db/ folder).

        Returns:
            Full path to database file
        """
        return DB_DIR / self.db_name

    def save(self) -> None:
        """Save configuration to db/config.json."""
        config_file = DB_DIR / "config.json"
        data = {
            "db_name": self.db_name,
            "timeout": self.timeout,
            "journal_mode": self.journal_mode,
            "synchronous": self.synchronous,
            "foreign_keys": self.foreign_keys,
            "cache_size_kb": self.cache_size_kb,
        }
        config_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "db_name": self.db_name,
            "timeout": self.timeout,
            "journal_mode": self.journal_mode,
            "synchronous": self.synchronous,
            "foreign_keys": self.foreign_keys,
            "cache_size_kb": self.cache_size_kb,
            "check_same_thread": self.check_same_thread,
        }
