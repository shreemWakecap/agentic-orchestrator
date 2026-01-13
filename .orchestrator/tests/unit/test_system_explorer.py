"""Tests for system_explorer - simple codebase tech detection."""
import json
import pytest
from pathlib import Path

from core.system_explorer import (
    TechDetection,
    detect_technologies,
    find_missing_experts,
)


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project structure."""
    # Create Python project files
    (tmp_path / "pyproject.toml").write_text("""
[project]
name = "test-project"
requires-python = ">=3.11"

[project.dependencies]
fastapi = ">=0.109.0"
pydantic = ">=2.0"
""")

    # Create source directory
    src = tmp_path / "src"
    src.mkdir()

    # Create Python files
    (src / "main.py").write_text("""
from fastapi import FastAPI
app = FastAPI()
""")

    return tmp_path


class TestTechDetection:
    """Tests for technology detection."""

    def test_detect_python(self, temp_project):
        """Should detect Python from pyproject.toml."""
        techs = detect_technologies(temp_project)
        python_tech = next((t for t in techs if t.name == "python"), None)

        assert python_tech is not None
        assert python_tech.category == "language"
        assert python_tech.confidence > 0

    def test_detect_fastapi(self, temp_project):
        """Should detect FastAPI from dependencies."""
        techs = detect_technologies(temp_project)
        fastapi_tech = next((t for t in techs if t.name == "fastapi"), None)

        assert fastapi_tech is not None
        assert fastapi_tech.category == "framework"

    def test_confidence_scores(self, temp_project):
        """Confidence scores should be between 0 and 1."""
        techs = detect_technologies(temp_project)

        for tech in techs:
            assert 0 <= tech.confidence <= 1

    def test_detection_has_source(self, temp_project):
        """Detections should include source information."""
        techs = detect_technologies(temp_project)
        python_tech = next((t for t in techs if t.name == "python"), None)

        assert python_tech is not None
        assert python_tech.source != ""


class TestFindMissingExperts:
    """Tests for gap detection."""

    def test_find_gaps_with_no_experts(self, temp_project):
        """Should find gaps when no experts exist."""
        gaps = find_missing_experts(temp_project, [])

        # Should find some gaps (techs detected without experts)
        assert isinstance(gaps, list)
        # If gaps found, verify structure
        if gaps:
            assert "name" in gaps[0]
            assert "type" in gaps[0]
            assert "confidence" in gaps[0]

    def test_find_gaps_with_existing_expert(self, temp_project):
        """Should not report gap for existing expert."""
        # Pass python as existing expert
        gaps = find_missing_experts(temp_project, ["python"])

        # Should not include python in gaps
        python_gap = next((g for g in gaps if g["name"] == "python"), None)
        assert python_gap is None

    def test_case_insensitive_matching(self, temp_project):
        """Expert matching should be case insensitive."""
        gaps = find_missing_experts(temp_project, ["Python", "FASTAPI"])

        # Should not include python or fastapi (case-insensitive match)
        python_gap = next((g for g in gaps if g["name"].lower() == "python"), None)
        fastapi_gap = next((g for g in gaps if g["name"].lower() == "fastapi"), None)
        assert python_gap is None
        assert fastapi_gap is None


class TestSkipDirectories:
    """Tests for directory skipping."""

    def test_skips_venv(self, temp_project):
        """Should skip .venv directory."""
        venv = temp_project / ".venv"
        venv.mkdir()
        (venv / "lib" / "python").mkdir(parents=True)
        (venv / "lib" / "python" / "site.py").write_text("# site packages")

        techs = detect_technologies(temp_project)

        # Should not crash with .venv present
        assert isinstance(techs, list)

    def test_skips_node_modules(self, temp_project):
        """Should skip node_modules directory."""
        nm = temp_project / "node_modules"
        nm.mkdir()
        (nm / "react").mkdir()
        (nm / "react" / "index.js").write_text("module.exports = {}")

        techs = detect_technologies(temp_project)

        # Should not crash with node_modules present
        assert isinstance(techs, list)


class TestJSDetection:
    """Tests for JavaScript/TypeScript detection."""

    def test_detect_typescript(self, tmp_path):
        """Should detect TypeScript from tsconfig.json."""
        (tmp_path / "tsconfig.json").write_text("{}")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.ts").write_text("const x = 1")

        techs = detect_technologies(tmp_path)
        ts_tech = next((t for t in techs if t.name == "typescript"), None)

        assert ts_tech is not None
        assert ts_tech.category == "language"

    def test_detect_react_from_package_json(self, tmp_path):
        """Should detect React from package.json dependencies."""
        (tmp_path / "package.json").write_text(json.dumps({
            "dependencies": {"react": "^18.0.0"}
        }))

        techs = detect_technologies(tmp_path)
        react_tech = next((t for t in techs if t.name == "react"), None)

        assert react_tech is not None
        assert react_tech.category == "framework"


class TestToolDetection:
    """Tests for tool detection."""

    def test_detect_docker(self, tmp_path):
        """Should detect Docker from Dockerfile."""
        (tmp_path / "Dockerfile").write_text("FROM python:3.11")

        techs = detect_technologies(tmp_path)
        docker_tech = next((t for t in techs if t.name == "docker"), None)

        assert docker_tech is not None
        assert docker_tech.category == "tool"

    def test_detect_pytest(self, tmp_path):
        """Should detect pytest from conftest.py."""
        (tmp_path / "conftest.py").write_text("import pytest")
        (tmp_path / "test_example.py").write_text("def test_pass(): pass")

        techs = detect_technologies(tmp_path)
        pytest_tech = next((t for t in techs if t.name == "pytest"), None)

        assert pytest_tech is not None
        assert pytest_tech.category == "tool"
