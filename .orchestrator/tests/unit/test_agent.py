"""Unit tests for the Agent class."""
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.agent import Agent, AgentResult, _is_transient_error, _safe_get


class TestAgentResult:
    """Tests for AgentResult dataclass."""

    def test_agent_result_creation(self):
        """Test AgentResult can be created with all fields."""
        result = AgentResult(
            content="test content",
            agent_name="test_agent",
            success=True,
            files_created=["a.py", "b.py"],
            files_modified=["c.py"],
            commands_run=["npm install"],
            tokens_used=150,
        )
        assert result.content == "test content"
        assert result.agent_name == "test_agent"
        assert result.success is True
        assert result.files_created == ["a.py", "b.py"]
        assert result.files_modified == ["c.py"]
        assert result.commands_run == ["npm install"]
        assert result.tokens_used == 150

    def test_agent_result_defaults(self):
        """Test AgentResult has correct default values."""
        result = AgentResult(
            content="test",
            agent_name="test",
            success=True,
        )
        assert result.files_created == []
        assert result.files_modified == []
        assert result.commands_run == []
        assert result.tokens_used == 0
        assert result.error is None

    def test_agent_result_with_error(self):
        """Test AgentResult with error field."""
        result = AgentResult(
            content="",
            agent_name="failed_agent",
            success=False,
            error="Something went wrong",
        )
        assert result.success is False
        assert result.error == "Something went wrong"


class TestTransientErrorDetection:
    """Tests for transient error detection."""

    def test_timeout_is_transient(self):
        """Test timeout errors are detected as transient."""
        assert _is_transient_error("Operation timeout") is True
        assert _is_transient_error("TIMEOUT occurred") is True

    def test_connection_refused_is_transient(self):
        """Test connection refused is transient."""
        assert _is_transient_error("Connection refused by server") is True

    def test_rate_limit_is_transient(self):
        """Test rate limit errors are transient."""
        assert _is_transient_error("Rate limit exceeded") is True
        assert _is_transient_error("Error 429: Too many requests") is True

    def test_server_errors_are_transient(self):
        """Test 502/503 errors are transient."""
        assert _is_transient_error("Error 502: Bad Gateway") is True
        assert _is_transient_error("503 Service Unavailable") is True

    def test_regular_errors_not_transient(self):
        """Test regular errors are not transient."""
        assert _is_transient_error("File not found") is False
        assert _is_transient_error("Invalid syntax") is False
        assert _is_transient_error("Permission denied") is False


class TestSafeGet:
    """Tests for _safe_get helper function."""

    def test_safe_get_from_dict(self):
        """Test getting value from dict."""
        data = {"key": "value", "nested": {"inner": 42}}
        assert _safe_get(data, "key") == "value"
        assert _safe_get(data, "nested") == {"inner": 42}

    def test_safe_get_missing_key(self):
        """Test getting missing key returns default."""
        data = {"key": "value"}
        assert _safe_get(data, "missing") is None
        assert _safe_get(data, "missing", "default") == "default"

    def test_safe_get_from_non_dict(self):
        """Test getting from non-dict returns default."""
        assert _safe_get([1, 2, 3], "key") is None
        assert _safe_get("string", "key", "default") == "default"
        assert _safe_get(None, "key") is None


class TestAgentLoading:
    """Tests for Agent loading from files."""

    def test_agent_load_success(self, project_root):
        """Test agent loads from markdown file."""
        agent = Agent.load("scout", project_root)
        assert agent.name == "scout"
        assert agent.system_prompt is not None
        assert len(agent.system_prompt) > 0

    def test_agent_load_strips_frontmatter(self, project_root):
        """Test frontmatter is stripped from system prompt."""
        agent = Agent.load("scout", project_root)
        # System prompt should not contain frontmatter markers
        assert not agent.system_prompt.startswith("---")
        assert "name: scout" not in agent.system_prompt

    def test_agent_load_not_found(self, project_root):
        """Test loading non-existent agent raises error."""
        with pytest.raises(FileNotFoundError):
            Agent.load("nonexistent_agent", project_root)

    def test_agent_repr(self, project_root):
        """Test agent string representation."""
        agent = Agent.load("scout", project_root)
        repr_str = repr(agent)
        assert "scout" in repr_str
        assert "agentic=False" in repr_str

    def test_agentic_agent_detection(self, project_root):
        """Test agentic agents are correctly identified."""
        builder = Agent.load("builder", project_root)
        scout = Agent.load("scout", project_root)

        assert "builder" in Agent.AGENTIC_AGENTS
        assert "scout" not in Agent.AGENTIC_AGENTS


class TestAgentPromptBuilding:
    """Tests for Agent prompt building."""

    def test_build_prompt_basic(self, project_root):
        """Test basic prompt building."""
        agent = Agent.load("scout", project_root)
        prompt = agent._build_prompt("Explore the codebase")

        assert "<system>" in prompt
        assert "</system>" in prompt
        assert "Explore the codebase" in prompt

    def test_build_prompt_with_context(self, project_root):
        """Test prompt building with context."""
        agent = Agent.load("scout", project_root)
        prompt = agent._build_prompt("Do something", context="Previous context here")

        assert "## Context" in prompt
        assert "Previous context here" in prompt
        assert "## Task" in prompt
        assert "Do something" in prompt


