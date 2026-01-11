"""Unit tests for the MCP client module."""
import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

# Ensure orchestrator is in path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.mcp_client import (
    MCPMessage,
    StreamEvent,
    MCPClient,
    HTTPSSETransport,
    StdioTransport,
)


class TestMCPMessage:
    """Tests for MCPMessage dataclass."""

    def test_message_creation(self):
        """Test MCPMessage can be created with defaults."""
        msg = MCPMessage()
        assert msg.jsonrpc == "2.0"
        assert msg.id is None
        assert msg.method is None

    def test_message_with_values(self):
        """Test MCPMessage with custom values."""
        msg = MCPMessage(
            id=1,
            method="tools/call",
            params={"name": "test", "arguments": {}}
        )
        assert msg.id == 1
        assert msg.method == "tools/call"
        assert msg.params["name"] == "test"

    def test_message_to_dict(self):
        """Test MCPMessage serialization."""
        msg = MCPMessage(
            id=1,
            method="initialize",
            params={"version": "1.0"}
        )
        d = msg.to_dict()

        assert d["jsonrpc"] == "2.0"
        assert d["id"] == 1
        assert d["method"] == "initialize"
        assert "result" not in d  # None values excluded

    def test_message_from_dict(self):
        """Test MCPMessage deserialization."""
        data = {
            "jsonrpc": "2.0",
            "id": 42,
            "result": {"content": "test"}
        }
        msg = MCPMessage.from_dict(data)

        assert msg.id == 42
        assert msg.result["content"] == "test"
        assert msg.method is None


class TestStreamEvent:
    """Tests for StreamEvent dataclass."""

    def test_event_creation(self):
        """Test StreamEvent can be created."""
        event = StreamEvent(event_type="token", data={"text": "Hello"})
        assert event.event_type == "token"
        assert event.data["text"] == "Hello"

    def test_token_factory(self):
        """Test StreamEvent.token factory method."""
        event = StreamEvent.token("world", tokens=10)
        assert event.event_type == "token"
        assert event.data["text"] == "world"
        assert event.tokens_so_far == 10

    def test_tool_use_factory(self):
        """Test StreamEvent.tool_use factory method."""
        event = StreamEvent.tool_use("Write", {"path": "test.py"})
        assert event.event_type == "tool_use"
        assert event.data["tool"] == "Write"

    def test_progress_factory(self):
        """Test StreamEvent.progress factory method."""
        event = StreamEvent.progress("Loading...", percent=50)
        assert event.event_type == "progress"
        assert event.data["message"] == "Loading..."
        assert event.data["percent"] == 50

    def test_complete_factory(self):
        """Test StreamEvent.complete factory method."""
        event = StreamEvent.complete({"total_tokens": 100})
        assert event.event_type == "complete"
        assert event.data["usage"]["total_tokens"] == 100

    def test_error_factory(self):
        """Test StreamEvent.error factory method."""
        event = StreamEvent.error("Something went wrong", code=500)
        assert event.event_type == "error"
        assert event.data["message"] == "Something went wrong"
        assert event.data["code"] == 500


class TestMCPClient:
    """Tests for MCPClient class."""

    def test_client_initialization(self):
        """Test MCPClient can be initialized."""
        client = MCPClient(
            server_url="http://localhost:3000",
            api_key="test-key"
        )
        assert client.server_url == "http://localhost:3000"
        assert client.api_key == "test-key"
        assert not client.connected

    def test_client_next_id(self):
        """Test message ID generation."""
        client = MCPClient()
        id1 = client._next_id()
        id2 = client._next_id()
        assert id2 == id1 + 1

    @pytest.mark.asyncio
    async def test_client_context_manager(self):
        """Test MCPClient as async context manager."""
        with patch.object(HTTPSSETransport, 'connect', new_callable=AsyncMock, return_value=True):
            with patch.object(HTTPSSETransport, 'send', new_callable=AsyncMock):
                with patch.object(HTTPSSETransport, 'disconnect', new_callable=AsyncMock):
                    async with MCPClient() as client:
                        assert client.connected

    def test_client_unknown_transport_raises(self):
        """Test unknown transport type raises error."""
        client = MCPClient(transport_type="unknown")
        with pytest.raises(ValueError, match="Unknown transport"):
            asyncio.run(client.connect())


