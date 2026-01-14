"""
Plan Registry: Manages cross-plan dependency tracking and deduplication.

Provides:
- Plan metadata generation and storage
- Registry maintenance (scan, index, update)
- Similarity detection between plans
- Dependency resolution
"""
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PlanMetadata:
    """Metadata for a single plan."""
    plan_id: str
    plan_name: str
    request: str
    request_hash: str
    keywords: list[str] = field(default_factory=list)
    features_provided: list[str] = field(default_factory=list)
    features_required: list[str] = field(default_factory=list)
    files_affected: list[str] = field(default_factory=list)
    modules_touched: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)
    status: str = "pending"
    complexity: str = "simple"
    created_at: str = ""
    updated_at: str = ""
    similarity_scores: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "schema_version": "1.0",
            "plan_id": self.plan_id,
            "plan_name": self.plan_name,
            "request": self.request,
            "request_hash": self.request_hash,
            "keywords": self.keywords,
            "features_provided": self.features_provided,
            "features_required": self.features_required,
            "files_affected": self.files_affected,
            "modules_touched": self.modules_touched,
            "depends_on": self.depends_on,
            "blocked_by": self.blocked_by,
            "status": self.status,
            "complexity": self.complexity,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "similarity_scores": self.similarity_scores
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PlanMetadata":
        """Create from dictionary."""
        return cls(
            plan_id=data.get("plan_id", ""),
            plan_name=data.get("plan_name", ""),
            request=data.get("request", ""),
            request_hash=data.get("request_hash", ""),
            keywords=data.get("keywords", []),
            features_provided=data.get("features_provided", []),
            features_required=data.get("features_required", []),
            files_affected=data.get("files_affected", []),
            modules_touched=data.get("modules_touched", []),
            depends_on=data.get("depends_on", []),
            blocked_by=data.get("blocked_by", []),
            status=data.get("status", "pending"),
            complexity=data.get("complexity", "simple"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            similarity_scores=data.get("similarity_scores", {})
        )


@dataclass
class ScanResult:
    """Result of pre-planning scan."""
    has_conflicts: bool
    duplicates: list[dict]  # [{plan_id, similarity, recommendation}]
    dependencies: list[dict]  # [{plan_id, reason, status}]
    blocked_by: list[dict]  # [{plan_id, reason}]
    recommendation: str  # "proceed", "warn", "block"
    message: str


class PlanRegistry:
    """
    Manages plan registry and cross-plan analysis.

    Provides:
    - Scanning of existing plans
    - Similarity detection
    - Dependency tracking
    - Pre-planning conflict detection
    """

    SIMILARITY_THRESHOLD_WARN = 0.6
    SIMILARITY_THRESHOLD_BLOCK = 0.85

    # Stop words for keyword extraction
    STOP_WORDS = {
        'a', 'an', 'the', 'to', 'for', 'with', 'and', 'or', 'in', 'on',
        'add', 'create', 'implement', 'build', 'make', 'update', 'new',
        'that', 'this', 'is', 'are', 'be', 'been', 'being', 'have', 'has',
        'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
        'of', 'at', 'by', 'from', 'up', 'about', 'into', 'over', 'after'
    }

    def __init__(self, project_root: Path):
        """
        Initialize plan registry.

        Args:
            project_root: Root directory of the project
        """
        self.project_root = project_root
        self.specs_dir = project_root / ".orchestrator" / "specs"
        self.registry_path = self.specs_dir / "registry.json"
        self._registry: dict = {}
        self._load_registry()

    def _load_registry(self) -> None:
        """Load or initialize the registry."""
        if self.registry_path.exists():
            try:
                self._registry = json.loads(
                    self.registry_path.read_text(encoding="utf-8")
                )
                logger.debug(f"Loaded registry with {len(self._registry.get('plans', {}))} plans")
            except json.JSONDecodeError:
                logger.warning("Invalid registry.json, creating new registry")
                self._registry = self._create_empty_registry()
        else:
            self._registry = self._create_empty_registry()

    def _create_empty_registry(self) -> dict:
        """Create an empty registry structure."""
        return {
            "schema_version": "1.0",
            "last_scan": None,
            "plans": {},
            "features_index": {},
            "files_index": {},
            "stats": {
                "total_plans": 0,
                "pending": 0,
                "in_progress": 0,
                "completed": 0,
                "failed": 0
            }
        }

    def _save_registry(self) -> None:
        """Persist registry to disk."""
        self.specs_dir.mkdir(parents=True, exist_ok=True)
        self.registry_path.write_text(
            json.dumps(self._registry, indent=2),
            encoding="utf-8"
        )
        logger.debug("Registry saved to disk")

    @staticmethod
    def compute_request_hash(request: str) -> str:
        """
        Compute a normalized hash of a request.

        Normalizes by lowercasing, removing punctuation, and sorting words.
        This helps detect requests that are semantically similar but worded differently.
        """
        # Normalize: lowercase, remove punctuation, sort words
        normalized = re.sub(r'[^\w\s]', '', request.lower())
        words = sorted(normalized.split())
        return hashlib.sha256(' '.join(words).encode()).hexdigest()[:16]

    @classmethod
    def extract_keywords(cls, request: str) -> list[str]:
        """
        Extract meaningful keywords from a request.

        Removes stop words and returns substantive terms.
        """
        words = re.sub(r'[^\w\s]', '', request.lower()).split()
        return [w for w in words if w not in cls.STOP_WORDS and len(w) > 2]

    @staticmethod
    def normalize_word(word: str) -> str:
        """
        Normalize a word by removing common suffixes for better matching.

        Handles basic stemming: tests->test, testing->test, tested->test
        """
        word = word.lower()

        # Special case: preserve minimum word length of 3
        if len(word) <= 3:
            return word

        # Common suffix removals with minimum remaining length check
        suffix_rules = [
            # (suffix, min_remaining_length)
            ('ation', 3),
            ('ment', 3),
            ('ness', 3),
            ('able', 3),
            ('ible', 3),
            ('ful', 3),
            ('less', 3),
            ('ous', 3),
            ('ive', 3),
            ('ion', 3),
            ('ing', 3),
            ('ed', 3),
            ('es', 3),
            ('s', 3),
        ]

        for suffix, min_len in suffix_rules:
            if word.endswith(suffix):
                stem = word[:-len(suffix)]
                if len(stem) >= min_len:
                    return stem

        return word

    def scan_existing_plans(self) -> None:
        """
        Scan all plan directories and update registry.

        Scans pending, in-progress, completed, and failed directories.
        Extracts or loads metadata for each plan and builds indices.
        """
        status_dirs = ["pending", "in-progress", "completed", "failed"]

        self._registry["plans"] = {}
        self._registry["features_index"] = {}
        self._registry["files_index"] = {}
        stats = {
            "total_plans": 0,
            "pending": 0,
            "in_progress": 0,
            "completed": 0,
            "failed": 0
        }

        for status in status_dirs:
            status_dir = self.specs_dir / status
            if not status_dir.exists():
                continue

            for plan_dir in status_dir.iterdir():
                if not plan_dir.is_dir():
                    continue

                # Skip hidden directories
                if plan_dir.name.startswith('.'):
                    continue

                metadata = self._load_plan_metadata(plan_dir, status)
                if metadata:
                    plan_id = metadata.plan_id
                    self._registry["plans"][plan_id] = {
                        "path": f"{status}/{plan_dir.name}",
                        "status": status.replace("-", "_"),
                        "request": metadata.request,
                        "request_hash": metadata.request_hash,
                        "keywords": metadata.keywords,
                        "features_provided": metadata.features_provided,
                        "files_affected": metadata.files_affected,
                        "depends_on": metadata.depends_on
                    }

                    # Update feature index
                    for feature in metadata.features_provided:
                        if feature not in self._registry["features_index"]:
                            self._registry["features_index"][feature] = []
                        if plan_id not in self._registry["features_index"][feature]:
                            self._registry["features_index"][feature].append(plan_id)

                    # Update file index
                    for file_pattern in metadata.files_affected:
                        if file_pattern not in self._registry["files_index"]:
                            self._registry["files_index"][file_pattern] = []
                        if plan_id not in self._registry["files_index"][file_pattern]:
                            self._registry["files_index"][file_pattern].append(plan_id)

                    stats["total_plans"] += 1
                    stat_key = status.replace("-", "_")
                    if stat_key in stats:
                        stats[stat_key] += 1

        self._registry["stats"] = stats
        self._registry["last_scan"] = datetime.now().isoformat()
        self._save_registry()
        logger.info(f"Registry scan complete: {stats['total_plans']} plans indexed")

    def _load_plan_metadata(self, plan_dir: Path, status: str) -> Optional[PlanMetadata]:
        """
        Load or generate metadata for a plan.

        First checks for existing metadata.json.
        If not found, extracts metadata from 00_overview.md.
        """
        metadata_file = plan_dir / "metadata.json"

        if metadata_file.exists():
            try:
                data = json.loads(metadata_file.read_text(encoding="utf-8"))
                return PlanMetadata.from_dict(data)
            except json.JSONDecodeError:
                logger.warning(f"Invalid metadata.json in {plan_dir}")

        # Generate metadata from plan content
        # Try plan.md first (new single-file format), then 00_overview.md (legacy format)
        plan_file = plan_dir / "plan.md"
        overview_file = plan_dir / "00_overview.md"

        if plan_file.exists():
            content = plan_file.read_text(encoding="utf-8")
        elif overview_file.exists():
            content = overview_file.read_text(encoding="utf-8")
        else:
            logger.debug(f"No plan.md or 00_overview.md in {plan_dir}")
            return None
        metadata = self._extract_metadata_from_overview(plan_dir, content, status)

        # Save generated metadata for future use
        if metadata:
            try:
                metadata_file.write_text(
                    json.dumps(metadata.to_dict(), indent=2),
                    encoding="utf-8"
                )
                logger.debug(f"Generated metadata.json for {plan_dir.name}")
            except Exception as e:
                logger.warning(f"Failed to save metadata for {plan_dir}: {e}")

        return metadata

    def _extract_metadata_from_overview(
        self, plan_dir: Path, content: str, status: str
    ) -> Optional[PlanMetadata]:
        """Extract metadata from 00_overview.md content."""
        # Extract plan ID from directory name (e.g., "001_feature-name")
        match = re.match(r'^(\d+)[_-](.+)$', plan_dir.name)
        if not match:
            return None

        plan_id = match.group(1).lstrip('0') or '0'
        plan_name = match.group(2)

        # Extract request from "**Request:**" line
        request_match = re.search(r'\*\*Request:\*\*\s*(.+)', content)
        request = request_match.group(1).strip() if request_match else plan_name.replace('-', ' ')

        # Extract complexity from header
        complexity_match = re.search(r'Complexity:\s*(\w+)', content, re.IGNORECASE)
        complexity = complexity_match.group(1).lower() if complexity_match else "simple"

        # Extract timestamp
        timestamp_match = re.search(r'Generated on\s*([\d-]+\s+[\d:]+)', content)
        created_at = ""
        if timestamp_match:
            try:
                # Convert to ISO format
                dt = datetime.strptime(timestamp_match.group(1), "%Y-%m-%d %H:%M")
                created_at = dt.isoformat()
            except ValueError:
                created_at = timestamp_match.group(1)

        # Extract keywords and infer features
        keywords = self.extract_keywords(request)
        features = self._infer_features_from_keywords(keywords, request)
        files = self._infer_files_from_request(request, keywords)

        return PlanMetadata(
            plan_id=plan_id,
            plan_name=plan_name,
            request=request,
            request_hash=self.compute_request_hash(request),
            keywords=keywords,
            features_provided=features,
            files_affected=files,
            status=status.replace("-", "_"),
            complexity=complexity,
            created_at=created_at,
            updated_at=created_at
        )

    def _infer_features_from_keywords(self, keywords: list[str], request: str) -> list[str]:
        """Infer feature names from keywords."""
        features = []
        request_lower = request.lower()

        # Common feature patterns
        feature_patterns = {
            'test': ['testing'],
            'e2e': ['e2e-testing'],
            'playwright': ['playwright-setup'],
            'auth': ['authentication'],
            'api': ['api-endpoints'],
            'ui': ['ui-components'],
            'database': ['database-setup'],
            'config': ['configuration'],
        }

        for keyword in keywords:
            if keyword in feature_patterns:
                features.extend(feature_patterns[keyword])
            elif len(keyword) > 3:
                features.append(f"{keyword}-feature")

        # Deduplicate while preserving order
        seen = set()
        unique_features = []
        for f in features:
            if f not in seen:
                seen.add(f)
                unique_features.append(f)

        return unique_features[:5]  # Limit to 5 features

    def _infer_files_from_request(self, request: str, keywords: list[str]) -> list[str]:
        """Infer likely affected file patterns from request."""
        patterns = []
        request_lower = request.lower()

        # Common patterns based on keywords
        pattern_map = {
            'test': ['tests/*'],
            'e2e': ['tests/e2e/*'],
            'playwright': ['tests/e2e/*', 'playwright.config.*'],
            'api': ['api/*', 'routes/*'],
            'auth': ['auth/*', 'middleware/*'],
            'config': ['config/*', '*.config.*'],
            'ui': ['src/components/*'],
            'component': ['src/components/*'],
            'database': ['models/*', 'migrations/*'],
            'style': ['styles/*', '*.css', '*.scss'],
        }

        for keyword in keywords:
            if keyword in pattern_map:
                patterns.extend(pattern_map[keyword])

        # Deduplicate
        return list(dict.fromkeys(patterns)) or ['*']

    def calculate_similarity(self, request1: str, request2: str) -> float:
        """
        Calculate Jaccard similarity between two requests.

        Uses keyword-based comparison with normalization for better matching.
        """
        # Extract and normalize keywords
        words1 = set(self.normalize_word(w) for w in self.extract_keywords(request1))
        words2 = set(self.normalize_word(w) for w in self.extract_keywords(request2))

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def find_similar_plans(self, request: str) -> list[tuple[str, float, dict]]:
        """
        Find plans similar to the given request.

        Returns list of (plan_id, similarity_score, plan_data) tuples,
        sorted by similarity in descending order.
        """
        similar = []

        for plan_id, plan_data in self._registry.get("plans", {}).items():
            existing_request = plan_data.get("request", "")
            similarity = self.calculate_similarity(request, existing_request)

            if similarity > 0.3:  # Minimum threshold
                similar.append((plan_id, similarity, plan_data))

        return sorted(similar, key=lambda x: x[1], reverse=True)

    def find_feature_conflicts(self, features: list[str]) -> list[dict]:
        """Find plans that provide the same features."""
        conflicts = []
        features_index = self._registry.get("features_index", {})

        for feature in features:
            if feature in features_index:
                for plan_id in features_index[feature]:
                    plan_data = self._registry["plans"].get(plan_id, {})
                    conflicts.append({
                        "plan_id": plan_id,
                        "feature": feature,
                        "status": plan_data.get("status", "unknown"),
                        "request": plan_data.get("request", "")
                    })

        return conflicts

    def find_file_conflicts(self, files: list[str]) -> list[dict]:
        """Find plans that affect the same files."""
        conflicts = []
        files_index = self._registry.get("files_index", {})

        for file_pattern in files:
            for indexed_pattern, plan_ids in files_index.items():
                if self._patterns_overlap(file_pattern, indexed_pattern):
                    for plan_id in plan_ids:
                        plan_data = self._registry["plans"].get(plan_id, {})
                        conflicts.append({
                            "plan_id": plan_id,
                            "file_pattern": indexed_pattern,
                            "status": plan_data.get("status", "unknown"),
                            "request": plan_data.get("request", "")
                        })

        return conflicts

    @staticmethod
    def _patterns_overlap(pattern1: str, pattern2: str) -> bool:
        """Check if two file patterns might overlap."""
        # Simple heuristic: check if patterns share a common prefix
        p1_parts = pattern1.rstrip('*').rstrip('/').split('/')
        p2_parts = pattern2.rstrip('*').rstrip('/').split('/')

        min_len = min(len(p1_parts), len(p2_parts))
        if min_len == 0:
            return True  # Wildcards overlap with everything

        return p1_parts[:min_len] == p2_parts[:min_len]

    def pre_planning_scan(self, request: str) -> ScanResult:
        """
        Perform pre-planning scan for a new request.

        Checks for duplicates, similar plans, and potential dependencies.
        Returns ScanResult with recommendation.
        """
        # Ensure registry is fresh
        self.scan_existing_plans()

        duplicates = []
        dependencies = []
        blocked_by = []

        # Check for similar plans
        similar_plans = self.find_similar_plans(request)

        for plan_id, similarity, plan_data in similar_plans:
            if similarity >= self.SIMILARITY_THRESHOLD_BLOCK:
                duplicates.append({
                    "plan_id": plan_id,
                    "similarity": similarity,
                    "status": plan_data.get("status"),
                    "request": plan_data.get("request"),
                    "recommendation": "block"
                })
            elif similarity >= self.SIMILARITY_THRESHOLD_WARN:
                duplicates.append({
                    "plan_id": plan_id,
                    "similarity": similarity,
                    "status": plan_data.get("status"),
                    "request": plan_data.get("request"),
                    "recommendation": "warn"
                })

        # Check for potential dependencies
        keywords = self.extract_keywords(request)
        for plan_id, plan_data in self._registry.get("plans", {}).items():
            # Skip if already in duplicates
            if any(d["plan_id"] == plan_id for d in duplicates):
                continue

            plan_features = plan_data.get("features_provided", [])
            for feature in plan_features:
                # Check if any keyword matches the feature
                feature_words = feature.lower().replace('-', ' ').split()
                if any(kw in feature_words for kw in keywords):
                    status = plan_data.get("status", "pending")
                    if status in ("pending", "in_progress"):
                        dependencies.append({
                            "plan_id": plan_id,
                            "feature": feature,
                            "status": status,
                            "reason": f"Plan {plan_id} provides '{feature}' which may be needed",
                            "request": plan_data.get("request", "")
                        })

        # Determine recommendation
        has_conflicts = bool(duplicates)
        blocking_duplicates = [d for d in duplicates if d["recommendation"] == "block"]

        if blocking_duplicates:
            recommendation = "block"
            plan_ids = [d['plan_id'] for d in blocking_duplicates]
            message = f"Near-duplicate plan(s) found: {plan_ids}"
        elif duplicates:
            recommendation = "warn"
            plan_ids = [d['plan_id'] for d in duplicates]
            message = f"Similar plan(s) exist: {plan_ids}"
        elif dependencies:
            recommendation = "warn"
            plan_ids = [d['plan_id'] for d in dependencies]
            message = f"Potential dependencies on plans: {plan_ids}"
        else:
            recommendation = "proceed"
            message = "No conflicts detected"

        return ScanResult(
            has_conflicts=has_conflicts,
            duplicates=duplicates,
            dependencies=dependencies,
            blocked_by=blocked_by,
            recommendation=recommendation,
            message=message
        )

    def get_plan(self, plan_id: str) -> Optional[dict]:
        """Get plan data from registry."""
        return self._registry.get("plans", {}).get(plan_id)

    def get_all_plans(self) -> dict[str, dict]:
        """Get all plans from registry."""
        return self._registry.get("plans", {})

    def get_stats(self) -> dict:
        """Get registry statistics."""
        return self._registry.get("stats", {})

    def update_plan_status(self, plan_id: str, new_status: str) -> None:
        """Update a plan's status in the registry."""
        if plan_id in self._registry.get("plans", {}):
            old_status = self._registry["plans"][plan_id].get("status", "pending")
            self._registry["plans"][plan_id]["status"] = new_status

            # Update stats
            if old_status in self._registry["stats"]:
                self._registry["stats"][old_status] = max(
                    0, self._registry["stats"][old_status] - 1
                )
            if new_status in self._registry["stats"]:
                self._registry["stats"][new_status] += 1

            self._save_registry()
            logger.info(f"Plan {plan_id} status updated: {old_status} -> {new_status}")

    def add_dependency(self, plan_id: str, depends_on_id: str) -> None:
        """Add a dependency between plans."""
        if plan_id in self._registry.get("plans", {}):
            deps = self._registry["plans"][plan_id].get("depends_on", [])
            if depends_on_id not in deps:
                deps.append(depends_on_id)
                self._registry["plans"][plan_id]["depends_on"] = deps
                self._save_registry()
                logger.info(f"Added dependency: {plan_id} depends on {depends_on_id}")

    def get_dependency_chain(self, plan_id: str) -> list[str]:
        """Get the full dependency chain for a plan."""
        chain = []
        visited = set()

        def traverse(pid: str):
            if pid in visited:
                return
            visited.add(pid)

            plan_data = self.get_plan(pid)
            if plan_data:
                for dep_id in plan_data.get("depends_on", []):
                    traverse(dep_id)
                    if dep_id not in chain:
                        chain.append(dep_id)

        traverse(plan_id)
        return chain
