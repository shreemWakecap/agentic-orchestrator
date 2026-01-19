"""
System Explorer: Simple codebase tech detection.

Detects technologies from project files to identify missing expert coverage.
"""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class TechDetection:
    """Detected technology."""
    name: str
    category: str  # language, framework, tool
    confidence: float
    source: str  # What indicated this tech


# Detection patterns - what files/deps indicate which tech
TECH_PATTERNS = {
    # Languages
    "python": {"files": ["pyproject.toml", "requirements.txt", "*.py"], "category": "language"},
    "typescript": {"files": ["tsconfig.json", "*.ts", "*.tsx"], "category": "language"},
    "javascript": {"files": ["*.js", "*.jsx"], "category": "language"},
    "go": {"files": ["go.mod", "*.go"], "category": "language"},
    "rust": {"files": ["Cargo.toml", "*.rs"], "category": "language"},

    # Python frameworks
    "fastapi": {"deps": ["fastapi"], "category": "framework"},
    "django": {"deps": ["django"], "files": ["manage.py"], "category": "framework"},
    "flask": {"deps": ["flask"], "category": "framework"},

    # JS frameworks
    "react": {"deps": ["react"], "category": "framework"},
    "vue": {"deps": ["vue"], "files": ["*.vue"], "category": "framework"},
    "nextjs": {"deps": ["next"], "category": "framework"},
    "express": {"deps": ["express"], "category": "framework"},

    # Tools
    "docker": {"files": ["Dockerfile", "docker-compose.yml"], "category": "tool"},
}


def detect_technologies(project_root: Path) -> list[TechDetection]:
    """
    Detect technologies used in a project.

    Returns list of TechDetection sorted by confidence.
    """
    detections = []

    # Load dependency files once
    py_deps = _get_python_deps(project_root)
    js_deps = _get_js_deps(project_root)
    all_deps = py_deps | js_deps

    for tech_name, pattern in TECH_PATTERNS.items():
        confidence = 0.0
        source = ""

        # Check dependencies
        if "deps" in pattern:
            for dep in pattern["deps"]:
                if dep in all_deps:
                    confidence = 0.9
                    source = f"dependency: {dep}"
                    break

        # Check files
        if "files" in pattern and confidence < 0.9:
            for file_pattern in pattern["files"]:
                if file_pattern.startswith("*"):
                    # Glob pattern - just check if any exist
                    matches = list(project_root.glob(f"**/{file_pattern}"))[:1]
                    if matches:
                        confidence = max(confidence, 0.7)
                        source = source or f"file: {file_pattern}"
                else:
                    # Exact file
                    if (project_root / file_pattern).exists():
                        confidence = max(confidence, 0.8)
                        source = source or f"file: {file_pattern}"

        if confidence > 0.5:
            detections.append(TechDetection(
                name=tech_name,
                category=pattern["category"],
                confidence=confidence,
                source=source
            ))

    # Sort by confidence
    detections.sort(key=lambda d: d.confidence, reverse=True)
    return detections


def find_missing_experts(project_root: Path, existing_expert_names: list[str]) -> list[dict]:
    """
    Find technologies without expert coverage.

    Args:
        project_root: Project directory
        existing_expert_names: Names of existing experts (lowercase)

    Returns:
        List of gaps: [{"name": "fastapi", "type": "tech", "category": "framework", "source": "..."}]
    """
    existing = {name.lower() for name in existing_expert_names}
    detections = detect_technologies(project_root)

    gaps = []
    for tech in detections:
        if tech.name.lower() not in existing:
            gaps.append({
                "name": tech.name,
                "type": "tech",
                "category": tech.category,
                "confidence": tech.confidence,
                "source": tech.source
            })

    return gaps


def _get_python_deps(project_root: Path) -> set[str]:
    """Extract Python dependencies."""
    deps = set()

    # pyproject.toml
    pyproject = project_root / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text().lower()
            # Simple extraction - look for common deps
            for dep in ["fastapi", "django", "flask", "pydantic"]:
                if dep in content:
                    deps.add(dep)
        except Exception:
            pass

    # requirements.txt
    reqs = project_root / "requirements.txt"
    if reqs.exists():
        try:
            for line in reqs.read_text().splitlines():
                line = line.strip().lower().split("==")[0].split(">=")[0].split("[")[0]
                if line and not line.startswith("#"):
                    deps.add(line)
        except Exception:
            pass

    return deps


def _get_js_deps(project_root: Path) -> set[str]:
    """Extract JavaScript dependencies."""
    deps = set()

    pkg_json = project_root / "package.json"
    if pkg_json.exists():
        try:
            pkg = json.loads(pkg_json.read_text())
            deps.update(pkg.get("dependencies", {}).keys())
            deps.update(pkg.get("devDependencies", {}).keys())
        except Exception:
            pass

    return deps
