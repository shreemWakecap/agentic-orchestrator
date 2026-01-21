"""
SQLAlchemy ORM Models for PostgreSQL.

This module defines all database tables required by the orchestrator.
Tables are auto-created on startup via Base.metadata.create_all().
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
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()


# =============================================================================
# PLANS AND STEPS
# =============================================================================

class Plan(Base):
    """Plan model - represents a development plan."""
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True)
    plan_id = Column(String(255), unique=True, nullable=False, index=True)
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
    phases = relationship("PlanPhase", back_populates="plan", cascade="all, delete-orphan")
    steps = relationship("PlanStep", back_populates="plan", cascade="all, delete-orphan")
    build_state = relationship("BuildState", back_populates="plan", cascade="all, delete-orphan", uselist=False)


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

    __table_args__ = (
        UniqueConstraint('plan_id', 'step_id', name='uq_step_states_plan_step'),
    )

    # Relationships
    build_state = relationship("BuildState", back_populates="step_states")


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

    # Relationships
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
    workflow = Column(String(50), nullable=False, index=True)
    run_id = Column(String(255), index=True)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    total_tokens = Column(Integer, default=0)
    estimated_cost = Column(Float, default=0.0)
    actual_cost = Column(Float)
    agents_json = Column(Text, default="{}")


# =============================================================================
# CODEBASE KNOWLEDGE
# =============================================================================

class CodebaseKnowledge(Base):
    """Codebase knowledge model - stores project analysis results."""
    __tablename__ = "codebase_knowledge"

    id = Column(Integer, primary_key=True)
    version = Column(String(50), default="1.0")
    last_updated = Column(DateTime, default=datetime.utcnow)
    project_name = Column(String(255))
    project_type = Column(String(100))
    primary_language = Column(String(100))
    statistics_json = Column(Text, default="{}")

    # Relationships
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
    version = Column(String(50), default="1.0")
    last_updated = Column(DateTime, default=datetime.utcnow)
    keyword_map_json = Column(Text, default="{}")
    path_map_json = Column(Text, default="{}")

    # Relationships
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
    scan_id = Column(String(255), unique=True, nullable=False, index=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    duration_seconds = Column(Float, default=0)
    files_scanned = Column(Integer, default=0)
    scan_type = Column(String(50), default="full")
    trigger_type = Column(String(50), default="manual")
    experts_generated_json = Column(Text, default="[]")


class ExtendedScanMetadata(Base):
    """Extended scan metadata with git state tracking for staleness detection."""
    __tablename__ = "extended_scan_metadata"

    id = Column(Integer, primary_key=True)
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
    knowledge_id = Column(Integer, ForeignKey("codebase_knowledge.id", ondelete="CASCADE"), index=True)
    rule_id = Column(String(255), unique=True, nullable=False, index=True)
    category = Column(String(50), nullable=False, index=True)  # naming, structure, patterns, security, testing, documentation
    rule_text = Column(Text, nullable=False)
    severity = Column(String(20), default="info", index=True)  # info, warning, error
    examples_json = Column(Text, default="[]")
    source_files_json = Column(Text, default="[]")
    confidence = Column(Float, default=0.5)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# =============================================================================
# FILE KNOWLEDGE
# =============================================================================

class FileKnowledge(Base):
    """File knowledge model - stores analyzed file information."""
    __tablename__ = "file_knowledge"

    id = Column(Integer, primary_key=True)
    file_path = Column(Text, unique=True, nullable=False, index=True)
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


class FileScanHistory(Base):
    """File scan history model - tracks individual file scans."""
    __tablename__ = "file_scan_history"

    id = Column(Integer, primary_key=True)
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
# UTILITY FUNCTIONS
# =============================================================================

def create_all_tables(engine):
    """Create all tables in the database."""
    Base.metadata.create_all(engine)


def drop_all_tables(engine):
    """Drop all tables from the database."""
    Base.metadata.drop_all(engine)