class TestAgentExecution:
    """Tests for Agent execution."""

    def test_run_print_mode_success(self, project_root, mock_subprocess_success):
        """Test successful agent run in print mode."""
        mock_subprocess_success.stdout = "Agent response"

        agent = Agent.load("scout", project_root)
        result = agent.run("Explore codebase")

        assert result.success is True
        assert result.content == "Agent response"
        assert result.agent_name == "scout"

    def test_run_print_mode_failure(self, project_root, mock_subprocess_failure):
        """Test failed agent run in print mode."""
        agent = Agent.load("scout", project_root)
        result = agent.run("Explore codebase")

        assert result.success is False
        assert result.error is not None

    def test_run_auto_detects_agentic(self, project_root):
        """Test that builder auto-runs in agentic mode."""
        with patch.object(Agent, 'run_agentic') as mock_agentic:
            mock_agentic.return_value = AgentResult(
                content="Built",
                agent_name="builder",
                success=True,
            )

            agent = Agent.load("builder", project_root)
            agent.run("Build something")

            mock_agentic.assert_called_once()

    @pytest.mark.timeout(10)
    def test_run_handles_timeout(self, project_root, monkeypatch):
        """Test agent handles subprocess timeout."""
        def mock_run(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="claude", timeout=300)

        monkeypatch.setattr("subprocess.run", mock_run)

        agent = Agent.load("scout", project_root)
        result = agent.run("Explore", max_retries=1)

        assert result.success is False
        assert "timed out" in result.error.lower()

    def test_run_handles_cli_not_found(self, project_root, monkeypatch):
        """Test agent handles missing Claude CLI."""
        def mock_run(*args, **kwargs):
            raise FileNotFoundError("claude not found")

        monkeypatch.setattr("subprocess.run", mock_run)

        agent = Agent.load("scout", project_root)
        result = agent.run("Explore")

        assert result.success is False
        assert "not found" in result.error.lower()


class TestAgenticExecution:
    """Tests for agentic mode execution."""

    def test_run_agentic_success(self, project_root, monkeypatch):
        """Test successful agentic execution."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "result": "Files created",
            "messages": [
                {"type": "tool_use", "name": "Write", "input": {"file_path": "test.py"}},
            ],
            "usage": {"input_tokens": 100, "output_tokens": 50},
        })
        mock_result.stderr = ""

        monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: mock_result)

        agent = Agent.load("builder", project_root)
        result = agent.run_agentic("Create a file")

        assert result.success is True
        assert "test.py" in result.files_created
        assert result.tokens_used == 150

    def test_run_agentic_parses_file_operations(self, project_root, monkeypatch):
        """Test agentic mode correctly parses file operations."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "result": "Modified files",
            "messages": [
                {"type": "tool_use", "name": "Write", "input": {"file_path": "new.py"}},
                {"type": "tool_use", "name": "Edit", "input": {"file_path": "existing.py"}},
                {"type": "tool_use", "name": "Bash", "input": {"command": "npm install"}},
            ],
        })
        mock_result.stderr = ""

        monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: mock_result)

        agent = Agent.load("builder", project_root)
        result = agent.run_agentic("Do work")

        assert "new.py" in result.files_created
        assert "existing.py" in result.files_modified
        assert "npm install" in result.commands_run

    def test_run_agentic_handles_non_json_output(self, project_root, monkeypatch):
        """Test agentic mode handles non-JSON output gracefully."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Plain text response, not JSON"
        mock_result.stderr = ""

        monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: mock_result)

        agent = Agent.load("builder", project_root)
        result = agent.run_agentic("Do work")

        # Should still succeed with raw content
        assert result.success is True
        assert result.content == "Plain text response, not JSON"


class TestAgentRetries:
    """Tests for agent retry logic."""

    def test_retries_on_transient_error(self, project_root, monkeypatch):
        """Test agent retries on transient errors."""
        call_count = 0

        def mock_run(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                result = MagicMock()
                result.returncode = 1
                result.stderr = "Rate limit exceeded"
                result.stdout = ""
                return result
            else:
                result = MagicMock()
                result.returncode = 0
                result.stdout = "Success after retries"
                result.stderr = ""
                return result

        monkeypatch.setattr("subprocess.run", mock_run)

        agent = Agent.load("scout", project_root)
        result = agent.run("Test", max_retries=3, retry_delay=0.01)

        assert result.success is True
        assert call_count == 3

    def test_no_retry_on_permanent_error(self, project_root, monkeypatch):
        """Test agent doesn't retry permanent errors."""
        call_count = 0

        def mock_run(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            result.returncode = 1
            result.stderr = "Invalid syntax error"  # Not transient
            result.stdout = ""
            return result

        monkeypatch.setattr("subprocess.run", mock_run)

        agent = Agent.load("scout", project_root)
        result = agent.run("Test", max_retries=3)

        assert result.success is False
        assert call_count == 1  # Only one attempt
