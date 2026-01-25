"""
Repository for expert definition CRUD operations.

This module provides database access for expert definitions that replace
the .orchestrator/agents/experts/*.md files.
"""
import json
from typing import Optional, List
from sqlalchemy import select

from .base import BaseRepository
from db.models import ExpertDefinition


class ExpertDefinitionRepository(BaseRepository):
    """Repository for managing expert definitions in database."""

    model = ExpertDefinition
    table_name = "expert_definitions"

    JSON_FIELDS = ["domain_keywords", "trigger_keywords", "trigger_paths", "trigger_topics"]

    def get_by_name(self, name: str) -> Optional[ExpertDefinition]:
        """Get expert definition by name."""
        with self.session() as session:
            stmt = select(ExpertDefinition).where(ExpertDefinition.name == name)
            expert = session.execute(stmt).scalar_one_or_none()
            if expert:
                session.expunge(expert)  # Detach from session to allow access after close
            return expert

    def list_all(self) -> List[ExpertDefinition]:
        """List all expert definitions."""
        with self.session() as session:
            stmt = select(ExpertDefinition).order_by(ExpertDefinition.name)
            experts = list(session.execute(stmt).scalars())
            for expert in experts:
                session.expunge(expert)  # Detach from session
            return experts

    def list_by_type(self, expert_type: str) -> List[ExpertDefinition]:
        """List experts by type (tech, domain, module)."""
        with self.session() as session:
            stmt = select(ExpertDefinition).where(
                ExpertDefinition.expert_type == expert_type
            ).order_by(ExpertDefinition.name)
            experts = list(session.execute(stmt).scalars())
            for expert in experts:
                session.expunge(expert)
            return experts

    def list_by_category(self, category: str) -> List[ExpertDefinition]:
        """List experts by category (language, framework, tool, general)."""
        with self.session() as session:
            stmt = select(ExpertDefinition).where(
                ExpertDefinition.category == category
            ).order_by(ExpertDefinition.name)
            experts = list(session.execute(stmt).scalars())
            for expert in experts:
                session.expunge(expert)
            return experts

    def find_by_keywords(self, keywords: List[str]) -> List[ExpertDefinition]:
        """Find experts matching any of the given keywords."""
        all_experts = self.list_all()
        matched = []
        keywords_lower = [k.lower() for k in keywords]

        for expert in all_experts:
            domain_keywords = json.loads(expert.domain_keywords_json or "[]")
            trigger_keywords = json.loads(expert.trigger_keywords_json or "[]")
            all_kw = [k.lower() for k in domain_keywords + trigger_keywords]

            if any(kw in all_kw for kw in keywords_lower):
                matched.append(expert)

        return matched

    def exists(self, name: str) -> bool:
        """Check if expert exists."""
        return self.get_by_name(name) is not None

    def create(
        self,
        name: str,
        system_prompt: str,
        description: str = None,
        expert_type: str = "tech",
        category: str = "general",
        domain_keywords: List[str] = None,
        module_path: str = None,
        trigger_keywords: List[str] = None,
        trigger_paths: List[str] = None,
        trigger_topics: List[str] = None,
        weight: float = 1.0,
        version: str = "1.0",
    ) -> ExpertDefinition:
        """Create a new expert definition."""
        with self.session() as session:
            expert = ExpertDefinition(
                name=name,
                version=version,
                description=description,
                expert_type=expert_type,
                category=category,
                system_prompt=system_prompt,
                domain_keywords_json=json.dumps(domain_keywords or []),
                module_path=module_path,
                trigger_keywords_json=json.dumps(trigger_keywords or []),
                trigger_paths_json=json.dumps(trigger_paths or []),
                trigger_topics_json=json.dumps(trigger_topics or []),
                weight=weight,
            )
            session.add(expert)
            session.commit()
            session.refresh(expert)
            return expert

    def update(self, name: str, **updates) -> Optional[ExpertDefinition]:
        """Update an expert definition."""
        with self.session() as session:
            stmt = select(ExpertDefinition).where(ExpertDefinition.name == name)
            expert = session.execute(stmt).scalar_one_or_none()
            if not expert:
                return None

            # Handle JSON fields
            json_fields = ['domain_keywords', 'trigger_keywords', 'trigger_paths', 'trigger_topics']
            for field in json_fields:
                if field in updates:
                    updates[f'{field}_json'] = json.dumps(updates.pop(field))

            for key, value in updates.items():
                if hasattr(expert, key):
                    setattr(expert, key, value)

            session.commit()
            session.refresh(expert)
            return expert

    def delete(self, name: str) -> bool:
        """Delete an expert definition."""
        with self.session() as session:
            stmt = select(ExpertDefinition).where(ExpertDefinition.name == name)
            expert = session.execute(stmt).scalar_one_or_none()
            if expert:
                session.delete(expert)
                session.commit()
                return True
            return False

    def to_dict(self, expert: ExpertDefinition) -> dict:
        """Convert expert definition to dictionary."""
        return {
            "id": expert.id,
            "name": expert.name,
            "version": expert.version,
            "description": expert.description,
            "expert_type": expert.expert_type,
            "category": expert.category,
            "module_path": expert.module_path,
            "domain_keywords": json.loads(expert.domain_keywords_json or "[]"),
            "system_prompt": expert.system_prompt,
            "weight": expert.weight,
            "trigger_keywords": json.loads(expert.trigger_keywords_json or "[]"),
            "trigger_paths": json.loads(expert.trigger_paths_json or "[]"),
            "trigger_topics": json.loads(expert.trigger_topics_json or "[]"),
            "created_at": expert.created_at.isoformat() if expert.created_at else None,
            "updated_at": expert.updated_at.isoformat() if expert.updated_at else None,
        }


# Singleton instance
_repository: Optional[ExpertDefinitionRepository] = None


def get_expert_definition_repository() -> ExpertDefinitionRepository:
    """Get singleton repository instance."""
    global _repository
    if _repository is None:
        _repository = ExpertDefinitionRepository()
    return _repository
