"""
Expert Selector: Intelligent expert selection based on request analysis.

Selects relevant experts by matching:
- Keywords in the request
- File paths mentioned or affected
- Topic areas

Uses the expert index for efficient matching.
"""
import fnmatch
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .knowledge_store import KnowledgeStore, ExpertIndex, ExpertIndexEntry
from .expert_loader import ExpertLoader, ExpertType

logger = logging.getLogger(__name__)


@dataclass
class ExpertMatch:
    """A matched expert with score."""
    name: str
    score: float
    match_reasons: list[str]


class ExpertSelector:
    """
    Selects relevant experts for a planning request.

    Usage:
        selector = ExpertSelector(project_root)

        # Select experts for a request
        experts = selector.select_experts("Add password reset to auth")
        # Returns: ["auth-domain", "fastapi", "structure"]

        # Select with file paths
        experts = selector.select_experts(
            "Fix bug in auth",
            paths=["src/api/auth.py"]
        )
    """

    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()
        self.knowledge_store = KnowledgeStore(project_root)
        self.expert_loader = ExpertLoader(project_root)

        # Load or build index
        self._index: Optional[ExpertIndex] = None

    def _ensure_index(self) -> ExpertIndex:
        """Ensure expert index is loaded or built."""
        if self._index:
            return self._index

        # Try to load existing index
        self._index = self.knowledge_store.load_index()

        if not self._index:
            # Build index from discovered experts
            self._index = self._build_index()
            self.knowledge_store.save_index(self._index)

        return self._index

    def _build_index(self) -> ExpertIndex:
        """Build expert index from discovered experts and knowledge."""
        from .knowledge_store import ExpertIndex, ExpertIndexEntry, ExpertTriggers

        index = ExpertIndex()
        experts = self.expert_loader.discover_experts()
        knowledge = self.knowledge_store.load()

        # Build entries from discovered experts
        for expert in experts:
            triggers = ExpertTriggers(
                keywords=self._extract_keywords_for_expert(expert, knowledge),
                paths=self._extract_paths_for_expert(expert, knowledge),
                topics=self._extract_topics_for_expert(expert),
            )

            # Weight based on type
            weight = 1.0
            if expert.expert_type == ExpertType.DOMAIN:
                weight = 0.9  # Domain experts are highly relevant
            elif expert.expert_type == ExpertType.MODULE:
                weight = 0.85

            index.experts.append(ExpertIndexEntry(
                name=expert.name,
                type=expert.expert_type.value,
                file=expert.name,
                triggers=triggers,
                weight=weight,
            ))

        # Build keyword map
        for entry in index.experts:
            for keyword in entry.triggers.keywords:
                if keyword not in index.keyword_map:
                    index.keyword_map[keyword] = []
                if entry.name not in index.keyword_map[keyword]:
                    index.keyword_map[keyword].append(entry.name)

        # Build path map from knowledge domains
        if knowledge:
            for domain in knowledge.domains:
                for file_path in domain.files:
                    if file_path not in index.path_map:
                        index.path_map[file_path] = []
                    # Find matching domain expert
                    domain_expert = f"{domain.name}-domain"
                    if any(e.name == domain_expert or e.name == domain.name for e in index.experts):
                        expert_name = domain_expert if any(e.name == domain_expert for e in index.experts) else domain.name
                        if expert_name not in index.path_map[file_path]:
                            index.path_map[file_path].append(expert_name)

        return index

    def _extract_keywords_for_expert(self, expert, knowledge) -> list[str]:
        """Extract keywords for an expert."""
        keywords = []

        # From expert's domain_keywords
        if expert.domain_keywords:
            keywords.extend(expert.domain_keywords)

        # From expert name
        name_words = re.split(r"[-_]", expert.name.lower())
        keywords.extend(name_words)

        # From knowledge domains
        if knowledge:
            for domain in knowledge.domains:
                if domain.name.lower() in expert.name.lower():
                    keywords.extend(domain.keywords)

        # Tech-specific keywords
        tech_keywords = {
            "python": ["py", "pip", "pytest", "pydantic", "typing"],
            "typescript": ["ts", "tsx", "tsc", "interface", "type"],
            "javascript": ["js", "jsx", "node", "npm"],
            "react": ["component", "hook", "jsx", "tsx", "usestate", "useeffect"],
            "fastapi": ["api", "endpoint", "route", "router", "pydantic"],
            "django": ["model", "view", "template", "admin", "orm"],
            "docker": ["container", "dockerfile", "compose", "image"],
        }

        for tech, kws in tech_keywords.items():
            if tech in expert.name.lower():
                keywords.extend(kws)

        return list(set(k.lower() for k in keywords))

    def _extract_paths_for_expert(self, expert, knowledge) -> list[str]:
        """Extract file path patterns for an expert."""
        patterns = []

        # From module_path
        if expert.module_path:
            patterns.append(f"{expert.module_path}/**")

        # From expert name (guess common patterns)
        name = expert.name.lower()
        patterns.append(f"**/*{name}*")

        # Domain-specific patterns
        if expert.expert_type == ExpertType.DOMAIN:
            for kw in expert.domain_keywords:
                patterns.append(f"**/*{kw}*")

        # From knowledge
        if knowledge:
            for domain in knowledge.domains:
                if domain.name.lower() in name:
                    patterns.extend(domain.files)

        return patterns

    def _extract_topics_for_expert(self, expert) -> list[str]:
        """Extract topic areas for an expert."""
        topics = []

        # From description
        if expert.description:
            # Extract key phrases
            words = expert.description.lower().split()
            topics.extend(words)

        # Domain topics
        domain_topics = {
            "auth": ["authentication", "authorization", "security", "login", "session"],
            "payment": ["billing", "subscription", "invoice", "stripe", "checkout"],
            "user": ["account", "profile", "registration", "password"],
            "api": ["rest", "endpoint", "http", "request", "response"],
            "database": ["sql", "query", "orm", "migration", "schema"],
            "test": ["testing", "unittest", "pytest", "mock", "fixture"],
        }

        for key, ts in domain_topics.items():
            if key in expert.name.lower():
                topics.extend(ts)

        return list(set(topics))

    def select_experts(
        self,
        request: str,
        paths: Optional[list[str]] = None,
        max_experts: int = 3,
    ) -> list[str]:
        """
        Select most relevant experts for a request.

        Args:
            request: User's planning request
            paths: Optional list of file paths involved
            max_experts: Maximum number of experts to return

        Returns:
            List of expert names ordered by relevance
        """
        index = self._ensure_index()
        matches: dict[str, ExpertMatch] = {}

        request_lower = request.lower()
        request_words = set(re.findall(r"\w+", request_lower))

        # Score by keyword matches
        for entry in index.experts:
            score = 0.0
            reasons = []

            # Check keywords
            for keyword in entry.triggers.keywords:
                if keyword in request_lower:
                    score += entry.weight * 0.5
                    reasons.append(f"keyword:{keyword}")
                # Partial match in words
                elif any(keyword in word for word in request_words):
                    score += entry.weight * 0.2
                    reasons.append(f"partial:{keyword}")

            # Check topics
            for topic in entry.triggers.topics:
                if topic in request_lower:
                    score += entry.weight * 0.3
                    reasons.append(f"topic:{topic}")

            if score > 0:
                matches[entry.name] = ExpertMatch(
                    name=entry.name,
                    score=score,
                    match_reasons=reasons,
                )

        # Score by path matches
        if paths:
            for path in paths:
                # Direct path match
                if path in index.path_map:
                    for expert_name in index.path_map[path]:
                        if expert_name in matches:
                            matches[expert_name].score += 0.5
                            matches[expert_name].match_reasons.append(f"path:{path}")
                        else:
                            matches[expert_name] = ExpertMatch(
                                name=expert_name,
                                score=0.5,
                                match_reasons=[f"path:{path}"],
                            )

                # Pattern match
                for entry in index.experts:
                    for pattern in entry.triggers.paths:
                        if fnmatch.fnmatch(path, pattern):
                            if entry.name in matches:
                                matches[entry.name].score += 0.3
                                matches[entry.name].match_reasons.append(f"pattern:{pattern}")
                            else:
                                matches[entry.name] = ExpertMatch(
                                    name=entry.name,
                                    score=0.3,
                                    match_reasons=[f"pattern:{pattern}"],
                                )

        # Always include structure expert if available for significant requests
        if len(request_words) > 5:  # Non-trivial request
            for entry in index.experts:
                if "structure" in entry.name.lower():
                    if entry.name not in matches:
                        matches[entry.name] = ExpertMatch(
                            name=entry.name,
                            score=0.2,
                            match_reasons=["default:structure"],
                        )
                    break

        # Sort by score and return top N
        sorted_matches = sorted(
            matches.values(),
            key=lambda m: m.score,
            reverse=True
        )

        return [m.name for m in sorted_matches[:max_experts]]

    def get_expert_context(self, expert_names: list[str]) -> str:
        """
        Get planning context from selected experts.

        Args:
            expert_names: List of expert names to gather context from

        Returns:
            Formatted string with expert guidance
        """
        contexts = []

        for name in expert_names:
            expert = self.expert_loader.get_expert(name)
            if not expert:
                continue

            # Extract planning-relevant sections from expert
            guidance = self._extract_planning_guidance(expert)
            if guidance:
                contexts.append(f"### {name}\n{guidance}")

        return "\n\n".join(contexts)

    def _extract_planning_guidance(self, agent) -> str:
        """Extract planning-relevant guidance from an expert agent."""
        # The agent's system_prompt contains the expert's knowledge
        prompt = agent.system_prompt if hasattr(agent, "system_prompt") else ""

        if not prompt:
            return ""

        # Look for specific sections
        sections = []

        # Focus Areas section
        focus_match = re.search(
            r"## Focus Areas\s*(.*?)(?=##|\Z)",
            prompt,
            re.DOTALL | re.IGNORECASE
        )
        if focus_match:
            focus = focus_match.group(1).strip()
            if focus:
                sections.append(f"Focus: {focus[:500]}")

        # Key Practices section
        practices_match = re.search(
            r"## Key Practices\s*(.*?)(?=##|\Z)",
            prompt,
            re.DOTALL | re.IGNORECASE
        )
        if practices_match:
            practices = practices_match.group(1).strip()
            if practices:
                sections.append(f"Practices: {practices[:500]}")

        # Planning Guidance section (for domain experts)
        planning_match = re.search(
            r"## Planning Guidance\s*(.*?)(?=##|\Z)",
            prompt,
            re.DOTALL | re.IGNORECASE
        )
        if planning_match:
            planning = planning_match.group(1).strip()
            if planning:
                sections.append(f"Guidance: {planning[:500]}")

        # Conventions section
        conventions_match = re.search(
            r"## Conventions\s*(.*?)(?=##|\Z)",
            prompt,
            re.DOTALL | re.IGNORECASE
        )
        if conventions_match:
            conventions = conventions_match.group(1).strip()
            if conventions:
                sections.append(f"Conventions: {conventions[:300]}")

        if not sections:
            # Fallback: first paragraph after the title
            para_match = re.search(r"^#[^\n]+\n\n([^\n]+)", prompt, re.MULTILINE)
            if para_match:
                return para_match.group(1)[:200]

        return "\n".join(sections)

    def rebuild_index(self) -> bool:
        """Force rebuild of the expert index."""
        try:
            self._index = self._build_index()
            return self.knowledge_store.save_index(self._index)
        except Exception as e:
            logger.error(f"Failed to rebuild expert index: {e}")
            return False
