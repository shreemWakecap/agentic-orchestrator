"""Unit tests for the MCP agent module."""
import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

# Ensure orchestrator is in path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.mcp_agent import MCPAgent, MCPAgentConfig, MCPAgentPool
from core.mcp_client import MCPClient, StreamEvent
from core.agent import AgentResult, Agent


class TestMCPAgentConfig:
    """Tests for MCPAgentConfig dataclass."""

    def test_config_creation(self, tmp_path):
        """Test MCPAgentConfig can be created."""
        config = MCPAgentConfig(
            name="test_agent",
            prompt_file=tmp_path / "test.md"
        )
        assert config.name == "test_agent"
        assert config.timeout == 300
        assert config.max_tokens == 4096

    def test_config_with_custom_values(self, tmp_path):
        """Test MCPAgentConfig with custom values."""
        config = MCPAgentConfig(
            name="builder",
            prompt_file=tmp_path / "builder.md",
            timeout=600,
            max_tokens=8192,
            tools=["Write", "Edit", "Bash"]
        )
        assert config.timeout == 600
        assert config.max_tokens == 8192
        assert "Write" in config.tools


class TestMCPAgent:
    """Tests for MCPAgent class."""

    @pytest.fixture
    def mock_client(self):
        """Create mock MCP client."""
        return MagicMock(spec=MCPClient)

    @pytest.fixture
    def agent_prompt_file(self, tmp_path):
        """Create agent prompt file."""
        prompt_file = tmp_path / "test_agent.md"
        prompt_file.write_text("""---
name: test_agent
mode: print
---

You are a test agent. Follow instructions carefully.
""")
        return prompt_file

    def test_agent_creation(self, mock_client, agent_prompt_file):
        """Test MCPAgent can be created."""
        config = MCPAgentConfig(
            name="test_agent",
            prompt_file=agent_prompt_file
        )
        agent = MCPAgent(config, mock_client)

        assert agent.config.name == "test_agent"
        assert "test agent" in agent.prompt.lower()

    def test_agent_strips_frontmatter(self, mock_client, agent_prompt_file):
        """Test agent strips YAML frontmatter from prompt."""
        config = MCPAgentConfig(
            name="test_agent",
            prompt_file=agent_prompt_file
        )
        agent = MCPAgent(config, mock_client)

        assert "---" not in agent.prompt
        assert "name:" not in agent.prompt

    def test_agent_handles_missing_prompt_file(self, mock_client, tmp_path):
        """Test agent handles missing prompt file."""
        config = MCPAgentConfig(
            name="nonexistent",
            prompt_file=tmp_path / "nonexistent.md"
        )
        agent = MCPAgent(config, mock_client)

        assert agent.prompt == ""

    def test_agent_repr(self, mock_client, agent_prompt_file):
        """Test agent string representation."""
        config = MCPAgentConfig(
            name="test_agent",
            prompt_file=agent_prompt_file
        )
        agent = MCPAgent(config, mock_client)

        repr_str = repr(agent)
        assert "MCPAgent" in repr_str
        assert "test_agent" in repr_str

    def test_agentic_agent_detection(self, mock_client, tmp_path):
        """Test agentic agent detection."""
        # Create prompt for builder (agentic agent)
        prompt_file = tmp_path / "builder.md"
        prompt_file.write_text("You are a builder agent.")

        config = MCPAgentConfig(
            name="builder",
            prompt_file=prompt_file
        )
        agent = MCPAgent(config, mock_client)

        assert agent.is_agentic is True

    @pytest.mark.asyncio
    async def test_agent_run_success(self, mock_client, agent_prompt_file):
        """Test successful agent execution."""
        config = MCPAgentConfig(
            name="test_agent",
            prompt_file=agent_prompt_file,
            timeout=30
        )
        agent = MCPAgent(config, mock_client)

        # Mock streaming response
        async def mock_call_agent(*args, **kwargs):
            yield StreamEvent.token("Hello ", tokens=5)
            yield StreamEvent.token("World!", tokens=10)
            yield StreamEvent.complete({"total_tokens": 10})

        mock_client.call_agent = mock_call_agent

        result = await agent.run("Say hello")

        assert result.success is True
        assert result.content == "Hello World!"
        assert result.tokens_used == 10

    @pytest.mark.asyncio
    async def test_agent_run_with_context(self, mock_client, agent_prompt_file):
        """Test agent execution with context."""
        config = MCPAgentConfig(
            name="test_agent",
            prompt_file=agent_prompt_file
        )
        agent = MCPAgent(config, mock_client)

        async def mock_call_agent(*args, **kwargs):
            yield StreamEvent.token("OK", tokens=2)
            yield StreamEvent.complete({"total_tokens": 2})

        mock_client.call_agent = mock_call_agent

        result = await agent.run("Do something", context="Additional context here")

        assert result.success is True
        assert result.content == "OK"

    @pytest.mark.asyncio
    async def test_agent_run_tracks_tool_use(self, mock_client, agent_prompt_file):
        """Test agent tracks tool usage."""
        config = MCPAgentConfig(
            name="test_agent",
            prompt_file=agent_prompt_file
        )
        agent = MCPAgent(config, mock_client)

        async def mock_call_agent(*args, **kwargs):
            yield StreamEvent.tool_use("Write", {"path": "new_file.py"})
            yield StreamEvent.tool_use("Edit", {"path": "existing.py"})
            yield StreamEvent.tool_use("Bash", {"command": "pytest"})
            yield StreamEvent.token("Done", tokens=5)
            yield StreamEvent.complete({"total_tokens": 5})

        mock_client.call_agent = mock_call_agent

        result = await agent.run("Create and edit files")

        assert "new_file.py" in result.files_created
        assert "existing.py" in result.files_modified
        assert "pytest" in result.commands_run

    @pytest.mark.asyncio
    async def test_agent_run_handles_error_event(self, mock_client, agent_prompt_file):
        """Test agent handles error events."""
        config = MCPAgentConfig(
            name="test_agent",
            prompt_file=agent_prompt_file
        )
        agent = MCPAgent(config, mock_client)

        async def mock_call_agent(*args, **kwargs):
            yield StreamEvent.token("Starting...", tokens=2)
            yield StreamEvent.error("Something went wrong")

        mock_client.call_agent = mock_call_agent

        result = await agent.run("Do something risky")

        assert result.success is False
        assert "Something went wrong" in result.error
        assert result.content == "Starting..."  # Partial content preserved

    @pytest.mark.asyncio
    async def test_agent_run_handles_timeout(self, mock_client, agent_prompt_file):
        """Test agent handles timeout."""
        config = MCPAgentConfig(
            name="test_agent",
            prompt_file=agent_prompt_file,
            timeout=1  # 1 second timeout
        )
        agent = MCPAgent(config, mock_client)

        async def mock_call_agent(*args, **kwargs):
            yield StreamEvent.token("Starting", tokens=1)
            await asyncio.sleep(5)  # Will timeout
            yield StreamEvent.complete({})

        mock_client.call_agent = mock_call_agent

        result = await agent.run("Slow task")

        assert result.success is False
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_agent_run_handles_cancellation(self, mock_client, agent_prompt_file):
        """Test agent handles cancellation."""
        config = MCPAgentConfig(
            name="test_agent",
            prompt_file=agent_prompt_file
        )
        agent = MCPAgent(config, mock_client)

        async def mock_call_agent(*args, **kwargs):
            yield StreamEvent.token("Start", tokens=1)
            raise asyncio.CancelledError()

        mock_client.call_agent = mock_call_agent

        result = await agent.run("Task to cancel")

        assert result.success is False
        assert "cancelled" in result.error.lower()

    @pytest.mark.asyncio
    async def test_agent_run_handles_exception(self, mock_client, agent_prompt_file):
        """Test agent handles unexpected exceptions."""
        config = MCPAgentConfig(
            name="test_agent",
            prompt_file=agent_prompt_file
        )
        agent = MCPAgent(config, mock_client)

        async def mock_call_agent(*args, **kwargs):
            raise RuntimeError("Unexpected error")
            yield  # Never reached

        mock_client.call_agent = mock_call_agent

        result = await agent.run("Task")

        assert result.success is False
        assert "Unexpected error" in result.error

    @pytest.mark.asyncio
    async def test_agent_run_with_progress_callback(self, mock_client, agent_prompt_file):
        """Test agent calls progress callback."""
        config = MCPAgentConfig(
            name="test_agent",
            prompt_file=agent_prompt_file
        )
        agent = MCPAgent(config, mock_client)

        progress_events = []

        async def mock_call_agent(*args, on_progress=None, **kwargs):
            events = [
                StreamEvent.progress("Loading...", percent=50),
                StreamEvent.token("Done", tokens=1),
                StreamEvent.complete({})
            ]
            for event in events:
                if on_progress:
                    on_progress(event)
                yield event

        mock_client.call_agent = mock_call_agent

        def on_progress_callback(event):
            progress_events.append(event)

        await agent.run("Task", on_progress=on_progress_callback)

        assert len(progress_events) == 3


