"""
Repository for orchestrator configuration.

This module provides database access for orchestrator configuration that replaces
the .orchestrator/config/agent.json and budget.json files.
"""
import json
from typing import Optional, Dict, Any
from sqlalchemy import select

from .base import BaseRepository
from db.models import OrchestratorConfig


# Default configurations
DEFAULT_AGENT_CONFIG = {
    "scan": {
        "solution_paths": [],
        "exclude_paths": ["node_modules", "__pycache__", ".git", ".venv", "venv"],
        "include_extensions": [".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".cs", ".go", ".rs"],
        "focus_on_solution": False
    },
    "timeouts": {
        "print_mode": 300,
        "agentic_mode": 600,
        "expert_consultation": 180
    },
    "retry": {
        "max_attempts": 3,
        "base_delay": 1.0,
        "agentic_base_delay": 2.0,
        "backoff_multiplier": 2.0,
        "max_delay": 60.0
    },
    "context_limits": {
        "base_codebase": 4000,
        "base_scout": 3500,
        "base_architect": 2500,
        "minimum": 1500
    },
    "parallel": {
        "max_sub_features": 3,
        "max_expert_workers": 3,
        "max_build_workers": 3,
        "overlap_build_test": False
    },
    "thinking": {
        "enabled": False,
        "budget": 10000,
        "timeout_multiplier": 1.5
    }
}

DEFAULT_BUDGET_CONFIG = {
    "daily_limit": 5.0,
    "weekly_limit": 25.0,
    "monthly_limit": 100.0,
    "per_workflow_limit": None,
    "warning_threshold": 0.8
}


class OrchestratorConfigRepository(BaseRepository):
    """Repository for managing orchestrator configuration."""

    model = OrchestratorConfig
    table_name = "orchestrator_config"

    def get_config(self, config_type: str) -> Optional[Dict[str, Any]]:
        """Get configuration by type."""
        with self.session() as session:
            stmt = select(OrchestratorConfig).where(
                OrchestratorConfig.config_type == config_type
            )
            config = session.execute(stmt).scalar_one_or_none()
            if config:
                return json.loads(config.config_data_json)
            return None

    def set_config(self, config_type: str, data: Dict[str, Any]) -> OrchestratorConfig:
        """Set or update configuration."""
        with self.session() as session:
            stmt = select(OrchestratorConfig).where(
                OrchestratorConfig.config_type == config_type
            )
            existing = session.execute(stmt).scalar_one_or_none()

            if existing:
                existing.config_data_json = json.dumps(data)
                existing.version += 1
                session.commit()
                session.refresh(existing)
                return existing
            else:
                config = OrchestratorConfig(
                    config_type=config_type,
                    config_data_json=json.dumps(data),
                )
                session.add(config)
                session.commit()
                session.refresh(config)
                return config

    def get_agent_config(self) -> Dict[str, Any]:
        """Get agent configuration with defaults."""
        config = self.get_config("agent")
        if not config:
            return DEFAULT_AGENT_CONFIG.copy()
        # Merge with defaults to ensure all keys exist
        result = _deep_merge(DEFAULT_AGENT_CONFIG, config)
        return result

    def get_budget_config(self) -> Dict[str, Any]:
        """Get budget configuration with defaults."""
        config = self.get_config("budget")
        if not config:
            return DEFAULT_BUDGET_CONFIG.copy()
        result = DEFAULT_BUDGET_CONFIG.copy()
        result.update(config)
        return result

    def update_agent_config(self, updates: Dict[str, Any]) -> OrchestratorConfig:
        """Update agent configuration with partial updates."""
        current = self.get_agent_config()
        merged = _deep_merge(current, updates)
        return self.set_config("agent", merged)

    def update_budget_config(self, updates: Dict[str, Any]) -> OrchestratorConfig:
        """Update budget configuration with partial updates."""
        current = self.get_budget_config()
        current.update(updates)
        return self.set_config("budget", current)

    def delete_config(self, config_type: str) -> bool:
        """Delete a configuration."""
        with self.session() as session:
            stmt = select(OrchestratorConfig).where(
                OrchestratorConfig.config_type == config_type
            )
            config = session.execute(stmt).scalar_one_or_none()
            if config:
                session.delete(config)
                session.commit()
                return True
            return False

    def list_all(self) -> list:
        """List all configuration entries."""
        with self.session() as session:
            stmt = select(OrchestratorConfig).order_by(OrchestratorConfig.config_type)
            return list(session.execute(stmt).scalars())

    def to_dict(self, config: OrchestratorConfig) -> dict:
        """Convert config to dictionary."""
        return {
            "id": config.id,
            "config_type": config.config_type,
            "config_data": json.loads(config.config_data_json),
            "version": config.version,
            "created_at": config.created_at.isoformat() if config.created_at else None,
            "updated_at": config.updated_at.isoformat() if config.updated_at else None,
        }


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries, with override taking precedence."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# Singleton instance
_repository: Optional[OrchestratorConfigRepository] = None


def get_config_repository() -> OrchestratorConfigRepository:
    """Get singleton repository instance."""
    global _repository
    if _repository is None:
        _repository = OrchestratorConfigRepository()
    return _repository
