"""
Project API Routes for multi-project management.

Provides REST endpoints for managing projects:
- List/get projects
- Add local/git projects
- Activate/switch projects
- Archive/restore/remove projects
- Git operations (fetch, pull, status)
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

router = APIRouter(prefix="/api/projects", tags=["projects"])


# =============================================================================
# REQUEST/RESPONSE SCHEMAS
# =============================================================================

class AddLocalProjectRequest(BaseModel):
    """Request to add a local project."""
    path: str = Field(..., description="Path to local project directory")
    name: Optional[str] = Field(None, description="Project name (default: directory name)")
    description: Optional[str] = Field(None, description="Project description")
    auto_index: bool = Field(False, description="Run scout after adding")


class AddGitProjectRequest(BaseModel):
    """Request to add a git project."""
    url: str = Field(..., description="Git repository URL")
    destination: str = Field(..., description="Local destination path")
    branch: Optional[str] = Field(None, description="Branch to clone")
    name: Optional[str] = Field(None, description="Project name (default: from URL)")
    description: Optional[str] = Field(None, description="Project description")
    auto_index: bool = Field(False, description="Run scout after adding")


class ProjectResponse(BaseModel):
    """Project response model."""
    id: str
    name: str
    slug: str
    path: str
    status: str
    source_type: str
    git_url: Optional[str] = None
    git_branch: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[str] = None
    last_accessed_at: Optional[str] = None
    indexed_at: Optional[str] = None


class ProjectListResponse(BaseModel):
    """Project list response."""
    projects: List[ProjectResponse]
    active_project: Optional[str] = None
    total: int


class ProjectInfoResponse(BaseModel):
    """Detailed project info response."""
    project: ProjectResponse
    git_status: Optional[Dict[str, Any]] = None
    knowledge_exists: bool = False
    expert_count: int = 0


class GitOperationResponse(BaseModel):
    """Git operation response."""
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    changed_files: Optional[List[str]] = None


class MessageResponse(BaseModel):
    """Simple message response."""
    message: str
    success: bool = True


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _check_multi_project_mode():
    """Check if multi-project mode is enabled."""
    from config import get_config
    config = get_config()
    if not config.is_multi_project_mode:
        raise HTTPException(
            status_code=400,
            detail="Multi-project mode is not enabled. Set SDLC_ORCHESTRATOR_HOME and run 'orch init'."
        )


def _get_project_service():
    """Get the project service."""
    from core.project_service import get_project_service
    return get_project_service()


def _entry_to_response(entry) -> ProjectResponse:
    """Convert a project dict or object to ProjectResponse."""
    # Handle both dict (from repository) and object formats
    if isinstance(entry, dict):
        status = entry.get('status', 'unknown')
        source_type = entry.get('source_type', 'local')
        return ProjectResponse(
            id=entry.get('id'),
            name=entry.get('name'),
            slug=entry.get('slug'),
            path=entry.get('path'),
            status=status.value if hasattr(status, 'value') else str(status),
            source_type=source_type.value if hasattr(source_type, 'value') else str(source_type),
            git_url=entry.get('git_url'),
            git_branch=entry.get('git_branch'),
            description=entry.get('description'),
            created_at=entry.get('added_at'),
            last_accessed_at=entry.get('last_accessed'),
            indexed_at=entry.get('indexed_at'),
        )
    else:
        # Legacy object format
        return ProjectResponse(
            id=entry.id,
            name=entry.name,
            slug=entry.slug,
            path=entry.path,
            status=entry.status.value if hasattr(entry.status, 'value') else str(entry.status),
            source_type=entry.source_type.value if hasattr(entry.source_type, 'value') else str(entry.source_type),
            git_url=entry.git_url,
            git_branch=entry.git_branch,
            description=entry.description,
            created_at=entry.added_at,
            last_accessed_at=entry.last_accessed,
            indexed_at=entry.indexed_at,
        )


# =============================================================================
# ROUTES
# =============================================================================

@router.get("/", response_model=ProjectListResponse)
async def list_projects(include_archived: bool = False):
    """
    List all projects.

    Args:
        include_archived: Include archived projects in the list.

    Returns:
        List of projects with active project indicator.
    """
    _check_multi_project_mode()
    service = _get_project_service()

    projects = service.list_projects(include_archived=include_archived)
    active = service.get_active()

    return ProjectListResponse(
        projects=[_entry_to_response(p) for p in projects],
        active_project=active.get('slug') if isinstance(active, dict) else (active.slug if active else None),
        total=len(projects)
    )


@router.get("/active", response_model=Optional[ProjectResponse])
async def get_active_project():
    """Get the currently active project."""
    _check_multi_project_mode()
    service = _get_project_service()

    active = service.get_active()
    if not active:
        return None

    return _entry_to_response(active)


@router.get("/{slug_or_id}", response_model=ProjectInfoResponse)
async def get_project(slug_or_id: str):
    """
    Get detailed project information.

    Args:
        slug_or_id: Project slug or UUID.

    Returns:
        Detailed project info including git status and knowledge state.
    """
    _check_multi_project_mode()
    service = _get_project_service()

    info = service.get_info(slug_or_id)
    if not info:
        raise HTTPException(status_code=404, detail="Project not found")

    return ProjectInfoResponse(
        project=_entry_to_response(info.entry),
        git_status=info.git_status.to_dict() if info.git_status else None,
        knowledge_exists=info.knowledge_exists,
        expert_count=info.expert_count,
    )


@router.post("/local", response_model=ProjectResponse)
async def add_local_project(request: AddLocalProjectRequest, background_tasks: BackgroundTasks):
    """
    Add a local project.

    Args:
        request: Project details including path.

    Returns:
        The created project.
    """
    _check_multi_project_mode()
    service = _get_project_service()

    result = service.add_local(
        path=request.path,
        name=request.name,
        description=request.description,
        auto_index=request.auto_index,
    )

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    # TODO: If auto_index, trigger scout in background
    # if request.auto_index:
    #     background_tasks.add_task(run_scout, result.project.slug)

    return _entry_to_response(result.project)


@router.post("/git", response_model=ProjectResponse)
async def add_git_project(request: AddGitProjectRequest, background_tasks: BackgroundTasks):
    """
    Add a git project by cloning.

    Args:
        request: Git repository details.

    Returns:
        The created project.
    """
    _check_multi_project_mode()
    service = _get_project_service()

    result = service.add_git(
        url=request.url,
        destination=request.destination,
        name=request.name,
        branch=request.branch,
        description=request.description,
        auto_index=request.auto_index,
    )

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    return _entry_to_response(result.project)


@router.post("/{slug_or_id}/activate", response_model=ProjectResponse)
async def activate_project(slug_or_id: str):
    """
    Activate/switch to a project.

    Args:
        slug_or_id: Project slug or UUID.

    Returns:
        The activated project.
    """
    _check_multi_project_mode()
    service = _get_project_service()

    project = service.switch(slug_or_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return _entry_to_response(project)


@router.post("/{slug_or_id}/index", response_model=MessageResponse)
async def index_project(slug_or_id: str, background_tasks: BackgroundTasks):
    """
    Run scout/indexing for a project.

    Args:
        slug_or_id: Project slug or UUID.

    Returns:
        Success message.
    """
    _check_multi_project_mode()
    service = _get_project_service()

    project = service.repository.get_by_slug_or_id(slug_or_id, as_dict=True)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # TODO: Trigger scout workflow in background
    # background_tasks.add_task(run_scout, project['slug'])

    return MessageResponse(message=f"Indexing started for {project['name']}")


@router.post("/{slug_or_id}/archive", response_model=ProjectResponse)
async def archive_project(slug_or_id: str):
    """
    Archive a project.

    Args:
        slug_or_id: Project slug or UUID.

    Returns:
        The archived project.
    """
    _check_multi_project_mode()
    service = _get_project_service()

    project = service.archive(slug_or_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return _entry_to_response(project)


@router.post("/{slug_or_id}/restore", response_model=ProjectResponse)
async def restore_project(slug_or_id: str):
    """
    Restore an archived project.

    Args:
        slug_or_id: Project slug or UUID.

    Returns:
        The restored project.
    """
    _check_multi_project_mode()
    service = _get_project_service()

    project = service.restore(slug_or_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return _entry_to_response(project)


@router.delete("/{slug_or_id}", response_model=MessageResponse)
async def remove_project(slug_or_id: str, delete_files: bool = False):
    """
    Remove a project.

    Args:
        slug_or_id: Project slug or UUID.
        delete_files: Also delete the project files.

    Returns:
        Success message.
    """
    _check_multi_project_mode()
    service = _get_project_service()

    # Get project info before deletion
    project = service.repository.get_by_slug_or_id(slug_or_id, as_dict=True)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    name = project['name']
    success = service.remove(slug_or_id, delete_files=delete_files)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to remove project")

    return MessageResponse(message=f"Project '{name}' removed")


# =============================================================================
# GIT OPERATIONS
# =============================================================================

@router.get("/{slug_or_id}/git/status", response_model=Dict[str, Any])
async def get_git_status(slug_or_id: str):
    """
    Get git status for a project.

    Args:
        slug_or_id: Project slug or UUID.

    Returns:
        Git status information.
    """
    _check_multi_project_mode()
    service = _get_project_service()

    status = service.get_git_status(slug_or_id)
    if not status:
        raise HTTPException(status_code=404, detail="Project not found")

    if status.error:
        return {"error": status.error}

    return status.to_dict()


@router.post("/{slug_or_id}/git/fetch", response_model=GitOperationResponse)
async def git_fetch(slug_or_id: str):
    """
    Git fetch for a project.

    Args:
        slug_or_id: Project slug or UUID.

    Returns:
        Fetch operation result.
    """
    _check_multi_project_mode()
    service = _get_project_service()

    result = service.fetch(slug_or_id)
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")

    return GitOperationResponse(**result)


@router.post("/{slug_or_id}/git/pull", response_model=GitOperationResponse)
async def git_pull(slug_or_id: str):
    """
    Git pull for a project.

    Args:
        slug_or_id: Project slug or UUID.

    Returns:
        Pull operation result.
    """
    _check_multi_project_mode()
    service = _get_project_service()

    result = service.pull(slug_or_id)
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")

    return GitOperationResponse(**result)