class TestMCPAgentPool:
    """Tests for MCPAgentPool class."""

    @pytest.fixture
    def mock_client(self):
        """Create mock MCP client."""
        return MagicMock(spec=MCPClient)

    @pytest.fixture
    def agents_dir(self, tmp_path):
        """Create agents directory with test prompts."""
        agents = tmp_path / "agents"
        agents.mkdir()

        (agents / "scout.md").write_text("You are a scout agent.")
        (agents / "builder.md").write_text("You are a builder agent.")

        return agents

    def test_pool_initialization(self, mock_client, agents_dir):
        """Test MCPAgentPool can be initialized."""
        pool = MCPAgentPool(mock_client, agents_dir)

        assert pool.client == mock_client
        assert pool.agents_dir == agents_dir

    def test_pool_register_agent(self, mock_client, agents_dir):
        """Test registering an agent."""
        pool = MCPAgentPool(mock_client, agents_dir)

        agent = pool.register("scout", timeout=120)

        assert agent is not None
        assert agent.config.name == "scout"
        assert agent.config.timeout == 120

    def test_pool_get_agent(self, mock_client, agents_dir):
        """Test getting registered agent."""
        pool = MCPAgentPool(mock_client, agents_dir)
        pool.register("scout")

        agent = pool.get("scout")
        assert agent is not None
        assert agent.config.name == "scout"

        # Non-existent agent
        assert pool.get("nonexistent") is None

    def test_pool_list_agents(self, mock_client, agents_dir):
        """Test listing registered agents."""
        pool = MCPAgentPool(mock_client, agents_dir)
        pool.register("scout")
        pool.register("builder")

        agents = pool.list_agents()

        assert "scout" in agents
        assert "builder" in agents

    @pytest.mark.asyncio
    async def test_pool_run_agent(self, mock_client, agents_dir):
        """Test running agent through pool."""
        pool = MCPAgentPool(mock_client, agents_dir)
        pool.register("scout")

        async def mock_call_agent(*args, **kwargs):
            yield StreamEvent.token("Result", tokens=5)
            yield StreamEvent.complete({"total_tokens": 5})

        mock_client.call_agent = mock_call_agent

        result = await pool.run("scout", "Explore")

        assert result.success is True
        assert result.content == "Result"

    @pytest.mark.asyncio
    async def test_pool_run_unregistered_agent(self, mock_client, agents_dir):
        """Test running unregistered agent fails gracefully."""
        pool = MCPAgentPool(mock_client, agents_dir)

        result = await pool.run("nonexistent", "Task")

        assert result.success is False
        assert "not registered" in result.error
