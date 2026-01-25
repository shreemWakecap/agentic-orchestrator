"""
API routes for orchestrator configuration.
"""
from typing import Dict, Any
from fastapi import APIRouter

from db.repositories.config_repository import get_config_repository


router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/agent")
async def get_agent_config() -> Dict[str, Any]:
    """Get agent configuration (merged with defaults)."""
    repo = get_config_repository()
    return repo.get_agent_config()


@router.put("/agent")
async def update_agent_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Update agent configuration (full replace)."""
    repo = get_config_repository()
    repo.set_config("agent", config)

    # Clear cached config in ConfigLoader
    from core.config import ConfigLoader
    ConfigLoader.clear_cache()

    return {"status": "updated", "config_type": "agent"}


@router.patch("/agent")
async def patch_agent_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Partially update agent configuration (merge with existing)."""
    repo = get_config_repository()
    repo.update_agent_config(updates)

    # Clear cached config in ConfigLoader
    from core.config import ConfigLoader
    ConfigLoader.clear_cache()

    return {"status": "updated", "config_type": "agent"}


@router.get("/budget")
async def get_budget_config() -> Dict[str, Any]:
    """Get budget configuration (merged with defaults)."""
    repo = get_config_repository()
    return repo.get_budget_config()


@router.put("/budget")
async def update_budget_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Update budget configuration (full replace)."""
    repo = get_config_repository()
    repo.set_config("budget", config)

    # Clear cached config in ConfigLoader
    from core.config import ConfigLoader
    ConfigLoader.clear_cache()

    return {"status": "updated", "config_type": "budget"}


@router.patch("/budget")
async def patch_budget_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Partially update budget configuration (merge with existing)."""
    repo = get_config_repository()
    repo.update_budget_config(updates)

    # Clear cached config in ConfigLoader
    from core.config import ConfigLoader
    ConfigLoader.clear_cache()

    return {"status": "updated", "config_type": "budget"}
