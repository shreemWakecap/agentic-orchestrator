"""Expert content API routes."""
from typing import Dict, Any
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException

from portal.dependencies import get_project_root

router = APIRouter(prefix="/api/experts", tags=["experts"])


def _estimate_token_count(text: str) -> int:
    """Estimate token count for text content.

    Uses a simple heuristic: ~4 characters per token on average.
    This approximation works reasonably well for English text and code.

    Args:
        text: The text content to estimate tokens for.

    Returns:
        Estimated number of tokens.
    """
    if not text:
        return 0
    # Average of ~4 characters per token is a reasonable approximation
    # for mixed content (prose + code)
    return len(text) // 4


def _parse_expert_frontmatter(content: str) -> Dict[str, Any]:
    """Parse YAML frontmatter from expert markdown file.

    Args:
        content: Full file content including frontmatter.

    Returns:
        Dictionary with parsed metadata fields.
    """
    metadata = {
        "name": "",
        "description": "",
        "expert_type": "tech",
        "domain_keywords": [],
        "module_path": None,
    }

    if not content.startswith("---"):
        return metadata

    parts = content.split("---", 2)
    if len(parts) < 3:
        return metadata

    frontmatter = parts[1]
    for line in frontmatter.split("\n"):
        line = line.strip()
        if line.startswith("name:"):
            metadata["name"] = line.split(":", 1)[1].strip()
        elif line.startswith("description:"):
            metadata["description"] = line.split(":", 1)[1].strip()
        elif line.startswith("expert_type:"):
            metadata["expert_type"] = line.split(":", 1)[1].strip()
        elif line.startswith("module_path:"):
            metadata["module_path"] = line.split(":", 1)[1].strip()
        elif line.startswith("domain_keywords:"):
            kw_str = line.split(":", 1)[1].strip()
            if kw_str.startswith("[") and kw_str.endswith("]"):
                metadata["domain_keywords"] = [k.strip() for k in kw_str[1:-1].split(",")]

    return metadata


@router.get("/{expert_name}")
async def get_expert_content(
    expert_name: str,
    project_root: Path = Depends(get_project_root),
) -> Dict[str, Any]:
    """Get expert markdown content and metadata.

    Returns the full content of an expert markdown file along with
    parsed metadata and estimated token count.

    Args:
        expert_name: Name of the expert (without .md extension)

    Returns:
        Dictionary containing:
        - content: Full markdown content of the expert file
        - metadata: Parsed frontmatter (name, description, expert_type, etc.)
        - token_count: Estimated token count for the content
    """
    experts_dir = project_root / ".orchestrator" / "agents" / "experts"
    expert_file = experts_dir / f"{expert_name}.md"

    if not expert_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Expert not found: {expert_name}"
        )

    try:
        content = expert_file.read_text(encoding="utf-8")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read expert file: {str(e)}"
        )

    metadata = _parse_expert_frontmatter(content)

    # Use filename as name if not in frontmatter
    if not metadata["name"]:
        metadata["name"] = expert_name

    return {
        "content": content,
        "metadata": metadata,
        "token_count": _estimate_token_count(content),
    }
