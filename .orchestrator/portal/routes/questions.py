"""Codebase Exploration API routes.

Refactored from Questions & Answers to serve as a codebase exploration tool.
Provides endpoints for exploring architecture, files, patterns, and domains
to help users understand the codebase before planning features or changes.
"""
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Path as PathParam
from pathlib import Path

from db import KnowledgeRepository, FileKnowledgeRepository
from portal.dependencies import (
    get_knowledge_repo,
    get_file_knowledge_repo,
    get_project_root,
)
from portal.schemas.requests import (
    ExploreCodebaseRequest,
    ExplorationResultResponse,
    ExplorationListResponse,
    ExplorationHistoryResponse,
    FileReference,
    CodeSnippet,
    RelatedTopic,
)
from portal.services.question_service import CodebaseExplorerService

router = APIRouter(prefix="/api/explore", tags=["exploration"])


def _get_explorer_service(
    knowledge_repo: KnowledgeRepository = Depends(get_knowledge_repo),
    file_knowledge_repo: FileKnowledgeRepository = Depends(get_file_knowledge_repo),
    project_root: Path = Depends(get_project_root),
) -> CodebaseExplorerService:
    """Get codebase explorer service with injected dependencies."""
    return CodebaseExplorerService(
        knowledge_repo=knowledge_repo,
        file_knowledge_repo=file_knowledge_repo,
        project_root=project_root,
    )


# --- Exploration Endpoints ---

@router.post("", response_model=ExplorationResultResponse)
async def explore_codebase(
    request: ExploreCodebaseRequest,
    explorer_service: CodebaseExplorerService = Depends(_get_explorer_service),
) -> ExplorationResultResponse:
    """Explore the codebase to find relevant information.

    Use this endpoint to ask questions about the codebase and get answers
    with relevant code snippets, file references, and explanations.
    Helps inform decision-making during feature planning and development.

    Request:
        - query: The exploration query/question about the codebase
        - scope: Optional scope ('architecture', 'files', 'patterns', 'dependencies', 'all')
        - include_snippets: Whether to include code snippets (default: True)
        - max_results: Maximum number of results (1-50, default: 10)
    """
    exploration = await explorer_service.explore(
        query=request.query,
        scope=request.scope or "all",
        max_results=request.max_results or 10,
        include_code=request.include_snippets if request.include_snippets is not None else True,
    )

    # Convert to response model
    file_references = []
    code_snippets = []
    related_topics = []
    sources_used = set()

    for result in exploration.results:
        # Build file references
        if result.file_path:
            file_references.append(FileReference(
                file_path=result.file_path,
                description=result.description or result.title,
                file_type=result.match_type,
                relevance=f"Matched on {result.match_type} - score: {result.relevance_score:.2f}",
            ))

        # Build code snippets from results with code
        if result.code_snippet:
            code_snippets.append(CodeSnippet(
                file_path=result.file_path,
                start_line=result.line_number,
                end_line=result.line_number + 10,  # Approximate
                content=result.code_snippet,
                language=result.context.get("language", "unknown"),
                relevance_score=result.relevance_score,
            ))

        # Track sources
        sources_used.add(result.match_type)

    # Build related topics from suggestions
    for suggestion in exploration.suggestions:
        related_topics.append(RelatedTopic(
            topic=suggestion.split(":")[0] if ":" in suggestion else suggestion,
            description=suggestion,
            suggested_query=suggestion.split(":")[1].strip() if ":" in suggestion else None,
        ))

    return ExplorationResultResponse(
        id=f"explore_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        query=exploration.query,
        scope=exploration.scope,
        explanation=exploration.context_summary or f"Found {exploration.total_results} results",
        file_references=file_references[:request.max_results or 10],
        code_snippets=code_snippets[:5],  # Limit snippets
        related_topics=related_topics,
        confidence=0.8 if exploration.total_results > 0 else 0.2,
        sources_used=list(sources_used),
        created_at=datetime.utcnow().isoformat(),
    )


@router.get("/architecture")
async def get_architecture_overview(
    explorer_service: CodebaseExplorerService = Depends(_get_explorer_service),
) -> Dict[str, Any]:
    """Get high-level architecture overview of the codebase.

    Returns information about:
    - Project name and type
    - Primary language and technologies
    - Architecture pattern
    - Modules and their dependencies
    - Domains and their scope
    - Coding conventions
    """
    overview = await explorer_service.get_architecture_overview()

    return {
        "project": {
            "name": overview.project_name,
            "type": overview.project_type,
            "primary_language": overview.primary_language,
            "architecture_pattern": overview.architecture_pattern,
        },
        "modules": overview.modules,
        "domains": overview.domains,
        "entry_points": overview.entry_points,
        "conventions": overview.conventions,
        "technologies": overview.technologies,
    }


