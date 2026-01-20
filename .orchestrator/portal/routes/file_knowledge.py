"""File-level knowledge API routes."""
import uuid
from typing import Dict, Any, List
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException

from db import FileKnowledgeRepository, RunRepository
from portal.dependencies import get_file_knowledge_repo, get_run_repo, get_project_root
from portal.schemas.requests import FileScoutRequest
from portal.schemas.responses import WorkflowStartResponse
from portal.services.file_knowledge_service import FileKnowledgeService
from portal.services.task_manager import TaskManager, get_task_manager

router = APIRouter(prefix="/api/knowledge/files", tags=["file-knowledge"])


def _get_file_knowledge_service(
    file_knowledge_repo: FileKnowledgeRepository = Depends(get_file_knowledge_repo),
    project_root: Path = Depends(get_project_root),
) -> FileKnowledgeService:
    """Get file knowledge service with injected dependencies."""
    return FileKnowledgeService(file_knowledge_repo, project_root)


@router.get("")
async def list_file_knowledge(
    file_knowledge_service: FileKnowledgeService = Depends(_get_file_knowledge_service),
) -> Dict[str, Any]:
    """List all file-level knowledge.

    Returns a summary of all scanned files including aggregate statistics
    and individual file information.
    """
    summary = await file_knowledge_service.get_all_files_summary()
    return {
        "total_files": summary.total_files,
        "total_size_bytes": summary.total_size_bytes,
        "total_lines": summary.total_lines,
        "languages": summary.languages,
        "file_types": summary.file_types,
        "last_scan_time": summary.last_scan_time,
        "files": summary.files,
    }


@router.get("/{file_path:path}")
async def get_file_knowledge(
    file_path: str,
    file_knowledge_service: FileKnowledgeService = Depends(_get_file_knowledge_service),
) -> Dict[str, Any]:
    """Get knowledge for a specific file.

    Returns the complete knowledge data structure for the specified file
    including imports, exports, classes, functions, and metadata.

    Args:
        file_path: Path to the file (URL-encoded)
    """
    knowledge = await file_knowledge_service.get_full_file_knowledge(file_path)
    if not knowledge:
        # Check if the file exists but hasn't been scanned
        overview = await file_knowledge_service.get_file_overview(file_path)
        if overview.exists:
            return {
                "knowledge": None,
                "file_exists": True,
                "message": f"File exists but has not been scanned. Use POST /api/knowledge/files/scout to scan it.",
            }
        raise HTTPException(status_code=404, detail=f"No knowledge found for file: {file_path}")

    return {"knowledge": knowledge}


@router.post("/scout", response_model=WorkflowStartResponse)
async def scout_file(
    request: FileScoutRequest,
    run_repo: RunRepository = Depends(get_run_repo),
    task_manager: TaskManager = Depends(get_task_manager),
) -> WorkflowStartResponse:
    """Scout a single file for knowledge extraction.

    Triggers a targeted scouting workflow for a specific file.
    This performs AI-powered analysis to extract detailed knowledge
    including imports, exports, classes, functions, and semantic summary.

    Args:
        request: FileScoutRequest containing the file path to scout
    """
    from portal.services.workflow_runner import run_file_scouting_workflow_sync

    run_id = str(uuid.uuid4())[:8]

    # Create run entry in database
    run_repo.create(run_id, workflow="file_scouting")

    # Submit to TaskManager for background execution
    task_manager.submit_task(
        func=run_file_scouting_workflow_sync,
        args=(run_id, request.file_path),
        kwargs={},
        name=f"File Scout: {request.file_path}",
        task_id=run_id,
        task_type="file_scout",
        metadata={"run_id": run_id, "file_path": request.file_path},
    )

    return WorkflowStartResponse(run_id=run_id, status="started")


@router.get("/{file_path:path}/history")
async def get_file_scan_history(
    file_path: str,
    limit: int = 10,
    file_knowledge_service: FileKnowledgeService = Depends(_get_file_knowledge_service),
) -> Dict[str, Any]:
    """Get scan history for a specific file.

    Returns a list of previous scan records for the file,
    including timestamps, duration, and status.

    Args:
        file_path: Path to the file (URL-encoded)
        limit: Maximum number of history records to return (default 10)
    """
    history = await file_knowledge_service.get_file_scan_history(file_path, limit)
    return {
        "file_path": file_path,
        "history": history,
        "count": len(history),
    }


@router.delete("/{file_path:path}")
async def delete_file_knowledge(
    file_path: str,
    file_knowledge_service: FileKnowledgeService = Depends(_get_file_knowledge_service),
) -> Dict[str, Any]:
    """Delete knowledge for a specific file.

    Removes all stored knowledge for the specified file.
    This does not affect scan history records.

    Args:
        file_path: Path to the file (URL-encoded)
    """
    success = await file_knowledge_service.clear_file_knowledge(file_path)
    if not success:
        raise HTTPException(status_code=404, detail=f"No knowledge found for file: {file_path}")

    return {
        "status": "deleted",
        "file_path": file_path,
        "message": f"Knowledge for '{file_path}' has been removed",
    }
