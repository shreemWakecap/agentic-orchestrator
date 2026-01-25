"""
Repository for agent definition CRUD operations.

This module provides database access for agent definitions that replace
the .orchestrator/agents/*.md files.
"""
import json
from typing import Optional, List
from sqlalchemy import select

from .base import BaseRepository
from db.models import AgentDefinition


class AgentDefinitionRepository(BaseRepository):
    """Repository for managing agent definitions in database."""

    model = AgentDefinition
    table_name = "agent_definitions"

    JSON_FIELDS = ["tools", "output_markers"]

    def get_by_name(self, name: str) -> Optional[AgentDefinition]:
        """Get agent definition by name."""
        with self.session() as session:
            stmt = select(AgentDefinition).where(AgentDefinition.name == name)
            agent = session.execute(stmt).scalar_one_or_none()
            if agent:
                session.expunge(agent)  # Detach from session to allow access after close
            return agent

    def list_all(self) -> List[AgentDefinition]:
        """List all agent definitions."""
        with self.session() as session:
            stmt = select(AgentDefinition).order_by(AgentDefinition.name)
            agents = list(session.execute(stmt).scalars())
            for agent in agents:
                session.expunge(agent)  # Detach from session
            return agents

    def exists(self, name: str) -> bool:
        """Check if agent exists."""
        return self.get_by_name(name) is not None

    def create(
        self,
        name: str,
        system_prompt: str,
        description: str = None,
        tools: List[str] = None,
        model: str = None,
        is_agentic: bool = False,
        output_markers: List[str] = None,
        version: str = "1.0",
    ) -> AgentDefinition:
        """Create a new agent definition."""
        with self.session() as session:
            agent = AgentDefinition(
                name=name,
                version=version,
                description=description,
                system_prompt=system_prompt,
                tools_json=json.dumps(tools or []),
                model=model,
                is_agentic=is_agentic,
                output_markers_json=json.dumps(output_markers or []),
            )
            session.add(agent)
            session.commit()
            session.refresh(agent)
            return agent

    def update(self, name: str, **updates) -> Optional[AgentDefinition]:
        """Update an agent definition."""
        with self.session() as session:
            stmt = select(AgentDefinition).where(AgentDefinition.name == name)
            agent = session.execute(stmt).scalar_one_or_none()
            if not agent:
                return None

            # Handle JSON fields
            if 'tools' in updates:
                updates['tools_json'] = json.dumps(updates.pop('tools'))
            if 'output_markers' in updates:
                updates['output_markers_json'] = json.dumps(updates.pop('output_markers'))

            for key, value in updates.items():
                if hasattr(agent, key):
                    setattr(agent, key, value)

            session.commit()
            session.refresh(agent)
            return agent

    def delete(self, name: str) -> bool:
        """Delete an agent definition."""
        with self.session() as session:
            stmt = select(AgentDefinition).where(AgentDefinition.name == name)
            agent = session.execute(stmt).scalar_one_or_none()
            if agent:
                session.delete(agent)
                session.commit()
                return True
            return False

    def to_dict(self, agent: AgentDefinition) -> dict:
        """Convert agent definition to dictionary."""
        return {
            "id": agent.id,
            "name": agent.name,
            "version": agent.version,
            "description": agent.description,
            "tools": json.loads(agent.tools_json or "[]"),
            "model": agent.model,
            "system_prompt": agent.system_prompt,
            "is_agentic": agent.is_agentic,
            "output_markers": json.loads(agent.output_markers_json or "[]"),
            "created_at": agent.created_at.isoformat() if agent.created_at else None,
            "updated_at": agent.updated_at.isoformat() if agent.updated_at else None,
        }


# Singleton instance
_repository: Optional[AgentDefinitionRepository] = None


def get_agent_definition_repository() -> AgentDefinitionRepository:
    """Get singleton repository instance."""
    global _repository
    if _repository is None:
        _repository = AgentDefinitionRepository()
    return _repository