@router.get("/file/{file_path:path}")
async def get_file_analysis(
    file_path: str = PathParam(..., description="Path to the file to analyze"),
    explorer_service: CodebaseExplorerService = Depends(_get_explorer_service),
) -> Dict[str, Any]:
    """Get detailed analysis of a specific file.

    Returns comprehensive information about the file including:
    - File metadata (size, lines, language)
    - Imports and exports
    - Classes and functions defined
    - Dependencies
    - Domain and module context
    - Related files
    """
    analysis = await explorer_service.get_file_analysis(file_path)

    if not analysis.exists and not analysis.has_knowledge:
        raise HTTPException(
            status_code=404,
            detail=f"File not found and no knowledge available: {file_path}"
        )

    return {
        "file_path": analysis.file_path,
        "file_name": analysis.file_name,
        "exists": analysis.exists,
        "has_knowledge": analysis.has_knowledge,
        "metadata": {
            "language": analysis.language,
            "size_bytes": analysis.size_bytes,
            "line_count": analysis.line_count,
        },
        "structure": {
            "imports": analysis.imports,
            "exports": analysis.exports,
            "classes": analysis.classes,
            "functions": analysis.functions,
        },
        "dependencies": analysis.dependencies,
        "context": {
            "domain": analysis.domain_context,
            "module": analysis.module_context,
        },
        "related_files": analysis.related_files,
    }


@router.get("/patterns")
async def search_patterns(
    keyword: str = Query(..., min_length=1, description="Keyword/pattern to search for"),
    max_results: int = Query(50, ge=1, le=100, description="Maximum results per category"),
    explorer_service: CodebaseExplorerService = Depends(_get_explorer_service),
) -> Dict[str, Any]:
    """Search for patterns and keywords across the codebase.

    Searches in:
    - File names
    - Class names
    - Function names
    - Import statements

    Use this to find where specific patterns, naming conventions,
    or technologies are used throughout the codebase.
    """
    result = await explorer_service.search_patterns(keyword, max_results)

    return {
        "keyword": result.keyword,
        "total_matches": result.total_matches,
        "matches": {
            "files": result.file_matches,
            "classes": result.class_matches,
            "functions": result.function_matches,
            "imports": result.import_matches,
        },
    }


@router.get("/domains")
async def list_domains(
    explorer_service: CodebaseExplorerService = Depends(_get_explorer_service),
) -> Dict[str, Any]:
    """List all domains identified in the codebase.

    Returns a list of business/technical domains with their
    associated keywords and file counts.
    """
    overview = await explorer_service.get_architecture_overview()

    return {
        "domains": overview.domains,
        "total": len(overview.domains),
    }


@router.get("/domains/{domain_name}")
async def get_domain_info(
    domain_name: str = PathParam(..., description="Domain name or keyword"),
    explorer_service: CodebaseExplorerService = Depends(_get_explorer_service),
) -> Dict[str, Any]:
    """Get detailed information about a specific domain.

    Returns:
    - Keywords associated with the domain
    - Files belonging to the domain
    - Models and routes in the domain
    - Naming conventions
    - Common imports
    """
    info = await explorer_service.get_domain_info(domain_name)

    if not info.files and not info.keywords:
        raise HTTPException(
            status_code=404,
            detail=f"Domain not found: {domain_name}"
        )

    return {
        "domain_name": info.domain_name,
        "keywords": info.keywords,
        "files": info.files,
        "models": info.models,
        "routes": info.routes,
        "patterns": {
            "naming_conventions": info.naming_conventions,
            "structure_patterns": info.structure_patterns,
        },
        "common_imports": info.common_imports,
    }


@router.get("/stats")
async def get_exploration_stats(
    explorer_service: CodebaseExplorerService = Depends(_get_explorer_service),
) -> Dict[str, Any]:
    """Get statistics about the indexed codebase knowledge.

    Returns counts and summaries useful for understanding
    what knowledge is available for exploration.
    """
    data = await explorer_service.get_exploration_data_for_template()

    return {
        "knowledge_available": data["stats"]["has_knowledge"],
        "total_files_indexed": data["stats"]["total_files"],
        "architecture": data["architecture"],
    }


@router.get("/suggestions")
async def get_exploration_suggestions(
    context: Optional[str] = Query(None, description="Context to base suggestions on"),
    explorer_service: CodebaseExplorerService = Depends(_get_explorer_service),
) -> Dict[str, Any]:
    """Get suggestions for what to explore.

    Returns suggested queries based on the codebase structure
    to help users discover important areas of the code.
    """
    overview = await explorer_service.get_architecture_overview()

    suggestions = []

    # Suggest exploring modules
    for module in overview.modules[:5]:
        suggestions.append({
            "query": f"How does the {module.get('name', 'module')} module work?",
            "category": "modules",
            "description": module.get("purpose", "Explore module structure"),
        })

    # Suggest exploring domains
    for domain in overview.domains[:5]:
        suggestions.append({
            "query": f"What files handle {domain.get('name', 'domain')}?",
            "category": "domains",
            "description": f"Files related to {domain.get('name', 'this domain')}",
        })

    # Add general suggestions
    suggestions.extend([
        {
            "query": "What are the main entry points?",
            "category": "architecture",
            "description": "Understand how the application starts",
        },
        {
            "query": "What patterns are used in this codebase?",
            "category": "patterns",
            "description": "Learn about coding conventions and patterns",
        },
        {
            "query": "What are the external dependencies?",
            "category": "dependencies",
            "description": "Understand third-party integrations",
        },
    ])

    return {
        "suggestions": suggestions,
        "total": len(suggestions),
    }
