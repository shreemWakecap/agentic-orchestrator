"""Pydantic response models for knowledge management endpoints."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class TechnologyResponse(BaseModel):
    """Technology detection result."""
    name: str
    category: str
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0-1")
    version: Optional[str] = None
    files: List[str] = Field(default_factory=list, description="Files where detected")

    class Config:
        from_attributes = True


class DomainResponse(BaseModel):
    """Domain/business area information."""
    name: str
    keywords: List[str] = Field(default_factory=list)
    files: List[str] = Field(default_factory=list)
    description: Optional[str] = None

    class Config:
        from_attributes = True


class ModuleResponse(BaseModel):
    """Module/component information."""
    name: str
    path: str
    purpose: Optional[str] = None
    dependencies: List[str] = Field(default_factory=list)
    exports: List[str] = Field(default_factory=list)

    class Config:
        from_attributes = True


class ScanMetaResponse(BaseModel):
    """Metadata about a knowledge scan operation."""
    scan_id: str
    timestamp: str
    duration: float = Field(description="Scan duration in seconds")
    files_scanned: int
    scan_type: str = Field(description="Type: full, incremental, targeted")
    status: str = "completed"
    errors: List[str] = Field(default_factory=list)

    class Config:
        from_attributes = True


class ExpertTriggerResponse(BaseModel):
    """Expert trigger definition."""
    pattern: str
    weight: float = 1.0
    description: Optional[str] = None


class ExpertResponse(BaseModel):
    """Expert agent information."""
    name: str
    triggers: List[ExpertTriggerResponse] = Field(default_factory=list)
    description: Optional[str] = None
    capabilities: List[str] = Field(default_factory=list)

    class Config:
        from_attributes = True


class ExpertIndexResponse(BaseModel):
    """Index of available experts with their triggers."""
    experts: List[ExpertResponse] = Field(default_factory=list)
    total_count: int = 0
    last_updated: Optional[str] = None

    class Config:
        from_attributes = True


class ArchitectureSummaryResponse(BaseModel):
    """Architecture summary information."""
    patterns: List[str] = Field(default_factory=list)
    layers: List[str] = Field(default_factory=list)
    entry_points: List[str] = Field(default_factory=list)
    description: Optional[str] = None


class KnowledgeOverviewResponse(BaseModel):
    """Overview of project knowledge for dashboard."""
    project: str
    technologies: List[TechnologyResponse] = Field(default_factory=list)
    architecture_summary: Optional[ArchitectureSummaryResponse] = None
    last_scan: Optional[ScanMetaResponse] = None
    domains_count: int = 0
    modules_count: int = 0
    files_indexed: int = 0

    class Config:
        from_attributes = True


class KnowledgeDetailResponse(BaseModel):
    """Full knowledge detail response."""
    project: str
    technologies: List[TechnologyResponse] = Field(default_factory=list)
    domains: List[DomainResponse] = Field(default_factory=list)
    modules: List[ModuleResponse] = Field(default_factory=list)
    architecture_summary: Optional[ArchitectureSummaryResponse] = None
    expert_index: Optional[ExpertIndexResponse] = None
    scan_history: List[ScanMetaResponse] = Field(default_factory=list)
    last_scan: Optional[ScanMetaResponse] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True


class ScoutRequestResponse(BaseModel):
    """Response for scout request submission."""
    request_id: str
    status: str = "queued"
    scan_type: str
    targets: List[str] = Field(default_factory=list)
    message: Optional[str] = None


class ScoutStatusResponse(BaseModel):
    """Status of a scouting operation."""
    request_id: str
    status: str
    progress: float = Field(ge=0.0, le=100.0, default=0.0)
    files_processed: int = 0
    files_total: int = 0
    current_target: Optional[str] = None
    errors: List[str] = Field(default_factory=list)
    result: Optional[KnowledgeOverviewResponse] = None
