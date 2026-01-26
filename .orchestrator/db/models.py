"""
SQLAlchemy ORM Models for PostgreSQL.

This module defines all database tables required by the orchestrator.
Tables are auto-created on startup via Base.metadata.create_all().

Multi-Project Support:
    Most tables include a project_id foreign key for multi-project isolation.
    The Project model is the root entity that owns all project-specific data.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
    Enum as SQLEnum,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import enum

Base = declarative_base()


# =============================================================================
# PROJECT MANAGEMENT (Multi-Project Support)
# =============================================================================

class ProjectStatus(str, enum.Enum):
    """Project lifecycle status."""
    PENDING = "pending"
    INDEXING = "indexing"
    READY = "ready"
    ACTIVE = "active"
    ARCHIVED = "archived"


class ProjectSourceType(str, enum.Enum):
    """Project source type."""
    LOCAL = "local"
    GIT = "git"


class Project(Base):
    """
    Project model - root entity for multi-project support.

    Each project owns its own plans, builds, knowledge, and other data.
    Projects are isolated from each other in the shared database.
    """
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    project_id = Column(String(36), unique=True, nullable=False, index=True)  # UUID
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    path = Column(Text, nullable=False)  # Path to project directory
    description = Column(Text)

    # Status
    status = Column(SQLEnum(ProjectStatus), default=ProjectStatus.PENDING, index=True)

    # Source info
    source_type = Column(SQLEnum(ProjectSourceType), default=ProjectSourceType.LOCAL)
    git_url = Column(String(500))
    git_branch = Column(String(255))

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_accessed_at = Column(DateTime)
    indexed_at = Column(DateTime)
    archived_at = Column(DateTime)

    # Relationships
    events = relationship("ProjectEvent", back_populates="project", cascade="all, delete-orphan")
    plans = relationship("Plan", back_populates="project", cascade="all, delete-orphan")
    runs = relationship("ActiveRun", back_populates="project", cascade="all, delete-orphan")
    knowledge = relationship("CodebaseKnowledge", back_populates="project", cascade="all, delete-orphan", uselist=False)
    cost_history = relationship("CostHistory", back_populates="project", cascade="all, delete-orphan")
    token_usage = relationship("TokenUsageRecord", back_populates="project", cascade="all, delete-orphan")
    expert_index = relationship("ExpertIndex", back_populates="project", cascade="all, delete-orphan", uselist=False)
    scan_metadata = relationship("ScanMetadata", back_populates="project", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "name": self.name,
            "slug": self.slug,
            "path": self.path,
            "description": self.description,
            "status": self.status.value if self.status else None,
            "source_type": self.source_type.value if self.source_type else None,
            "git_url": self.git_url,
            "git_branch": self.git_branch,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_accessed_at": self.last_accessed_at.isoformat() if self.last_accessed_at else None,
            "indexed_at": self.indexed_at.isoformat() if self.indexed_at else None,
        }


class ProjectEvent(Base):
    """
    Project event model - audit log for project changes.

    Tracks important events like creation, status changes, indexing, etc.
    """
    __tablename__ = "project_events"

    id = Column(Integer, primary_key=True)
    project_id = Column(String(36), ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)  # created, activated, indexed, archived, etc.
    event_data_json = Column(Text, default="{}")
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    triggered_by = Column(String(100))  # cli, portal, system

    # Relationships
    project = relationship("Project", back_populates="events")


# =============================================================================
# PLANS AND STEPS
# =============================================================================

class Plan(Base):
    """Plan model - represents a development plan."""
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True)
    plan_id = Column(String(255), unique=True, nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.project_id", ondelete="CASCADE"), index=True)  # Multi-project support
    goal = Column(Text)
    request = Column(Text)
    raw_content = Column(Text)
    context_json = Column(Text, default="[]")
    verify_json = Column(Text, default="[]")
    status = Column(String(50), default="pending", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime)

    # Relationships
    project = relationship("Project", back_populates="plans")
    phases = relationship("PlanPhase", back_populates="plan", cascade="all, delete-orphan")
    steps = relationship("PlanStep", back_populates="plan", cascade="all, delete-orphan")
    build_state = relationship("BuildState", back_populates="plan", cascade="all, delete-orphan", uselist=False)
    task_mappings = relationship("TaskMapping", back_populates="plan", cascade="all, delete-orphan")


class PlanPhase(Base):
    """Plan phase model - groups steps into phases."""
    __tablename__ = "plan_phases"

    id = Column(Integer, primary_key=True)
    plan_id = Column(String(255), ForeignKey("plans.plan_id", ondelete="CASCADE"), nullable=False, index=True)
    phase_id = Column(String(255), nullable=False)
    name = Column(String(500))
    phase_number = Column(Integer, default=0)
    can_parallelize = Column(Boolean, default=False)

    # Relationships
    plan = relationship("Plan", back_populates="phases")


class PlanStep(Base):
    """Plan step model - individual steps within a plan."""
    __tablename__ = "plan_steps"

    id = Column(Integer, primary_key=True)
    plan_id = Column(String(255), ForeignKey("plans.plan_id", ondelete="CASCADE"), nullable=False, index=True)
    phase_id = Column(String(255))
    step_id = Column(String(255), nullable=False)
    action = Column(String(255))
    target = Column(Text)
    description = Column(Text)
    done = Column(Text)
    inputs_json = Column(Text, default="[]")
    needs_json = Column(Text, default="[]")
    step_order = Column(Integer, default=0)

    # Relationships
    plan = relationship("Plan", back_populates="steps")


# =============================================================================
# BUILD STATE AND STEP STATE
# =============================================================================

class BuildState(Base):
    """Build state model - tracks build progress."""
    __tablename__ = "build_states"

    id = Column(Integer, primary_key=True)
    plan_id = Column(String(255), ForeignKey("plans.plan_id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    status = Column(String(50), default="pending", index=True)
    current_step = Column(String(255))
    current_phase = Column(Integer, default=0)
    total_steps = Column(Integer, default=0)
    last_error = Column(Text)
    execution_mode = Column(String(50), default="sequential")
    current_wave_index = Column(Integer, default=0)
    completed_steps_json = Column(Text, default="[]")
    failed_steps_json = Column(Text, default="[]")
    skipped_steps_json = Column(Text, default="[]")
    files_created_json = Column(Text, default="[]")
    files_modified_json = Column(Text, default="[]")
    started_at = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime)

    # Relationships
    plan = relationship("Plan", back_populates="build_state")
    step_states = relationship("StepState", back_populates="build_state", cascade="all, delete-orphan")


class StepState(Base):
    """Step state model - tracks individual step execution state."""
    __tablename__ = "step_states"

    id = Column(Integer, primary_key=True)
    plan_id = Column(String(255), ForeignKey("build_states.plan_id", ondelete="CASCADE"), nullable=False, index=True)
    step_id = Column(String(255), nullable=False, index=True)
    status = Column(String(50), default="pending")
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    retry_count = Column(Integer, default=0)
    error = Column(Text)
    files_affected_json = Column(Text, default="[]")
    summary = Column(Text)
    full_output = Column(Text)
    retry_history_json = Column(Text, default="[]")

    # Task integration fields (Claude Native Task Tools)
    task_session_id = Column(String(255), index=True)  # Which Claude session
    task_id_in_session = Column(String(50))            # Task ID like "1", "2"
    task_owner = Column(String(100))                   # For future parallel execution
    blocked_by_steps_json = Column(Text, default="[]") # Step IDs this depends on
    blocks_steps_json = Column(Text, default="[]")     # Step IDs that depend on this

    __table_args__ = (
        UniqueConstraint('plan_id', 'step_id', name='uq_step_states_plan_step'),
    )

    # Relationships
    build_state = relationship("BuildState", back_populates="step_states")


# =============================================================================
# TASK MAPPING (Claude Native Task Tools Integration)
# =============================================================================

class TaskMapping(Base):
    """
    Maps Claude Task IDs to PlanStep IDs for session persistence.

    Enables:
    - Resume from crash (recreate Tasks from DB state)
    - Multi-session continuity
    - Portal progress tracking
    """
    __tablename__ = "task_mappings"

    id = Column(Integer, primary_key=True)
    plan_id = Column(String(255), ForeignKey("plans.plan_id", ondelete="CASCADE"),
                     nullable=False, index=True)
    step_id = Column(String(255), nullable=False, index=True)

    # Task metadata (for reconstruction)
    task_subject = Column(String(500), nullable=False)
    task_description = Column(Text)
    task_active_form = Column(String(255))

    # Dependency info (stored for reconstruction)
    blocked_by_json = Column(Text, default="[]")  # List of step_ids
    blocks_json = Column(Text, default="[]")      # List of step_ids

    # Session tracking
    session_id = Column(String(255), index=True)  # UUID of the Claude session
    session_task_id = Column(String(50))          # Task ID within that session

    # Status tracking (synced from Tasks)
    status = Column(String(50), default="pending", index=True)  # pending/in_progress/completed

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    synced_at = Column(DateTime)  # Last sync from Task state

    __table_args__ = (
        UniqueConstraint('plan_id', 'step_id', name='uq_task_mapping_plan_step'),
        Index('ix_task_mapping_session', 'session_id'),
    )

    # Relationships
    plan = relationship("Plan", back_populates="task_mappings")

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        import json
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "step_id": self.step_id,
            "task_subject": self.task_subject,
            "task_description": self.task_description,
            "task_active_form": self.task_active_form,
            "blocked_by": json.loads(self.blocked_by_json or "[]"),
            "blocks": json.loads(self.blocks_json or "[]"),
            "session_id": self.session_id,
            "session_task_id": self.session_task_id,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "synced_at": self.synced_at.isoformat() if self.synced_at else None,
        }


class GoalVerificationState(Base):
    """Goal verification state model - tracks goal completion."""
    __tablename__ = "goal_verification_state"

    id = Column(Integer, primary_key=True)
    plan_id = Column(String(255), unique=True, nullable=False, index=True)
    goal = Column(Text, default="")
    original_request = Column(Text, default="")
    verification_attempt = Column(Integer, default=0)
    missing_items_json = Column(Text, default="[]")
    completion_percentage = Column(Integer, default=0)
    goal_achieved = Column(Boolean, default=False)
    context_notes_json = Column(Text, default="[]")
    verify_commands_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# =============================================================================
# ACTIVE RUNS AND EVENTS
# =============================================================================

class ActiveRun(Base):
    """Active run model - tracks running workflows."""
    __tablename__ = "active_runs"

    id = Column(Integer, primary_key=True)
    run_id = Column(String(255), unique=True, nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.project_id", ondelete="CASCADE"), index=True)  # Multi-project support
    workflow = Column(String(50), nullable=False)
    status = Column(String(50), default="pending", index=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    plan_id = Column(String(255), index=True)
    plan_path = Column(Text)
    description = Column(Text)
    progress = Column(Integer, default=0)
    error = Column(Text)
    data_json = Column(Text, default="{}")
    triggered_by = Column(String(50), default="manual")  # manual, system, auto_pre_planning, post_build

    # Relationships
    project = relationship("Project", back_populates="runs")
    events = relationship("RunEvent", back_populates="run", cascade="all, delete-orphan")


class RunEvent(Base):
    """Run event model - events during workflow execution."""
    __tablename__ = "run_events"

    id = Column(Integer, primary_key=True)
    run_id = Column(String(255), ForeignKey("active_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    data_json = Column(Text, default="{}")

    # Relationships
    run = relationship("ActiveRun", back_populates="events")


# =============================================================================
# COST TRACKING
# =============================================================================

class CostHistory(Base):
    """Cost history model - tracks API usage costs."""
    __tablename__ = "cost_history"

    id = Column(Integer, primary_key=True)
    project_id = Column(String(36), ForeignKey("projects.project_id", ondelete="CASCADE"), index=True)  # Multi-project support
    workflow = Column(String(50), nullable=False, index=True)
    run_id = Column(String(255), index=True)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    total_tokens = Column(Integer, default=0)
    estimated_cost = Column(Float, default=0.0)
    actual_cost = Column(Float)
    agents_json = Column(Text, default="{}")

    # Relationships
    project = relationship("Project", back_populates="cost_history")


# =============================================================================
# TOKEN USAGE TRACKING
# =============================================================================

class TokenUsageRecord(Base):
    """Token usage record model - tracks individual token usage events."""
    __tablename__ = "token_usage_records"

    id = Column(Integer, primary_key=True)
    project_id = Column(String(36), ForeignKey("projects.project_id", ondelete="CASCADE"), index=True)  # Multi-project support
    run_id = Column(String(255), ForeignKey("active_runs.run_id", ondelete="SET NULL"), index=True)
    plan_id = Column(String(255), ForeignKey("plans.plan_id", ondelete="SET NULL"), index=True)
    workflow_type = Column(String(100), nullable=False, index=True)  # scout, build, plan, etc.
    event_type = Column(String(50), nullable=False, index=True)  # execution, estimation
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    model = Column(String(255), index=True)
    cost_usd = Column(Float, default=0.0)
    estimated_tokens = Column(Integer)  # For estimation events - predicted token count
    estimated_cost_usd = Column(Float)  # For estimation events - predicted cost
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    metadata_json = Column(Text, default="{}")

    __table_args__ = (
        Index('ix_token_usage_workflow_timestamp', 'workflow_type', 'timestamp'),
        Index('ix_token_usage_event_timestamp', 'event_type', 'timestamp'),
        Index('ix_token_usage_project_timestamp', 'project_id', 'timestamp'),
    )

    # Relationships
    project = relationship("Project", back_populates="token_usage")
    run = relationship("ActiveRun", backref="token_usage_records")
    plan = relationship("Plan", backref="token_usage_records")


# =============================================================================
# CODEBASE KNOWLEDGE
# =============================================================================

class CodebaseKnowledge(Base):
    """Codebase knowledge model - stores project analysis results."""
    __tablename__ = "codebase_knowledge"

    id = Column(Integer, primary_key=True)
    project_id = Column(String(36), ForeignKey("projects.project_id", ondelete="CASCADE"), unique=True, index=True)  # Multi-project support
    version = Column(String(50), default="1.0")
    last_updated = Column(DateTime, default=datetime.utcnow)
    project_name = Column(String(255))
    project_type = Column(String(100))
    primary_language = Column(String(100))
    statistics_json = Column(Text, default="{}")

    # Relationships
    project = relationship("Project", back_populates="knowledge")
    technologies = relationship("Technology", back_populates="knowledge", cascade="all, delete-orphan")
    architecture = relationship("ArchitectureInfo", back_populates="knowledge", cascade="all, delete-orphan", uselist=False)
    modules = relationship("ArchitectureModule", back_populates="knowledge", cascade="all, delete-orphan")
    domains = relationship("Domain", back_populates="knowledge", cascade="all, delete-orphan")
    patterns = relationship("Pattern", back_populates="knowledge", cascade="all, delete-orphan", uselist=False)


class Technology(Base):
    """Technology model - languages, frameworks, tools."""
    __tablename__ = "technologies"

    id = Column(Integer, primary_key=True)
    knowledge_id = Column(Integer, ForeignKey("codebase_knowledge.id", ondelete="CASCADE"), nullable=False, index=True)
    tech_type = Column(String(50), nullable=False)  # language, framework, tool
    name = Column(String(255), nullable=False)
    confidence = Column(Float, default=0.0)
    version = Column(String(100))
    entry_point = Column(Text)
    config_file = Column(Text)

    # Relationships
    knowledge = relationship("CodebaseKnowledge", back_populates="technologies")


class ArchitectureInfo(Base):
    """Architecture info model - overall architecture pattern."""
    __tablename__ = "architecture_info"

    id = Column(Integer, primary_key=True)
    knowledge_id = Column(Integer, ForeignKey("codebase_knowledge.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    pattern = Column(String(100), default="unknown")
    entry_points_json = Column(Text, default="[]")

    # Relationships
    knowledge = relationship("CodebaseKnowledge", back_populates="architecture")


class ArchitectureModule(Base):
    """Architecture module model - code modules."""
    __tablename__ = "architecture_modules"

    id = Column(Integer, primary_key=True)
    knowledge_id = Column(Integer, ForeignKey("codebase_knowledge.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    path = Column(Text)
    purpose = Column(Text)
    depends_on_json = Column(Text, default="[]")

    # Relationships
    knowledge = relationship("CodebaseKnowledge", back_populates="modules")


class Domain(Base):
    """Domain model - business/feature domains."""
    __tablename__ = "domains"

    id = Column(Integer, primary_key=True)
    knowledge_id = Column(Integer, ForeignKey("codebase_knowledge.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    keywords_json = Column(Text, default="[]")
    files_json = Column(Text, default="[]")
    models_json = Column(Text, default="[]")
    routes_json = Column(Text, default="[]")

    # Relationships
    knowledge = relationship("CodebaseKnowledge", back_populates="domains")


class Pattern(Base):
    """Pattern model - coding conventions and patterns."""
    __tablename__ = "patterns"

    id = Column(Integer, primary_key=True)
    knowledge_id = Column(Integer, ForeignKey("codebase_knowledge.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    naming_json = Column(Text, default="{}")
    structure_json = Column(Text, default="{}")
    conventions_json = Column(Text, default="[]")

    # Relationships
    knowledge = relationship("CodebaseKnowledge", back_populates="patterns")


# =============================================================================
# EXPERT INDEX
# =============================================================================

class ExpertIndex(Base):
    """Expert index model - index of available experts."""
    __tablename__ = "expert_index"

    id = Column(Integer, primary_key=True)
    project_id = Column(String(36), ForeignKey("projects.project_id", ondelete="CASCADE"), unique=True, index=True)  # Multi-project support
    version = Column(String(50), default="1.0")
    last_updated = Column(DateTime, default=datetime.utcnow)
    keyword_map_json = Column(Text, default="{}")
    path_map_json = Column(Text, default="{}")

    # Relationships
    project = relationship("Project", back_populates="expert_index")
    entries = relationship("ExpertEntry", back_populates="index", cascade="all, delete-orphan")


class ExpertEntry(Base):
    """Expert entry model - individual expert records."""
    __tablename__ = "expert_entries"

    id = Column(Integer, primary_key=True)
    index_id = Column(Integer, ForeignKey("expert_index.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    expert_type = Column(String(50))
    file_path = Column(Text)
    weight = Column(Float, default=1.0)
    triggers_keywords_json = Column(Text, default="[]")
    triggers_paths_json = Column(Text, default="[]")
    triggers_topics_json = Column(Text, default="[]")

    # Relationships
    index = relationship("ExpertIndex", back_populates="entries")


# =============================================================================
# SCAN METADATA
# =============================================================================

class ScanMetadata(Base):
    """Scan metadata model - tracks codebase scans."""
    __tablename__ = "scan_metadata"

    id = Column(Integer, primary_key=True)
    project_id = Column(String(36), ForeignKey("projects.project_id", ondelete="CASCADE"), index=True)  # Multi-project support
    scan_id = Column(String(255), unique=True, nullable=False, index=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    duration_seconds = Column(Float, default=0)
    files_scanned = Column(Integer, default=0)
    scan_type = Column(String(50), default="full")
    trigger_type = Column(String(50), default="manual")
    experts_generated_json = Column(Text, default="[]")

    # Relationships
    project = relationship("Project", back_populates="scan_metadata")


class ExtendedScanMetadata(Base):
    """Extended scan metadata with git state tracking for staleness detection."""
    __tablename__ = "extended_scan_metadata"

    id = Column(Integer, primary_key=True)
    project_id = Column(String(36), ForeignKey("projects.project_id", ondelete="CASCADE"), index=True)  # Multi-project support
    git_commit_hash = Column(String(64), index=True)
    git_branch = Column(String(255))
    scanned_paths_json = Column(Text, default="[]")
    trigger_type = Column(String(50), default="manual")  # manual, auto, post_build
    scan_time = Column(DateTime, default=datetime.utcnow, index=True)
    scan_mode = Column(String(50), default="full")  # full, incremental


# =============================================================================
# CODING RULES
# =============================================================================

class CodingRule(Base):
    """Coding rule model - stores extracted coding rules for enforcement."""
    __tablename__ = "coding_rules"

    id = Column(Integer, primary_key=True)
    project_id = Column(String(36), ForeignKey("projects.project_id", ondelete="CASCADE"), index=True)  # Multi-project support
    knowledge_id = Column(Integer, ForeignKey("codebase_knowledge.id", ondelete="CASCADE"), index=True)
    rule_id = Column(String(255), nullable=False, index=True)
    category = Column(String(50), nullable=False, index=True)  # naming, structure, patterns, security, testing, documentation
    rule_text = Column(Text, nullable=False)
    severity = Column(String(20), default="info", index=True)  # info, warning, error
    examples_json = Column(Text, default="[]")
    source_files_json = Column(Text, default="[]")
    confidence = Column(Float, default=0.5)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('project_id', 'rule_id', name='uq_coding_rules_project_rule'),
    )


# =============================================================================
# FILE KNOWLEDGE
# =============================================================================

class FileKnowledge(Base):
    """File knowledge model - stores analyzed file information."""
    __tablename__ = "file_knowledge"

    id = Column(Integer, primary_key=True)
    project_id = Column(String(36), ForeignKey("projects.project_id", ondelete="CASCADE"), index=True)  # Multi-project support
    file_path = Column(Text, nullable=False, index=True)
    file_type = Column(String(50))
    language = Column(String(50), index=True)
    size_bytes = Column(Integer, default=0)
    line_count = Column(Integer, default=0)
    imports_json = Column(Text, default="[]")
    exports_json = Column(Text, default="[]")
    classes_json = Column(Text, default="[]")
    functions_json = Column(Text, default="[]")
    dependencies_json = Column(Text, default="[]")
    metadata_json = Column(Text, default="{}")
    summary = Column(Text)
    last_scanned = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        UniqueConstraint('project_id', 'file_path', name='uq_file_knowledge_project_path'),
    )


class FileScanHistory(Base):
    """File scan history model - tracks individual file scans."""
    __tablename__ = "file_scan_history"

    id = Column(Integer, primary_key=True)
    project_id = Column(String(36), ForeignKey("projects.project_id", ondelete="CASCADE"), index=True)  # Multi-project support
    scan_id = Column(String(255), unique=True, nullable=False, index=True)
    file_path = Column(Text, nullable=False, index=True)
    scan_type = Column(String(50), default="single")
    trigger_type = Column(String(50), default="manual")
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    duration_seconds = Column(Float, default=0)
    status = Column(String(50), default="completed")
    error_message = Column(Text)
    knowledge_id = Column(Integer)


# =============================================================================
# AGENT AND EXPERT DEFINITIONS (Global - not project-specific)
# =============================================================================

class AgentDefinition(Base):
    """
    Stores agent system prompts and metadata.
    Replaces: .orchestrator/agents/*.md files
    """
    __tablename__ = "agent_definitions"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True, index=True)  # scout, builder, planner
    version = Column(String(20), default="1.0")

    # Metadata (from YAML frontmatter)
    description = Column(Text)
    tools_json = Column(Text, default="[]")  # ["Read", "Glob", "Grep", "Bash"]
    model = Column(String(50))  # sonnet, opus, etc.

    # System prompt content (markdown body)
    system_prompt = Column(Text, nullable=False)

    # Behavior settings
    is_agentic = Column(Boolean, default=False)  # Can write files
    output_markers_json = Column(Text, default="[]")  # Expected output markers

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ExpertDefinition(Base):
    """
    Stores expert prompts and trigger conditions.
    Replaces: .orchestrator/agents/experts/*.md files
    """
    __tablename__ = "expert_definitions"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True, index=True)  # python, fastapi
    version = Column(String(20), default="1.0")

    # Metadata (from YAML frontmatter)
    description = Column(Text)
    expert_type = Column(String(20), default="tech", index=True)  # tech, domain, module
    category = Column(String(50))  # language, framework, tool, general

    # Domain/Module specific
    module_path = Column(Text)  # For MODULE type experts
    domain_keywords_json = Column(Text, default="[]")  # ["auth", "login", "jwt"]

    # System prompt content
    system_prompt = Column(Text, nullable=False)

    # Triggering conditions
    weight = Column(Float, default=1.0)  # Priority weight
    trigger_keywords_json = Column(Text, default="[]")
    trigger_paths_json = Column(Text, default="[]")
    trigger_topics_json = Column(Text, default="[]")

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OrchestratorConfig(Base):
    """
    Stores orchestrator configuration as JSON.
    Replaces: .orchestrator/config/agent.json, budget.json
    """
    __tablename__ = "orchestrator_config"

    id = Column(Integer, primary_key=True)
    config_type = Column(String(50), nullable=False, unique=True, index=True)  # agent, budget

    # JSON configuration data
    config_data_json = Column(Text, nullable=False)

    # Version for tracking changes
    version = Column(Integer, default=1)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def create_all_tables(engine):
    """Create all tables in the database."""
    Base.metadata.create_all(engine)


def drop_all_tables(engine):
    """Drop all tables from the database."""
    Base.metadata.drop_all(engine)
