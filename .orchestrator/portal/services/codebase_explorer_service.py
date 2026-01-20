"""Codebase Explorer Service for querying and understanding the codebase.

Combines KnowledgeRepository and FileKnowledgeRepository to provide
comprehensive codebase search and exploration capabilities. Designed to
help users understand architecture, patterns, dependencies, and implementation
details before planning features or making changes.
"""
import re
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path

from db import KnowledgeRepository, FileKnowledgeRepository


@dataclass
class SearchResult:
    """A single search result from codebase exploration."""
    file_path: str = ""
    relevance_score: float = 0.0
    match_type: str = ""  # "file", "class", "function", "domain", "module", "pattern"
    title: str = ""
    description: str = ""
    code_snippet: str = ""
    line_number: int = 0
    context: Dict = field(default_factory=dict)


@dataclass
class CodebaseSearchResponse:
    """Response from a codebase search query."""
    query: str = ""
    total_results: int = 0
    results: List[SearchResult] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    context_summary: str = ""


@dataclass
class ArchitectureContext:
    """Architecture context for understanding the codebase."""
    project_name: str = ""
    project_type: str = ""
    primary_language: str = ""
    architecture_pattern: str = ""
    modules: List[Dict] = field(default_factory=list)
    entry_points: List[str] = field(default_factory=list)
    domains: List[Dict] = field(default_factory=list)
    conventions: List[str] = field(default_factory=list)
    technologies: Dict = field(default_factory=dict)


@dataclass
class FileDetails:
    """Detailed information about a specific file."""
    file_path: str = ""
    file_name: str = ""
    exists: bool = False
    has_knowledge: bool = False
    language: str = ""
    size_bytes: int = 0
    line_count: int = 0
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    classes: List[Dict] = field(default_factory=list)
    functions: List[Dict] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    domain_context: str = ""
    module_context: str = ""
    related_files: List[str] = field(default_factory=list)


@dataclass
class RelatedFilesResult:
    """Result of finding related files."""
    query: str = ""
    primary_matches: List[Dict] = field(default_factory=list)
    dependency_matches: List[Dict] = field(default_factory=list)
    domain_matches: List[Dict] = field(default_factory=list)
    module_matches: List[Dict] = field(default_factory=list)


@dataclass
class DomainPatterns:
    """Patterns and conventions for a specific domain."""
    domain_name: str = ""
    keywords: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    models: List[str] = field(default_factory=list)
    routes: List[str] = field(default_factory=list)
    naming_conventions: Dict = field(default_factory=dict)
    structure_patterns: Dict = field(default_factory=dict)
    common_imports: List[str] = field(default_factory=list)


@dataclass
class FormattedCodeSnippet:
    """A formatted code snippet for display."""
    file_path: str = ""
    language: str = ""
    start_line: int = 0
    end_line: int = 0
    code: str = ""
    context_description: str = ""
    highlights: List[int] = field(default_factory=list)