class TestHTTPSSETransport:
    """Tests for HTTP SSE transport."""

    def test_transport_initialization(self):
        """Test HTTPSSETransport can be initialized."""
        transport = HTTPSSETransport(
            base_url="http://localhost:3000/",
            api_key="test-key"
        )
        assert transport.base_url == "http://localhost:3000"  # Trailing slash stripped
        assert transport.api_key == "test-key"

    @pytest.mark.asyncio
    async def test_transport_connect(self):
        """Test transport connection."""
        transport = HTTPSSETransport("http://localhost:3000")
        with patch("httpx.AsyncClient") as mock_client:
            result = await transport.connect()
            assert result is True
            assert transport._client is not None

    @pytest.mark.asyncio
    async def test_transport_disconnect(self):
        """Test transport disconnection."""
        transport = HTTPSSETransport("http://localhost:3000")

        # Mock the client
        mock_client = AsyncMock()
        transport._client = mock_client

        await transport.disconnect()

        mock_client.aclose.assert_called_once()
        assert transport._client is None


class TestStdioTransport:
    """Tests for Stdio transport."""

    def test_transport_initialization(self):
        """Test StdioTransport can be initialized."""
        transport = StdioTransport(["python", "-m", "mcp_server"])
        assert transport.server_command == ["python", "-m", "mcp_server"]
        assert transport.process is None

    @pytest.mark.asyncio
    async def test_transport_start_process(self):
        """Test starting server process."""
        transport = StdioTransport(["echo", "test"])

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_create:
            mock_process = MagicMock()
            mock_process.stdout = AsyncMock()
            mock_process.stdin = MagicMock()
            mock_process.stdin.write = MagicMock()
            mock_process.stdin.drain = AsyncMock()
            mock_create.return_value = mock_process

            result = await transport.connect()

            assert result is True
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_transport_send_message(self):
        """Test sending message to server."""
        transport = StdioTransport(["echo"])

        # Mock process
        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stdin.write = MagicMock()
        mock_process.stdin.drain = AsyncMock()
        transport.process = mock_process

        msg = MCPMessage(id=1, method="test")
        await transport.send(msg)

        mock_process.stdin.write.assert_called_once()
        mock_process.stdin.drain.assert_called_once()


class TestMCPClientIntegration:
    """Integration-style tests for MCPClient."""

    @pytest.mark.asyncio
    async def test_call_agent_not_connected_raises(self):
        """Test calling agent when not connected raises error."""
        client = MCPClient()

        with pytest.raises(RuntimeError, match="not connected"):
            async for _ in client.call_agent("test", "message"):
                pass

    @pytest.mark.asyncio
    async def test_call_agent_with_mocked_transport(self):
        """Test calling agent with mocked transport."""
        client = MCPClient()
        client._connected = True

        # Mock transport
        mock_transport = MagicMock()

        async def mock_stream(*args, **kwargs):
            yield StreamEvent.token("Hello", tokens=5)
            yield StreamEvent.token(" World", tokens=10)
            yield StreamEvent.complete({"total_tokens": 10})

        mock_transport.stream_request = mock_stream
        client._transport = mock_transport

        events = []
        progress_events = []

        def on_progress(event):
            progress_events.append(event)

        async for event in client.call_agent(
            "test",
            "Say hello",
            on_progress=on_progress
        ):
            events.append(event)

        assert len(events) == 3
        assert events[0].event_type == "token"
        assert events[2].event_type == "complete"
        assert len(progress_events) == 3  # Callback also called
