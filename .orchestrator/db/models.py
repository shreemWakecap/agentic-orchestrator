"""
SQLAlchemy ORM Models for PostgreSQL.
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
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()


class Plan(Base):
    """Plan model - represents a development plan."""
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True)
    plan_id = Column(String(255), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    status = Column(String(50), default="pending", index=True)
    priority = Column(Integer, default=0)
    tags_json = Column(Text)  # JSON array of tags
    metadata_json = Column(Text)  # JSON object for extra data
    file_path = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    steps = relationship("PlanStep", back_populates="plan", cascade="all, delete-orphan")
    build_states = relationship("BuildState", back_populates="plan", cascade="all, delete-orphan")


class PlanStep(Base):
    """Plan step model - individual steps within a plan."""
    __tablename__ = "plan_steps"

    id = Column(Integer, primary_key=True)
    plan_id = Column(String(255), ForeignKey("plans.plan_id", ondelete="CASCADE"), nullable=False, index=True)
    step_number = Column(Integer, nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    status = Column(String(50), default="pending")
    files_json = Column(Text)  # JSON array of files
    dependencies_json = Column(Text)  # JSON array of dependencies
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    plan = relationship("Plan", back_populates="steps")


class BuildState(Base):
    """Build state model - tracks build progress."""
    __tablename__ = "build_states"

    id = Column(Integer, primary_key=True)
    plan_id = Column(String(255), ForeignKey("plans.plan_id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(50), default="pending", index=True)
    current_step = Column(Integer, default=0)
    total_steps = Column(Integer, default=0)
    progress_json = Column(Text)  # JSON object for progress details
    error_message = Column(Text)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    plan = relationship("Plan", back_populates="build_states")


class Run(Base):
    """Run model - tracks workflow runs."""
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True)
    run_id = Column(String(255), unique=True, nullable=False, index=True)
    plan_id = Column(String(255), index=True)
    workflow_type = Column(String(50), nullable=False)  # plan, build, sync
    status = Column(String(50), default="pending", index=True)
    input_json = Column(Text)
    output_json = Column(Text)
    error_message = Column(Text)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration_seconds = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)


class Cost(Base):
    """Cost model - tracks API usage costs."""
    __tablename__ = "costs"

    id = Column(Integer, primary_key=True)
    run_id = Column(String(255), index=True)
    plan_id = Column(String(255), index=True)
    model = Column(String(100))
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)


class Knowledge(Base):
    """Knowledge model - stores codebase knowledge."""
    __tablename__ = "knowledge"

    id = Column(Integer, primary_key=True)
    key = Column(String(255), unique=True, nullable=False, index=True)
    category = Column(String(100), index=True)
    content = Column(Text, nullable=False)
    metadata_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FileKnowledge(Base):
    """File knowledge model - stores analyzed file information."""
    __tablename__ = "file_knowledge"

    id = Column(Integer, primary_key=True)
    file_path = Column(Text, unique=True, nullable=False, index=True)
    file_type = Column(String(50))
    language = Column(String(50), index=True)
    size_bytes = Column(Integer, default=0)
    line_count = Column(Integer, default=0)
    imports_json = Column(Text)
    exports_json = Column(Text)
    classes_json = Column(Text)
    functions_json = Column(Text)
    dependencies_json = Column(Text)
    metadata_json = Column(Text)
    summary = Column(Text)
    last_scanned = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Question(Base):
    """Question model - stores codebase exploration questions."""
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True)
    question_id = Column(String(255), unique=True, nullable=False, index=True)
    question = Column(Text, nullable=False)
    context = Column(Text)
    status = Column(String(50), default="pending", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    answers = relationship("Answer", back_populates="question", cascade="all, delete-orphan")


class Answer(Base):
    """Answer model - stores answers to questions."""
    __tablename__ = "answers"

    id = Column(Integer, primary_key=True)
    question_id = Column(String(255), ForeignKey("questions.question_id", ondelete="CASCADE"), nullable=False, index=True)
    answer = Column(Text, nullable=False)
    confidence = Column(Float, default=0.0)
    sources_json = Column(Text)  # JSON array of source references
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    question = relationship("Question", back_populates="answers")


def create_all_tables(engine):
    """Create all tables in the database."""
    Base.metadata.create_all(engine)


def drop_all_tables(engine):
    """Drop all tables from the database."""
    Base.metadata.drop_all(engine)
