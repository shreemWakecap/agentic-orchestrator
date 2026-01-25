"""
API routes for expert definition management.
"""
import json
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from db.repositories.expert_definition import get_expert_definition_repository


router = APIRouter(prefix="/api/expert-definitions", tags=["expert-definitions"])


class ExpertCreateRequest(BaseModel):
    """Request model for creating an expert."""
    name: str
    system_prompt: str
    description: Optional[str] = None
    expert_type: str = "tech"
    category: str = "general"
    domain_keywords: Optional[List[str]] = None
    module_path: Optional[str] = None
    trigger_keywords: Optional[List[str]] = None
    trigger_paths: Optional[List[str]] = None
    trigger_topics: Optional[List[str]] = None
    weight: float = 1.0


class ExpertUpdateRequest(BaseModel):
    """Request model for updating an expert."""
    system_prompt: Optional[str] = None
    description: Optional[str] = None
    expert_type: Optional[str] = None
    category: Optional[str] = None
    domain_keywords: Optional[List[str]] = None
    module_path: Optional[str] = None
    trigger_keywords: Optional[List[str]] = None
    trigger_paths: Optional[List[str]] = None
    trigger_topics: Optional[List[str]] = None
    weight: Optional[float] = None


@router.get("")
async def list_experts(expert_type: Optional[str] = Query(None, description="Filter by type: tech, domain, module")) -> Dict[str, Any]:
    """List all expert definitions."""
    repo = get_expert_definition_repository()

    if expert_type:
        experts = repo.list_by_type(expert_type)
    else:
        experts = repo.list_all()

    return {
        "experts": [
            {
                "name": e.name,
                "description": e.description,
                "expert_type": e.expert_type,
                "category": e.category,
                "domain_keywords": json.loads(e.domain_keywords_json or "[]"),
                "module_path": e.module_path,
                "weight": e.weight,
                "version": e.version,
                "updated_at": e.updated_at.isoformat() if e.updated_at else None,
            }
            for e in experts
        ],
        "count": len(experts),
    }


@router.get("/search")
async def search_experts(keywords: str = Query(..., description="Comma-separated keywords to search")) -> Dict[str, Any]:
    """Search experts by keywords (comma-separated)."""
    repo = get_expert_definition_repository()
    keyword_list = [k.strip() for k in keywords.split(",") if k.strip()]
    experts = repo.find_by_keywords(keyword_list)

    return {
        "keywords": keyword_list,
        "experts": [
            {
                "name": e.name,
                "description": e.description,
                "expert_type": e.expert_type,
                "domain_keywords": json.loads(e.domain_keywords_json or "[]"),
            }
            for e in experts
        ],
        "count": len(experts),
    }


@router.get("/{name}")
async def get_expert(name: str) -> Dict[str, Any]:
    """Get expert definition by name."""
    repo = get_expert_definition_repository()
    expert = repo.get_by_name(name)

    if not expert:
        raise HTTPException(status_code=404, detail=f"Expert not found: {name}")

    return {
        "name": expert.name,
        "description": expert.description,
        "system_prompt": expert.system_prompt,
        "expert_type": expert.expert_type,
        "category": expert.category,
        "domain_keywords": json.loads(expert.domain_keywords_json or "[]"),
        "module_path": expert.module_path,
        "trigger_keywords": json.loads(expert.trigger_keywords_json or "[]"),
        "trigger_paths": json.loads(expert.trigger_paths_json or "[]"),
        "trigger_topics": json.loads(expert.trigger_topics_json or "[]"),
        "weight": expert.weight,
        "version": expert.version,
        "created_at": expert.created_at.isoformat() if expert.created_at else None,
        "updated_at": expert.updated_at.isoformat() if expert.updated_at else None,
    }


@router.post("")
async def create_expert(request: ExpertCreateRequest) -> Dict[str, Any]:
    """Create a new expert definition."""
    repo = get_expert_definition_repository()

    if repo.exists(request.name):
        raise HTTPException(status_code=409, detail=f"Expert already exists: {request.name}")

    expert = repo.create(
        name=request.name,
        system_prompt=request.system_prompt,
        description=request.description,
        expert_type=request.expert_type,
        category=request.category,
        domain_keywords=request.domain_keywords,
        module_path=request.module_path,
        trigger_keywords=request.trigger_keywords,
        trigger_paths=request.trigger_paths,
        trigger_topics=request.trigger_topics,
        weight=request.weight,
    )

    return {"status": "created", "name": expert.name}


@router.put("/{name}")
async def update_expert(name: str, request: ExpertUpdateRequest) -> Dict[str, Any]:
    """Update an expert definition."""
    repo = get_expert_definition_repository()

    if not repo.exists(name):
        raise HTTPException(status_code=404, detail=f"Expert not found: {name}")

    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    expert = repo.update(name, **updates)

    return {"status": "updated", "name": expert.name}


@router.delete("/{name}")
async def delete_expert(name: str) -> Dict[str, Any]:
    """Delete an expert definition."""
    repo = get_expert_definition_repository()

    if not repo.delete(name):
        raise HTTPException(status_code=404, detail=f"Expert not found: {name}")

    return {"status": "deleted", "name": name}
