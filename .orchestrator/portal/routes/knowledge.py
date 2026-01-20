"""Knowledge-related API routes."""
import uuid
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException

from db import KnowledgeRepository, RunRepository
from portal.dependencies import get_knowledge_repo, get_run_repo
from portal.schemas.requests import ScoutingRequest, PathScoutRequest, KeywordScoutRequest
from portal.schemas.responses import WorkflowStartResponse
from portal.services.knowledge_service import KnowledgeService
from portal.services.task_manager import TaskManager, get_task_manager

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


def _get_knowledge_service(
    knowledge_repo: KnowledgeRepository = Depends(get_knowledge_repo),
) -> KnowledgeService:
    """Get knowledge service with injected dependencies."""
    return KnowledgeService(knowledge_repo)


@router.get("")
async def get_knowledge_overview(
    knowledge_service: KnowledgeService = Depends(_get_knowledge_service),
) -> Dict[str, Any]:
    """Get knowledge overview/summary.

    Returns a lightweight summary of the current knowledge state
    including project info, counts, and last scan details.
    """
    overview = await knowledge_service.get_knowledge_overview()
    return {
        "has_knowledge": overview.has_knowledge,
        "has_expert_index": overview.has_expert_index,
        "project_name": overview.project_name,
        "project_type": overview.project_type,
        "primary_language": overview.primary_language,
        "last_updated": overview.last_updated,
        "languages_count": overview.languages_count,
        "frameworks_count": overview.frameworks_count,
        "tools_count": overview.tools_count,
        "modules_count": overview.modules_count,
        "domains_count": overview.domains_count,
        "last_scan": overview.last_scan,
    }


@router.get("/full")
async def get_full_knowledge(
    knowledge_service: KnowledgeService = Depends(_get_knowledge_service),
) -> Dict[str, Any]:
    """Get complete codebase knowledge.

    Returns the full knowledge data structure including
    project info, technologies, architecture, domains, and patterns.
    """
    knowledge = await knowledge_service.get_full_knowledge()
    if not knowledge:
        return {"knowledge": None, "message": "No knowledge available. Run scouting first."}
    return {"knowledge": knowledge}


@router.get("/expert-index")
async def get_expert_index(
    knowledge_service: KnowledgeService = Depends(_get_knowledge_service),
) -> Dict[str, Any]:
    """Get expert index for intelligent agent selection.

    Returns the expert index including experts list,
    keyword mappings, and path mappings.
    """
    index = await knowledge_service.get_expert_index()
    if not index:
        return {"expert_index": None, "message": "No expert index available. Run scouting first."}
    return {"expert_index": index}


@router.get("/scan-meta")
async def get_scan_metadata(
    knowledge_service: KnowledgeService = Depends(_get_knowledge_service),
) -> Dict[str, Any]:
    """Get scan metadata and history.

    Returns metadata about the most recent scan including
    scan ID, timestamps, files scanned, and generated experts.
    """
    meta = await knowledge_service.get_scan_history()
    if not meta:
        return {"scan_meta": None, "message": "No scan history available."}
    return {"scan_meta": meta}


@router.post("/scout", response_model=WorkflowStartResponse)
async def start_scouting(
    request: ScoutingRequest,
    run_repo: RunRepository = Depends(get_run_repo),
    task_manager: TaskManager = Depends(get_task_manager),
) -> WorkflowStartResponse:
    """Start a scouting workflow to discover codebase knowledge.

    Accepts optional targeting parameters to focus the scan on
    specific paths, keywords, or technologies.
    """
    from portal.services.workflow_runner import run_scouting_workflow_sync

    run_id = str(uuid.uuid4())[:8]

    # Create run entry in database
    run_repo.create(run_id, workflow="scouting")

    # Submit to TaskManager for background execution
    task_manager.submit_task(
        func=run_scouting_workflow_sync,
        args=(run_id,),
        kwargs={
            "scan_type": request.scan_type or "quick",
            "target_paths": request.target_paths,
            "target_keywords": request.target_keywords,
            "target_tech": request.target_tech,
            "generate_experts": request.generate_experts if request.generate_experts is not None else True,
        },
        name=f"Scouting: {request.scan_type or 'quick'}",
        task_id=run_id,
        task_type="scout",
        metadata={"run_id": run_id, "scan_type": request.scan_type or "quick"},
    )

    return WorkflowStartResponse(run_id=run_id, status="started")


@router.post("/scout/path", response_model=WorkflowStartResponse)
async def scout_path(
    request: PathScoutRequest,
    run_repo: RunRepository = Depends(get_run_repo),
    task_manager: TaskManager = Depends(get_task_manager),
) -> WorkflowStartResponse:
    """Scout a specific path for knowledge extraction.

    Triggers a quick scouting workflow focused on a single path.
    Useful for targeted knowledge gathering on specific files or directories.
    """
    from portal.services.workflow_runner import run_scouting_workflow_sync

    run_id = str(uuid.uuid4())[:8]

    # Create run entry in database
    run_repo.create(run_id, workflow="scouting")

    # Submit to TaskManager for background execution
    task_manager.submit_task(
        func=run_scouting_workflow_sync,
        args=(run_id,),
        kwargs={
            "scan_type": "quick",
            "target_paths": [request.path],
            "target_keywords": None,
            "target_tech": None,
            "generate_experts": True,
        },
        name=f"Scouting: {request.path}",
        task_id=run_id,
        task_type="scout",
        metadata={"run_id": run_id, "path": request.path},
    )

    return WorkflowStartResponse(run_id=run_id, status="started")


@router.post("/scout/keywords", response_model=WorkflowStartResponse)
async def scout_keywords(
    request: KeywordScoutRequest,
    run_repo: RunRepository = Depends(get_run_repo),
    task_manager: TaskManager = Depends(get_task_manager),
) -> WorkflowStartResponse:
    """Scout based on keywords for knowledge extraction.

    Accepts a comma-separated keywords string, parses it into a list,
    and triggers a quick scouting workflow focused on those keywords.
    Useful for targeted knowledge gathering on specific topics or patterns.
    """
    from portal.services.workflow_runner import run_scouting_workflow_sync

    run_id = str(uuid.uuid4())[:8]

    # Parse comma-separated keywords into list
    keywords_list = [kw.strip() for kw in request.keywords.split(",") if kw.strip()]

    # Create run entry in database
    run_repo.create(run_id, workflow="scouting")

    # Submit to TaskManager for background execution
    task_manager.submit_task(
        func=run_scouting_workflow_sync,
        args=(run_id,),
        kwargs={
            "scan_type": "quick",
            "target_paths": None,
            "target_keywords": keywords_list,
            "target_tech": None,
            "generate_experts": True,
        },
        name=f"Scouting: {request.keywords[:30]}..." if len(request.keywords) > 30 else f"Scouting: {request.keywords}",
        task_id=run_id,
        task_type="scout",
        metadata={"run_id": run_id, "keywords": request.keywords},
    )

    return WorkflowStartResponse(run_id=run_id, status="started")


@router.delete("")
async def clear_knowledge(
    knowledge_service: KnowledgeService = Depends(_get_knowledge_service),
) -> Dict[str, Any]:
    """Clear all codebase knowledge.

    Removes all knowledge data from the database including
    project info, technologies, architecture, domains, patterns,
    expert index, and scan metadata.
    """
    success = await knowledge_service.clear_knowledge()
    if not success:
        raise HTTPException(status_code=500, detail="Failed to clear knowledge")
    return {"status": "cleared", "message": "All knowledge data has been removed"}
