"""Knowledge service for business logic related to codebase knowledge."""
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from db import KnowledgeRepository


@dataclass
class KnowledgeOverview:
    """Summary of current knowledge state."""
    has_knowledge: bool = False
    has_expert_index: bool = False
    project_name: str = ""
    project_type: str = ""
    primary_language: str = ""
    last_updated: str = ""
    languages_count: int = 0
    frameworks_count: int = 0
    tools_count: int = 0
    modules_count: int = 0
    domains_count: int = 0
    last_scan: Optional[Dict] = None


class KnowledgeService:
    """Service for knowledge-related business logic.

    Encapsulates knowledge data retrieval and transformation logic
    for the portal layer.
    """

    def __init__(self, knowledge_repo: KnowledgeRepository):
        self.knowledge_repo = knowledge_repo

    async def get_knowledge_overview(self) -> KnowledgeOverview:
        """Get summary of current knowledge.

        Returns a lightweight overview of the knowledge state
        including counts and basic project info.
        """
        overview = KnowledgeOverview()

        # Check if knowledge exists
        overview.has_knowledge = self.knowledge_repo.exists()
        overview.has_expert_index = self.knowledge_repo.has_expert_index()

        if not overview.has_knowledge:
            return overview

        # Load full knowledge for summary
        knowledge_data = self.knowledge_repo.load_knowledge()
        if not knowledge_data:
            return overview

        # Extract project info
        project = knowledge_data.get("project", {})
        overview.project_name = project.get("name", "")
        overview.project_type = project.get("type", "unknown")
        overview.primary_language = project.get("primary_language", "")
        overview.last_updated = knowledge_data.get("last_updated", "")

        # Extract counts
        technologies = knowledge_data.get("technologies", {})
        overview.languages_count = len(technologies.get("languages", []))
        overview.frameworks_count = len(technologies.get("frameworks", []))
        overview.tools_count = len(technologies.get("tools", []))

        architecture = knowledge_data.get("architecture", {})
        overview.modules_count = len(architecture.get("modules", []))

        overview.domains_count = len(knowledge_data.get("domains", []))

        # Get last scan info
        scan_meta = self.knowledge_repo.load_scan_meta()
        if scan_meta:
            overview.last_scan = {
                "scan_id": scan_meta.get("scan_id", ""),
                "started_at": scan_meta.get("started_at", ""),
                "completed_at": scan_meta.get("completed_at", ""),
                "files_scanned": scan_meta.get("files_scanned", 0),
                "scan_type": scan_meta.get("scan_type", "full"),
            }

        return overview

    async def get_full_knowledge(self) -> Optional[Dict]:
        """Get complete codebase knowledge.

        Returns the full knowledge data structure including
        project info, technologies, architecture, domains, and patterns.
        """
        if not self.knowledge_repo.exists():
            return None

        return self.knowledge_repo.load_knowledge()

    async def get_expert_index(self) -> Optional[Dict]:
        """Get expert index for intelligent agent selection.

        Returns the expert index including experts list,
        keyword mappings, and path mappings.
        """
        if not self.knowledge_repo.has_expert_index():
            return None

        return self.knowledge_repo.load_expert_index()

    async def get_scan_history(self) -> Optional[Dict]:
        """Get scan metadata and history.

        Returns metadata about the most recent scan including
        scan ID, timestamps, files scanned, and generated experts.
        """
        scan_meta = self.knowledge_repo.load_scan_meta()
        if not scan_meta:
            return None

        # Transform to clean dict
        return {
            "scan_id": scan_meta.get("scan_id", ""),
            "started_at": scan_meta.get("started_at", ""),
            "completed_at": scan_meta.get("completed_at", ""),
            "duration_seconds": scan_meta.get("duration_seconds", 0),
            "files_scanned": scan_meta.get("files_scanned", 0),
            "scan_type": scan_meta.get("scan_type", "full"),
            "trigger": scan_meta.get("trigger_type", "manual"),
            "experts_generated": scan_meta.get("experts_generated", []),
        }

    async def clear_knowledge(self) -> bool:
        """Clear all knowledge data.

        Removes all codebase knowledge from the database.
        Returns True if successful.
        """
        try:
            self.knowledge_repo.clear()
            return True
        except Exception:
            return False

    async def get_knowledge_for_template(self) -> Optional[Dict]:
        """Get knowledge data transformed for template rendering.

        Calls get_full_knowledge() and get_expert_index(), then transforms
        the nested data structure into a flat dict matching template expectations.

        Returns a dict with:
            - project_name: str
            - project_type: str
            - primary_language: str
            - last_scan: str (formatted)
            - architecture_pattern: str
            - languages: list[dict] with name, confidence
            - frameworks: list[dict] with name, confidence
            - tools: list[dict] with name, confidence
            - modules: list[dict] with name, path, purpose
            - domains: list[dict] with name, keywords, file_count
            - experts: list[dict] with name, description, triggers (flattened)
        """
        knowledge_data = await self.get_full_knowledge()
        if not knowledge_data:
            return None

        # Extract project info
        project = knowledge_data.get("project", {})
        technologies = knowledge_data.get("technologies", {})
        architecture = knowledge_data.get("architecture", {})
        domains_data = knowledge_data.get("domains", [])

        # Get last scan timestamp
        scan_meta = self.knowledge_repo.load_scan_meta()
        last_scan = ""
        if scan_meta:
            last_scan = scan_meta.get("completed_at", "") or scan_meta.get("started_at", "")

        # Transform languages
        languages = [
            {"name": lang.get("name", ""), "confidence": lang.get("confidence", 0.0)}
            for lang in technologies.get("languages", [])
        ]

        # Transform frameworks
        frameworks = [
            {"name": fw.get("name", ""), "confidence": fw.get("confidence", 0.0)}
            for fw in technologies.get("frameworks", [])
        ]

        # Transform tools
        tools = [
            {"name": tool.get("name", ""), "confidence": tool.get("confidence", 0.0)}
            for tool in technologies.get("tools", [])
        ]

        # Transform modules
        modules = [
            {
                "name": mod.get("name", ""),
                "path": mod.get("path", ""),
                "purpose": mod.get("purpose", ""),
            }
            for mod in architecture.get("modules", [])
        ]

        # Transform domains with file_count computed from files length
        domains = [
            {
                "name": domain.get("name", ""),
                "keywords": domain.get("keywords", []),
                "file_count": len(domain.get("files", [])),
            }
            for domain in domains_data
        ]

        # Get expert index and transform experts
        experts = []
        expert_index = await self.get_expert_index()
        if expert_index:
            for expert in expert_index.get("experts", []):
                # Build description from type
                expert_type = expert.get("type", "")
                description = f"{expert_type.replace('_', ' ').title()} Expert" if expert_type else ""

                # Flatten triggers: combine keywords, paths, and topics into a single list
                triggers_data = expert.get("triggers", {})
                flattened_triggers = []
                flattened_triggers.extend(triggers_data.get("keywords", []))
                flattened_triggers.extend(triggers_data.get("paths", []))
                flattened_triggers.extend(triggers_data.get("topics", []))

                experts.append({
                    "name": expert.get("name", ""),
                    "description": description,
                    "triggers": flattened_triggers,
                })

        return {
            "project_name": project.get("name", ""),
            "project_type": project.get("type", "unknown"),
            "primary_language": project.get("primary_language", ""),
            "last_scan": last_scan,
            "architecture_pattern": architecture.get("pattern", "unknown"),
            "languages": languages,
            "frameworks": frameworks,
            "tools": tools,
            "modules": modules,
            "domains": domains,
            "experts": experts,
        }
