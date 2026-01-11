"""MCP Client for real-time agent communication.

Implements the Model Context Protocol (MCP) client for streaming
responses from Claude API with real-time progress updates.

Supports multiple transport options:
- HTTP+SSE: Server-Sent Events over HTTP (default)
- Stdio: Direct stdin/stdout communication with local server
- WebSocket: Bidirectional WebSocket connection
"""

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional, Callable, Any
from pathlib import Path


@dataclass
class MCPMessage:
    """MCP protocol message (JSON-RPC 2.0)."""
    jsonrpc: str = "2.0"
    id: Optional[int] = None
    method: Optional[str] = None
    params: Optional[dict] = None
    result: Optional[dict] = None
    error: Optional[dict] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        d = {"jsonrpc": self.jsonrpc}
        if self.id is not None:
            d["id"] = self.id
        if self.method is not None:
            d["method"] = self.method
        if self.params is not None:
            d["params"] = self.params
        if self.result is not None:
            d["result"] = self.result
        if self.error is not None:
            d["error"] = self.error
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "MCPMessage":
        """Create MCPMessage from dictionary."""
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            id=data.get("id"),
            method=data.get("method"),
            params=data.get("params"),
            result=data.get("result"),
            error=data.get("error")
        )


@dataclass
class StreamEvent:
    """Streaming event from MCP server."""
    event_type: str  # "progress", "token", "tool_use", "complete", "error"
    data: dict = field(default_factory=dict)
    tokens_so_far: int = 0

    @classmethod
    def token(cls, text: str, tokens: int = 0) -> "StreamEvent":
        """Create token event."""
        return cls(event_type="token", data={"text": text}, tokens_so_far=tokens)

    @classmethod
    def tool_use(cls, tool: str, result: Any) -> "StreamEvent":
        """Create tool use event."""
        return cls(event_type="tool_use", data={"tool": tool, "result": result})

    @classmethod
    def progress(cls, message: str, percent: int = 0) -> "StreamEvent":
        """Create progress event."""
        return cls(event_type="progress", data={"message": message, "percent": percent})

    @classmethod
    def complete(cls, usage: dict) -> "StreamEvent":
        """Create completion event."""
        return cls(event_type="complete", data={"usage": usage})

    @classmethod
    def error(cls, message: str, code: int = -1) -> "StreamEvent":
        """Create error event."""
        return cls(event_type="error", data={"message": message, "code": code})


class MCPTransport(ABC):
    """Base class for MCP transport implementations."""

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection."""
        pass

    @abstractmethod
    async def disconnect(self):
        """Close connection."""
        pass

    @abstractmethod
    async def send(self, message: MCPMessage) -> None:
        """Send message to server."""
        pass

    @abstractmethod
    async def receive(self) -> AsyncIterator[MCPMessage]:
        """Receive messages from server."""
        pass

    @abstractmethod
    async def stream_request(self, request: MCPMessage) -> AsyncIterator[StreamEvent]:
        """Send request and stream response events."""
        pass


class HTTPSSETransport(MCPTransport):
    """Transport via HTTP with Server-Sent Events for streaming."""

    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client = None

    async def connect(self) -> bool:
        """Initialize HTTP client."""
        import httpx
        self._client = httpx.AsyncClient(timeout=300.0)
        return True

    async def disconnect(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def send(self, message: MCPMessage) -> None:
        """Send non-streaming request."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        await self._client.post(
            f"{self.base_url}/mcp",
            json=message.to_dict(),
            headers=headers
        )

    async def receive(self) -> AsyncIterator[MCPMessage]:
        """Not used for HTTP transport - use stream_request instead."""
        return
        yield  # Make this a generator

    async def stream_request(self, request: MCPMessage) -> AsyncIterator[StreamEvent]:
        """Make HTTP request with SSE streaming response."""
        headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with self._client.stream(
            "POST",
            f"{self.base_url}/mcp",
            json=request.to_dict(),
            headers=headers
        ) as response:
            async for line in response.aiter_lines():
                line = line.strip()
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        yield StreamEvent(
                            event_type=data.get("event_type", "unknown"),
                            data=data.get("data", {}),
                            tokens_so_far=data.get("tokens_so_far", 0)
                        )
                    except json.JSONDecodeError:
                        continue


