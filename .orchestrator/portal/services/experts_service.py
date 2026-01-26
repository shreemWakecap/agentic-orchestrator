"""Experts service for business logic related to expert agents."""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.expert_loader import ExpertLoader, ExpertInfo


@dataclass
class ExpertContent:
    """Expert file content with metadata."""
    name: str
    content: str
    description: str
    expert_type: str
    category: str
    token_estimate: int
    module_path: Optional[str] = None
    domain_keywords: list[str] = None

    def __post_init__(self):
        if self.domain_keywords is None:
            self.domain_keywords = []


class ExpertsService:
    """Service for expert-related business logic.

    Encapsulates expert discovery, content retrieval, and token estimation
    for the portal layer.
    """

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.expert_loader = ExpertLoader(project_root)

    async def get_expert_content(self, name: str) -> Optional[ExpertContent]:
        """Get expert markdown content and metadata.

        Args:
            name: Expert name (filename without .md extension)

        Returns:
            ExpertContent with markdown content and metadata, or None if not found
        """
        # Discover all experts to find metadata
        experts = self.expert_loader.discover_experts()
        expert_info: Optional[ExpertInfo] = None

        for expert in experts:
            if expert.name.lower() == name.lower():
                expert_info = expert
                break

        if not expert_info:
            return None

        # Read the expert content from database
        content = self.expert_loader.get_expert_content(expert_info.name)
        if not content:
            return None

        # Estimate tokens for the content
        token_estimate = self.estimate_tokens(content)

        return ExpertContent(
            name=expert_info.name,
            content=content,
            description=expert_info.description,
            expert_type=expert_info.expert_type.value,
            category=expert_info.category,
            token_estimate=token_estimate,
            module_path=expert_info.module_path,
            domain_keywords=expert_info.domain_keywords,
        )

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count using 4 chars/token heuristic.

        This is a rough approximation. Actual tokenization varies by model
        and content type, but 4 characters per token is a reasonable
        average for English text and code.

        Args:
            text: Text content to estimate tokens for

        Returns:
            Estimated token count
        """
        if not text:
            return 0
        return len(text) // 4

    async def list_experts(self) -> list[dict]:
        """List all available experts with basic info.

        Returns:
            List of expert dictionaries with name, description, type, category
        """
        experts = self.expert_loader.discover_experts()
        return [
            {
                "name": expert.name,
                "description": expert.description,
                "expert_type": expert.expert_type.value,
                "category": expert.category,
                "file_name": expert.name,
            }
            for expert in experts
        ]
