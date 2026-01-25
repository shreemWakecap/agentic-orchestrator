"""
API routes for agent definition management.
"""
import json
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db.repositories.agent_definition import get_agent_definition_repository


router = APIRouter(prefix="/api/agent-definitions", tags=["agent-definitions"])


class AgentCreateRequest(BaseModel):
    """Request model for creating an agent."""
    name: str
    system_prompt: str
    description: Optional[str] = None
    tools: Optional[List[str]] = None
    model: Optional[str] = None
    is_agentic: bool = False
    output_markers: Optional[List[str]] = None


class AgentUpdateRequest(BaseModel):
    """Request model for updating an agent."""
    system_prompt: Optional[str] = None
    description: Optional[str] = None
    tools: Optional[List[str]] = None
    model: Optional[str] = None
    is_agentic: Optional[bool] = None
    output_markers: Optional[List[str]] = None


@router.get("")
async def list_agents() -> Dict[str, Any]:
    """List all agent definitions."""
    repo = get_agent_definition_repository()
    agents = repo.list_all()

    return {
        "agents": [
            {
                "name": a.name,
                "description": a.description,
                "is_agentic": a.is_agentic,
                "model": a.model,
                "tools": json.loads(a.tools_json or "[]"),
                "version": a.version,
                "updated_at": a.updated_at.isoformat() if a.updated_at else None,
            }
            for a in agents
        ],
        "count": len(agents),
    }


@router.get("/{name}")
async def get_agent(name: str) -> Dict[str, Any]:
    """Get agent definition by name."""
    repo = get_agent_definition_repository()
    agent = repo.get_by_name(name)

    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {name}")

    return {
        "name": agent.name,
        "description": agent.description,
        "system_prompt": agent.system_prompt,
        "tools": json.loads(agent.tools_json or "[]"),
        "model": agent.model,
        "is_agentic": agent.is_agentic,
        "output_markers": json.loads(agent.output_markers_json or "[]"),
        "version": agent.version,
        "created_at": agent.created_at.isoformat() if agent.created_at else None,
        "updated_at": agent.updated_at.isoformat() if agent.updated_at else None,
    }


@router.post("")
async def create_agent(request: AgentCreateRequest) -> Dict[str, Any]:
    """Create a new agent definition."""
    repo = get_agent_definition_repository()

    if repo.exists(request.name):
        raise HTTPException(status_code=409, detail=f"Agent already exists: {request.name}")

    agent = repo.create(
        name=request.name,
        system_prompt=request.system_prompt,
        description=request.description,
        tools=request.tools,
        model=request.model,
        is_agentic=request.is_agentic,
        output_markers=request.output_markers,
    )

    return {"status": "created", "name": agent.name}


@router.put("/{name}")
async def update_agent(name: str, request: AgentUpdateRequest) -> Dict[str, Any]:
    """Update an agent definition."""
    repo = get_agent_definition_repository()

    if not repo.exists(name):
        raise HTTPException(status_code=404, detail=f"Agent not found: {name}")

    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    agent = repo.update(name, **updates)

    return {"status": "updated", "name": agent.name}


@router.delete("/{name}")
async def delete_agent(name: str) -> Dict[str, Any]:
    """Delete an agent definition."""
    repo = get_agent_definition_repository()

    if not repo.delete(name):
        raise HTTPException(status_code=404, detail=f"Agent not found: {name}")

    return {"status": "deleted", "name": name}