class StdioTransport(MCPTransport):
    """Transport via stdin/stdout to local MCP server process."""

    def __init__(self, server_command: list[str]):
        self.server_command = server_command
        self.process = None
        self._read_task = None
        self._message_queue = asyncio.Queue()

    async def connect(self) -> bool:
        """Start MCP server process."""
        self.process = await asyncio.create_subprocess_exec(
            *self.server_command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        # Start reading task
        self._read_task = asyncio.create_task(self._read_stdout())
        return True

    async def disconnect(self):
        """Stop MCP server process."""
        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass

        if self.process:
            self.process.terminate()
            await self.process.wait()
            self.process = None

    async def _read_stdout(self):
        """Background task to read stdout."""
        while True:
            line = await self.process.stdout.readline()
            if not line:
                break
            try:
                message = MCPMessage.from_dict(json.loads(line.decode()))
                await self._message_queue.put(message)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

    async def send(self, message: MCPMessage) -> None:
        """Send message to server."""
        data = json.dumps(message.to_dict()) + "\n"
        self.process.stdin.write(data.encode())
        await self.process.stdin.drain()

    async def receive(self) -> AsyncIterator[MCPMessage]:
        """Receive messages from server."""
        while True:
            message = await self._message_queue.get()
            yield message

    async def stream_request(self, request: MCPMessage) -> AsyncIterator[StreamEvent]:
        """Send request and stream response events."""
        await self.send(request)

        async for message in self.receive():
            if message.method == "notifications/progress":
                params = message.params or {}
                yield StreamEvent(
                    event_type=params.get("event_type", "progress"),
                    data=params.get("data", {}),
                    tokens_so_far=params.get("tokens_so_far", 0)
                )
            elif message.id == request.id:
                # Final response
                if message.result:
                    usage = message.result.get("usage", {})
                    yield StreamEvent.complete(usage)
                elif message.error:
                    yield StreamEvent.error(message.error.get("message", "Unknown error"))
                break


class MCPClient:
    """Client for communicating with MCP server."""

    def __init__(
        self,
        server_url: str = "http://localhost:3000",
        api_key: Optional[str] = None,
        transport_type: str = "http-sse"
    ):
        """
        Initialize MCP client.

        Args:
            server_url: URL for HTTP transport or command for stdio
            api_key: API key for authentication
            transport_type: "http-sse" or "stdio"
        """
        self.server_url = server_url
        self.api_key = api_key
        self._message_id = 0
        self._transport: Optional[MCPTransport] = None
        self._transport_type = transport_type
        self._connected = False
        self._capabilities: dict = {}

    async def connect(self) -> bool:
        """Establish connection to MCP server."""
        if self._transport_type == "http-sse":
            self._transport = HTTPSSETransport(self.server_url, self.api_key)
        elif self._transport_type == "stdio":
            self._transport = StdioTransport(self.server_url.split())
        else:
            raise ValueError(f"Unknown transport type: {self._transport_type}")

        self._connected = await self._transport.connect()

        if self._connected:
            # Send initialize message
            init_request = MCPMessage(
                id=self._next_id(),
                method="initialize",
                params={
                    "protocolVersion": "2024-11-05",
                    "clientInfo": {
                        "name": "orchestrator",
                        "version": "1.0.0"
                    }
                }
            )
            await self._transport.send(init_request)

        return self._connected

    async def disconnect(self):
        """Close connection to MCP server."""
        if self._transport:
            await self._transport.disconnect()
            self._transport = None
        self._connected = False

    async def call_agent(
        self,
        agent_name: str,
        message: str,
        context: Optional[str] = None,
        tools: Optional[list[str]] = None,
        on_progress: Optional[Callable[[StreamEvent], None]] = None
    ) -> AsyncIterator[StreamEvent]:
        """
        Call an agent and stream responses.

        Args:
            agent_name: Name of agent to invoke
            message: User message/prompt
            context: Additional context
            tools: List of allowed tools (for agentic agents)
            on_progress: Callback for progress events

        Yields:
            StreamEvent objects as response streams
        """
        if not self._connected:
            raise RuntimeError("Client not connected")

        request = MCPMessage(
            id=self._next_id(),
            method="tools/call",
            params={
                "name": agent_name,
                "arguments": {
                    "message": message,
                    "context": context or "",
                    "tools": tools or []
                }
            }
        )

        async for event in self._transport.stream_request(request):
            if on_progress:
                on_progress(event)
            yield event

    def _next_id(self) -> int:
        """Generate next message ID."""
        self._message_id += 1
        return self._message_id

    @property
    def connected(self) -> bool:
        """Check if client is connected."""
        return self._connected

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