class CodebaseExplorerService:
    """Service for exploring and understanding the codebase.

    Combines knowledge from bulk scans (KnowledgeRepository) and
    file-level analysis (FileKnowledgeRepository) to provide
    comprehensive codebase search and exploration.

    Methods:
        search_codebase: Search across all knowledge for a query
        get_architecture_context: Get high-level architecture overview
        get_file_details: Get detailed info about a specific file
        find_related_files: Find files related to a query or path
        get_patterns_for_domain: Get patterns for a domain/area
        format_code_snippets: Format code snippets for display
    """

    def __init__(
        self,
        knowledge_repo: KnowledgeRepository,
        file_knowledge_repo: FileKnowledgeRepository,
        project_root: Path = None
    ):
        self.knowledge_repo = knowledge_repo
        self.file_knowledge_repo = file_knowledge_repo
        self.project_root = project_root or Path.cwd()

    async def search_codebase(
        self,
        query: str,
        max_results: int = 20,
        include_code: bool = True
    ) -> CodebaseSearchResponse:
        """Search the codebase for relevant information.

        Searches across domains, modules, files, classes, functions,
        and patterns to find information relevant to the query.
        Results are ranked by relevance.

        Args:
            query: Search query (can be natural language or keywords)
            max_results: Maximum number of results to return
            include_code: Whether to include code snippets in results

        Returns:
            CodebaseSearchResponse with ranked results and suggestions
        """
        response = CodebaseSearchResponse(query=query)
        all_results: List[Tuple[float, SearchResult]] = []

        # Extract keywords from query
        keywords = self._extract_keywords(query)
        query_lower = query.lower()

        # Search in codebase knowledge (domains, modules, patterns)
        knowledge_results = self._search_knowledge(keywords, query_lower)
        all_results.extend(knowledge_results)

        # Search in file-level knowledge
        file_results = self._search_file_knowledge(keywords, query_lower, include_code)
        all_results.extend(file_results)

        # Sort by relevance score (descending)
        all_results.sort(key=lambda x: x[0], reverse=True)

        # Take top results
        for score, result in all_results[:max_results]:
            result.relevance_score = score
            response.results.append(result)

        response.total_results = len(all_results)

        # Generate suggestions for follow-up queries
        response.suggestions = self._generate_suggestions(keywords, all_results)

        # Generate context summary
        response.context_summary = self._generate_context_summary(response.results)

        return response

    async def get_architecture_context(self) -> ArchitectureContext:
        """Get high-level architecture context.

        Returns comprehensive architecture information including
        project info, modules, domains, patterns, and technologies.

        Returns:
            ArchitectureContext with architecture overview
        """
        context = ArchitectureContext()

        # Load codebase knowledge
        knowledge = self.knowledge_repo.load_knowledge()
        if not knowledge:
            return context

        # Extract project info
        project = knowledge.get("project", {})
        context.project_name = project.get("name", "")
        context.project_type = project.get("type", "unknown")
        context.primary_language = project.get("primary_language", "")

        # Extract architecture
        architecture = knowledge.get("architecture", {})
        context.architecture_pattern = architecture.get("pattern", "unknown")
        context.entry_points = architecture.get("entry_points", [])

        # Extract modules with dependencies
        context.modules = [
            {
                "name": m.get("name", ""),
                "path": m.get("path", ""),
                "purpose": m.get("purpose", ""),
                "depends_on": m.get("depends_on", [])
            }
            for m in architecture.get("modules", [])
        ]

        # Extract domains
        context.domains = [
            {
                "name": d.get("name", ""),
                "keywords": d.get("keywords", []),
                "file_count": len(d.get("files", []))
            }
            for d in knowledge.get("domains", [])
        ]

        # Extract patterns/conventions
        patterns = knowledge.get("patterns", {})
        context.conventions = patterns.get("conventions", [])

        # Extract technologies
        tech = knowledge.get("technologies", {})
        context.technologies = {
            "languages": [l.get("name", "") for l in tech.get("languages", [])],
            "frameworks": [f.get("name", "") for f in tech.get("frameworks", [])],
            "tools": [t.get("name", "") for t in tech.get("tools", [])]
        }

        return context

    async def get_file_details(self, file_path: str) -> FileDetails:
        """Get detailed information about a specific file.

        Combines file-level knowledge with domain/module context
        from codebase knowledge.

        Args:
            file_path: Path to the file (relative or absolute)

        Returns:
            FileDetails with comprehensive file information
        """
        details = FileDetails(file_path=file_path)

        # Normalize path
        normalized_path = self._normalize_path(file_path)
        details.file_path = normalized_path
        details.file_name = Path(normalized_path).name

        # Check physical existence
        try:
            full_path = self._resolve_full_path(normalized_path)
            details.exists = full_path.exists()
        except Exception:
            details.exists = False

        # Load file-level knowledge
        file_knowledge = self.file_knowledge_repo.load_file_knowledge(normalized_path)
        if file_knowledge:
            details.has_knowledge = True
            details.language = file_knowledge.get("language", "")
            details.size_bytes = file_knowledge.get("size_bytes", 0)
            details.line_count = file_knowledge.get("line_count", 0)
            details.imports = file_knowledge.get("imports", [])
            details.exports = file_knowledge.get("exports", [])
            details.classes = file_knowledge.get("classes", [])
            details.functions = file_knowledge.get("functions", [])
            details.dependencies = file_knowledge.get("dependencies", [])

        # Get domain and module context from codebase knowledge
        knowledge = self.knowledge_repo.load_knowledge()
        if knowledge:
            # Find which domain this file belongs to
            for domain in knowledge.get("domains", []):
                if normalized_path in domain.get("files", []):
                    details.domain_context = domain.get("name", "")
                    break

            # Find which module this file belongs to
            for module in knowledge.get("architecture", {}).get("modules", []):
                module_path = module.get("path", "")
                if normalized_path.startswith(module_path):
                    details.module_context = module.get("name", "")
                    break

        # Find related files
        details.related_files = await self._find_related_files_for_path(normalized_path)

        return details

    async def find_related_files(self, query: str, limit: int = 10) -> RelatedFilesResult:
        """Find files related to a query or concept.

        Searches for files that are related by:
        - Direct name/path match
        - Shared dependencies
        - Same domain
        - Same module

        Args:
            query: Search query or file path
            limit: Maximum number of results per category

        Returns:
            RelatedFilesResult with categorized related files
        """
        result = RelatedFilesResult(query=query)
        keywords = self._extract_keywords(query)
        query_lower = query.lower()

        # Get all file knowledge
        all_files = self.file_knowledge_repo.get_all_file_knowledge()

        # Primary matches (name/path contains query terms)
        for file_data in all_files:
            file_path = file_data.get("file_path", "")
            file_lower = file_path.lower()

            score = 0
            for keyword in keywords:
                if keyword in file_lower:
                    score += 1

            if score > 0:
                result.primary_matches.append({
                    "file_path": file_path,
                    "score": score,
                    "language": file_data.get("language", ""),
                    "line_count": file_data.get("line_count", 0)
                })

        # Sort and limit primary matches
        result.primary_matches.sort(key=lambda x: x["score"], reverse=True)
        result.primary_matches = result.primary_matches[:limit]

        # Load codebase knowledge for domain/module matching
        knowledge = self.knowledge_repo.load_knowledge()
        if knowledge:
            # Domain matches
            for domain in knowledge.get("domains", []):
                domain_name = domain.get("name", "").lower()
                domain_keywords = [k.lower() for k in domain.get("keywords", [])]

                # Check if query matches domain
                match_score = 0
                for keyword in keywords:
                    if keyword in domain_name or keyword in domain_keywords:
                        match_score += 1

                if match_score > 0:
                    for file_path in domain.get("files", [])[:limit]:
                        result.domain_matches.append({
                            "file_path": file_path,
                            "domain": domain.get("name", ""),
                            "score": match_score
                        })

            # Module matches
            for module in knowledge.get("architecture", {}).get("modules", []):
                module_name = module.get("name", "").lower()
                module_purpose = module.get("purpose", "").lower()

                match_score = 0
                for keyword in keywords:
                    if keyword in module_name or keyword in module_purpose:
                        match_score += 1

                if match_score > 0:
                    module_path = module.get("path", "")
                    # Find files in this module
                    for file_data in all_files:
                        if file_data.get("file_path", "").startswith(module_path):
                            result.module_matches.append({
                                "file_path": file_data.get("file_path", ""),
                                "module": module.get("name", ""),
                                "score": match_score
                            })

            result.module_matches = result.module_matches[:limit]

        # Dependency matches (files that import/export similar things)
        if keywords:
            for file_data in all_files:
                imports = file_data.get("imports", [])
                exports = file_data.get("exports", [])
                all_deps = [i.lower() for i in imports + exports]

                for keyword in keywords:
                    for dep in all_deps:
                        if keyword in dep:
                            result.dependency_matches.append({
                                "file_path": file_data.get("file_path", ""),
                                "matched_on": dep,
                                "type": "import" if dep in [i.lower() for i in imports] else "export"
                            })
                            break

            result.dependency_matches = result.dependency_matches[:limit]

        return result

    async def get_patterns_for_domain(self, domain: str) -> DomainPatterns:
        """Get patterns and conventions for a specific domain.

        Returns naming conventions, structure patterns, common
        imports, and other patterns used in the domain.

        Args:
            domain: Domain name or keyword

        Returns:
            DomainPatterns with domain-specific patterns
        """
        patterns = DomainPatterns(domain_name=domain)
        domain_lower = domain.lower()

        # Load codebase knowledge
        knowledge = self.knowledge_repo.load_knowledge()
        if not knowledge:
            return patterns

        # Find matching domain
        matched_domain = None
        for d in knowledge.get("domains", []):
            if d.get("name", "").lower() == domain_lower:
                matched_domain = d
                break
            # Also check keywords
            if domain_lower in [k.lower() for k in d.get("keywords", [])]:
                matched_domain = d
                break

        if matched_domain:
            patterns.domain_name = matched_domain.get("name", "")
            patterns.keywords = matched_domain.get("keywords", [])
            patterns.files = matched_domain.get("files", [])
            patterns.models = matched_domain.get("models", [])
            patterns.routes = matched_domain.get("routes", [])

        # Get naming conventions and structure patterns
        codebase_patterns = knowledge.get("patterns", {})
        patterns.naming_conventions = codebase_patterns.get("naming", {})
        patterns.structure_patterns = codebase_patterns.get("structure", {})

        # Analyze common imports from domain files
        if patterns.files:
            import_counts: Dict[str, int] = {}
            for file_path in patterns.files[:20]:  # Limit for performance
                file_knowledge = self.file_knowledge_repo.load_file_knowledge(file_path)
                if file_knowledge:
                    for imp in file_knowledge.get("imports", []):
                        import_counts[imp] = import_counts.get(imp, 0) + 1

            # Sort by frequency
            sorted_imports = sorted(import_counts.items(), key=lambda x: x[1], reverse=True)
            patterns.common_imports = [imp for imp, count in sorted_imports[:15]]

        return patterns

    def format_code_snippets(
        self,
        file_path: str,
        elements: List[Dict],
        context_lines: int = 3
    ) -> List[FormattedCodeSnippet]:
        """Format code snippets for display.

        Creates formatted code snippets with context for classes,
        functions, or arbitrary line ranges.

        Args:
            file_path: Path to the source file
            elements: List of elements to format (with "line" or "start_line"/"end_line")
            context_lines: Number of context lines around each element

        Returns:
            List of FormattedCodeSnippet objects
        """
        snippets = []

        # Try to read the actual file
        try:
            full_path = self._resolve_full_path(file_path)
            if not full_path.exists():
                return snippets

            content = full_path.read_text(encoding="utf-8")
            lines = content.splitlines()
        except Exception:
            return snippets

        # Detect language from extension
        language = self._detect_language(full_path)

        for element in elements:
            # Get line range
            if "start_line" in element and "end_line" in element:
                start = element["start_line"]
                end = element["end_line"]
            elif "line" in element:
                start = element["line"]
                end = element.get("end_line", start + 10)  # Default snippet size
            else:
                continue

            # Add context lines
            start_with_context = max(1, start - context_lines)
            end_with_context = min(len(lines), end + context_lines)

            # Extract code
            code_lines = lines[start_with_context - 1:end_with_context]
            code = "\n".join(code_lines)

            # Generate context description
            name = element.get("name", "")
            element_type = element.get("type", "code")
            description = f"{element_type.title()}: {name}" if name else f"Lines {start}-{end}"

            # Highlight lines (the actual element lines, not context)
            highlights = list(range(start - start_with_context + 1, end - start_with_context + 2))

            snippet = FormattedCodeSnippet(
                file_path=file_path,
                language=language,
                start_line=start_with_context,
                end_line=end_with_context,
                code=code,
                context_description=description,
                highlights=highlights
            )
            snippets.append(snippet)

        return snippets

    # --- Private Helper Methods ---

    def _extract_keywords(self, query: str) -> List[str]:
        """Extract meaningful keywords from a query."""
        # Remove common stop words
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "can", "need", "to", "of", "in", "for", "on", "with", "at",
            "by", "from", "as", "into", "through", "during", "before",
            "after", "above", "below", "between", "under", "again", "further",
            "then", "once", "here", "there", "when", "where", "why", "how",
            "all", "each", "few", "more", "most", "other", "some", "such",
            "no", "nor", "not", "only", "own", "same", "so", "than", "too",
            "very", "just", "and", "but", "if", "or", "because", "until",
            "while", "about", "against", "what", "which", "who", "whom",
            "this", "that", "these", "those", "am", "it", "its"
        }

        # Tokenize and filter
        words = re.findall(r'\b\w+\b', query.lower())
        keywords = [w for w in words if w not in stop_words and len(w) > 2]

        return keywords

    def _search_knowledge(
        self,
        keywords: List[str],
        query_lower: str
    ) -> List[Tuple[float, SearchResult]]:
        """Search in codebase knowledge (domains, modules, patterns)."""
        results = []

        knowledge = self.knowledge_repo.load_knowledge()
        if not knowledge:
            return results

        # Search domains
        for domain in knowledge.get("domains", []):
            score = 0
            domain_name = domain.get("name", "").lower()
            domain_keywords = [k.lower() for k in domain.get("keywords", [])]

            for kw in keywords:
                if kw in domain_name:
                    score += 3
                if kw in domain_keywords:
                    score += 2

            if score > 0:
                result = SearchResult(
                    match_type="domain",
                    title=f"Domain: {domain.get('name', '')}",
                    description=f"Keywords: {', '.join(domain.get('keywords', [])[:5])}",
                    context={
                        "files": domain.get("files", [])[:5],
                        "models": domain.get("models", []),
                        "routes": domain.get("routes", [])
                    }
                )
                results.append((score, result))

        # Search modules
        for module in knowledge.get("architecture", {}).get("modules", []):
            score = 0
            module_name = module.get("name", "").lower()
            module_purpose = module.get("purpose", "").lower()
            module_path = module.get("path", "").lower()

            for kw in keywords:
                if kw in module_name:
                    score += 3
                if kw in module_purpose:
                    score += 2
                if kw in module_path:
                    score += 1

            if score > 0:
                result = SearchResult(
                    file_path=module.get("path", ""),
                    match_type="module",
                    title=f"Module: {module.get('name', '')}",
                    description=module.get("purpose", ""),
                    context={
                        "depends_on": module.get("depends_on", [])
                    }
                )
                results.append((score, result))

        # Search patterns/conventions
        patterns = knowledge.get("patterns", {})
        conventions = patterns.get("conventions", [])
        for convention in conventions:
            score = 0
            conv_lower = convention.lower()

            for kw in keywords:
                if kw in conv_lower:
                    score += 1

            if score > 0:
                result = SearchResult(
                    match_type="pattern",
                    title="Convention",
                    description=convention,
                    context={}
                )
                results.append((score, result))

        return results

    def _search_file_knowledge(
        self,
        keywords: List[str],
        query_lower: str,
        include_code: bool
    ) -> List[Tuple[float, SearchResult]]:
        """Search in file-level knowledge."""
        results = []

        all_files = self.file_knowledge_repo.get_all_file_knowledge()

        for file_data in all_files:
            file_path = file_data.get("file_path", "")
            file_lower = file_path.lower()

            # Score based on path match
            path_score = sum(1 for kw in keywords if kw in file_lower)

            # Add file result if path matches
            if path_score > 0:
                result = SearchResult(
                    file_path=file_path,
                    match_type="file",
                    title=Path(file_path).name,
                    description=f"{file_data.get('language', '')} - {file_data.get('line_count', 0)} lines",
                    context={
                        "language": file_data.get("language", ""),
                        "classes_count": len(file_data.get("classes", [])),
                        "functions_count": len(file_data.get("functions", []))
                    }
                )
                results.append((path_score, result))

            # Search classes
            for cls in file_data.get("classes", []):
                cls_name = cls.get("name", "").lower()
                score = sum(2 for kw in keywords if kw in cls_name)

                if score > 0:
                    result = SearchResult(
                        file_path=file_path,
                        match_type="class",
                        title=f"Class: {cls.get('name', '')}",
                        line_number=cls.get("line", 0),
                        description=f"in {Path(file_path).name}",
                        context={"class_info": cls}
                    )
                    results.append((score, result))

            # Search functions
            for func in file_data.get("functions", []):
                func_name = func.get("name", "").lower()
                score = sum(2 for kw in keywords if kw in func_name)

                if score > 0:
                    result = SearchResult(
                        file_path=file_path,
                        match_type="function",
                        title=f"Function: {func.get('name', '')}",
                        line_number=func.get("line", 0),
                        description=f"in {Path(file_path).name}",
                        context={"function_info": func}
                    )
                    results.append((score, result))

            # Search imports
            for imp in file_data.get("imports", []):
                imp_lower = imp.lower()
                score = sum(1 for kw in keywords if kw in imp_lower)

                if score > 0:
                    result = SearchResult(
                        file_path=file_path,
                        match_type="import",
                        title=f"Import: {imp}",
                        description=f"used in {Path(file_path).name}",
                        context={"import": imp}
                    )
                    results.append((score * 0.5, result))  # Lower weight for imports

        return results

    def _generate_suggestions(
        self,
        keywords: List[str],
        results: List[Tuple[float, SearchResult]]
    ) -> List[str]:
        """Generate suggestions for follow-up queries."""
        suggestions = []

        # Collect related terms from results
        related_terms = set()
        for _, result in results[:10]:
            if result.match_type == "domain":
                # Add domain keywords
                if "keywords" in result.context:
                    related_terms.update(result.context.get("keywords", []))
            elif result.match_type == "module":
                # Add dependency names
                if "depends_on" in result.context:
                    related_terms.update(result.context.get("depends_on", []))

        # Filter out already-searched keywords
        new_terms = [t for t in related_terms if t.lower() not in keywords]

        # Generate suggestions
        if new_terms:
            suggestions.append(f"Related: {', '.join(new_terms[:3])}")

        # Suggest narrowing by file type
        file_types = set()
        for _, result in results:
            if result.match_type == "file":
                lang = result.context.get("language", "")
                if lang:
                    file_types.add(lang)

        if len(file_types) > 1:
            suggestions.append(f"Try filtering by language: {', '.join(list(file_types)[:3])}")

        return suggestions[:3]

    def _generate_context_summary(self, results: List[SearchResult]) -> str:
        """Generate a summary of the search context."""
        if not results:
            return "No results found. Try different keywords or check if knowledge has been scanned."

        # Count by type
        type_counts: Dict[str, int] = {}
        for r in results:
            type_counts[r.match_type] = type_counts.get(r.match_type, 0) + 1

        parts = []
        for match_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            parts.append(f"{count} {match_type}(s)")

        return f"Found: {', '.join(parts)}"

    async def _find_related_files_for_path(self, file_path: str) -> List[str]:
        """Find files related to a specific file path."""
        related = []

        # Get this file's knowledge
        file_knowledge = self.file_knowledge_repo.load_file_knowledge(file_path)
        if not file_knowledge:
            return related

        # Get imports from this file
        imports = file_knowledge.get("imports", [])

        # Find files that export what this file imports
        all_files = self.file_knowledge_repo.get_all_file_knowledge()
        for other_file in all_files:
            if other_file.get("file_path") == file_path:
                continue

            other_exports = other_file.get("exports", [])
            other_imports = other_file.get("imports", [])

            # Check if other file exports something this file imports
            for imp in imports:
                imp_base = imp.split(".")[-1].lower()
                for exp in other_exports:
                    if imp_base in exp.lower():
                        related.append(other_file.get("file_path", ""))
                        break

            # Check if other file imports from same modules
            common_imports = set(imports) & set(other_imports)
            if len(common_imports) > 2:  # Significant overlap
                if other_file.get("file_path", "") not in related:
                    related.append(other_file.get("file_path", ""))

        return related[:10]  # Limit results

    def _normalize_path(self, file_path: str) -> str:
        """Normalize a file path for consistent storage."""
        path = Path(file_path)

        if path.is_absolute():
            try:
                path = path.relative_to(self.project_root)
            except ValueError:
                pass

        return str(path).replace("\\", "/")

    def _resolve_full_path(self, normalized_path: str) -> Path:
        """Resolve a normalized path to an absolute path."""
        path = Path(normalized_path)
        if not path.is_absolute():
            path = self.project_root / path
        return path.resolve()

    def _detect_language(self, file_path: Path) -> str:
        """Detect programming language from file extension."""
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
            ".rb": "ruby",
            ".php": "php",
            ".c": "c",
            ".cpp": "cpp",
            ".h": "c",
            ".hpp": "cpp",
            ".cs": "csharp",
            ".swift": "swift",
            ".kt": "kotlin",
            ".sql": "sql",
            ".html": "html",
            ".css": "css",
            ".scss": "scss",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".toml": "toml",
            ".xml": "xml",
            ".md": "markdown",
            ".sh": "shell",
        }
        return ext_map.get(file_path.suffix.lower(), "unknown")

    # --- Aliases for compatibility with question_service interface ---

    async def get_architecture_overview(self) -> ArchitectureContext:
        """Alias for get_architecture_context for API compatibility."""
        return await self.get_architecture_context()

    async def get_file_analysis(self, file_path: str) -> FileDetails:
        """Alias for get_file_details for API compatibility."""
        return await self.get_file_details(file_path)

    async def get_exploration_data_for_template(self, query: str = "") -> Dict:
        """Get exploration data formatted for template rendering.

        Args:
            query: Optional search query

        Returns:
            Dict with exploration results and architecture context
        """
        result = {
            "query": query,
            "results": [],
            "architecture": {},
            "stats": {},
            "domains": [],
            "modules": []
        }

        # Get architecture overview
        overview = await self.get_architecture_context()
        result["architecture"] = {
            "project_name": overview.project_name,
            "project_type": overview.project_type,
            "primary_language": overview.primary_language,
            "architecture_pattern": overview.architecture_pattern,
            "modules_count": len(overview.modules),
            "domains_count": len(overview.domains),
            "technologies": overview.technologies
        }

        # Include domains and modules for exploration
        result["domains"] = overview.domains[:5]  # Top 5 domains
        result["modules"] = overview.modules[:5]  # Top 5 modules

        # If query provided, search
        if query:
            exploration = await self.search_codebase(query)
            result["results"] = [
                {
                    "file_path": r.file_path,
                    "match_type": r.match_type,
                    "title": r.title,
                    "description": r.description,
                    "line_number": r.line_number,
                    "relevance_score": r.relevance_score
                }
                for r in exploration.results
            ]
            result["total_results"] = exploration.total_results
            result["suggestions"] = exploration.suggestions
            result["context_summary"] = exploration.context_summary

        # Get stats
        all_files = self.file_knowledge_repo.get_all_file_knowledge()
        result["stats"] = {
            "total_files": len(all_files),
            "has_knowledge": bool(self.knowledge_repo.load_knowledge())
        }

        return result

    async def get_recent_explorations(self, limit: int = 5) -> List[Dict]:
        """Get recent exploration highlights for dashboard display.

        Returns domains and modules as exploration entry points,
        formatted for the dashboard widget.

        Args:
            limit: Maximum number of items to return

        Returns:
            List of exploration items with type, name, and description
        """
        explorations = []

        # Get architecture context
        context = await self.get_architecture_context()

        # Add domains as exploration items
        for domain in context.domains[:limit]:
            explorations.append({
                "type": "domain",
                "name": domain.get("name", "Unknown Domain"),
                "description": f"Domain with {domain.get('file_count', 0)} files",
                "keywords": domain.get("keywords", [])[:3],
                "icon": "folder",
                "link": f"/questions?domain={domain.get('name', '')}"
            })

        # Add modules as exploration items
        remaining = limit - len(explorations)
        for module in context.modules[:remaining]:
            explorations.append({
                "type": "module",
                "name": module.get("name", "Unknown Module"),
                "description": module.get("purpose", "")[:60] or "Code module",
                "path": module.get("path", ""),
                "icon": "code",
                "link": f"/explore/{module.get('path', '')}"
            })

        return explorations[:limit]
