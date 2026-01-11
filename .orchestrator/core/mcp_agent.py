"""MCP-enabled agent implementation.

Provides agents that communicate via MCP protocol with streaming
response handling and tool use tracking.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional, Callable, List
from pathlib import Path

from .agent import AgentResult, Agent
from .mcp_client import MCPClient, StreamEvent


@dataclass
class MCPAgentConfig:
    """Configuration for MCP agent."""
    name: str
    prompt_file: Path
    timeout: int = 300  # 5 minutes
    max_tokens: int = 4096
    tools: List[str] = field(default_factory=list)  # Allowed tools for agentic agents
    model: str = "claude-sonnet-4-20250514"


class MCPAgent:
    """Agent that communicates via MCP protocol."""

    def __init__(
        self,
        config: MCPAgentConfig,
        client: MCPClient
    ):
        """
        Initialize MCP agent.

        Args:
            config: Agent configuration
            client: MCP client for communication
        """
        self.config = config
        self.client = client
        self.prompt = self._load_prompt()
        self._is_agentic = config.name in Agent.AGENTIC_AGENTS

    def _load_prompt(self) -> str:
        """Load agent prompt from markdown file."""
        if not self.config.prompt_file.exists():
            return ""

        content = self.config.prompt_file.read_text(encoding="utf-8")
        # Strip YAML frontmatter if present
        if content.startswith("---"):
            parts = content.split("---", 2)
            return parts[2].strip() if len(parts) > 2 else content
        return content

    async def run(
        self,
        message: str,
        context: Optional[str] = None,
        on_progress: Optional[Callable[[StreamEvent], None]] = None
    ) -> AgentResult:
        """
        Execute agent via MCP and return result.

        Args:
            message: The task/prompt for the agent
            context: Additional context to include
            on_progress: Callback for streaming progress

        Returns:
            AgentResult with response and metadata
        """
        # Build full message with prompt and context
        full_message = f"{self.prompt}\n\n{message}"
        if context:
            full_message = f"{context}\n\n{full_message}"

        tools = self.config.tools if self._is_agentic else None

        content_parts: List[str] = []
        total_tokens = 0
        files_created: List[str] = []
        files_modified: List[str] = []
        commands_run: List[str] = []

        try:
            async with asyncio.timeout(self.config.timeout):
                async for event in self.client.call_agent(
                    agent_name=self.config.name,
                    message=full_message,
                    tools=tools,
                    on_progress=on_progress
                ):
                    if event.event_type == "token":
                        text = event.data.get("text", "")
                        content_parts.append(text)
                        total_tokens = event.tokens_so_far

                    elif event.event_type == "tool_use":
                        tool_data = event.data
                        tool_name = tool_data.get("tool", "")
                        tool_result = tool_data.get("result", {})
                        if isinstance(tool_result, dict):
                            tool_path = tool_result.get("path", "")
                            tool_command = tool_result.get("command", "")
                        else:
                            tool_path = ""
                            tool_command = ""

                        if tool_name == "Write":
                            if tool_path:
                                files_created.append(tool_path)
                        elif tool_name == "Edit":
                            if tool_path:
                                files_modified.append(tool_path)
                        elif tool_name == "Bash":
                            if tool_command:
                                commands_run.append(tool_command)

                    elif event.event_type == "complete":
                        usage = event.data.get("usage", {})
                        total_tokens = usage.get("total_tokens", total_tokens)

                    elif event.event_type == "error":
                        return AgentResult(
                            content="".join(content_parts),
                            agent_name=self.config.name,
                            success=False,
                            error=event.data.get("message", "Unknown error"),
                            files_created=files_created,
                            files_modified=files_modified,
                            commands_run=commands_run,
                            tokens_used=total_tokens
                        )

            return AgentResult(
                content="".join(content_parts),
                agent_name=self.config.name,
                success=True,
                files_created=files_created,
                files_modified=files_modified,
                commands_run=commands_run,
                tokens_used=total_tokens
            )

        except asyncio.TimeoutError:
            return AgentResult(
                content="".join(content_parts),
                agent_name=self.config.name,
                success=False,
                error=f"Agent timed out after {self.config.timeout} seconds",
                files_created=files_created,
                files_modified=files_modified,
                commands_run=commands_run,
                tokens_used=total_tokens
            )

        except asyncio.CancelledError:
            return AgentResult(
                content="".join(content_parts),
                agent_name=self.config.name,
                success=False,
                error="Agent execution cancelled",
                files_created=files_created,
                files_modified=files_modified,
                commands_run=commands_run,
                tokens_used=total_tokens
            )

        except Exception as e:
            return AgentResult(
                content="".join(content_parts),
                agent_name=self.config.name,
                success=False,
                error=str(e),
                files_created=files_created,
                files_modified=files_modified,
                commands_run=commands_run,
                tokens_used=total_tokens
            )

    @property
    def is_agentic(self) -> bool:
        """Check if this agent uses agentic (tool-use) mode."""
        return self._is_agentic

    def __repr__(self) -> str:
        mode = "agentic" if self._is_agentic else "print"
        return f"MCPAgent({self.config.name}, mode={mode})"


class MCPAgentPool:
    """Pool of MCP agents for a workflow."""

    def __init__(self, client: MCPClient, agents_dir: Path):
        """
        Initialize agent pool.

        Args:
            client: MCP client for communication
            agents_dir: Directory containing agent prompt files
        """
        self.client = client
        self.agents_dir = agents_dir
        self._agents: dict[str, MCPAgent] = {}

    def register(
        self,
        name: str,
        timeout: int = 300,
        max_tokens: int = 4096,
        tools: Optional[List[str]] = None
    ) -> MCPAgent:
        """
        Register an agent with the pool.

        Args:
            name: Agent name (matches prompt file)
            timeout: Execution timeout in seconds
            max_tokens: Maximum response tokens
            tools: Allowed tools for agentic agents

        Returns:
            Registered MCPAgent instance
        """
        config = MCPAgentConfig(
            name=name,
            prompt_file=self.agents_dir / f"{name}.md",
            timeout=timeout,
            max_tokens=max_tokens,
            tools=tools or []
        )
        agent = MCPAgent(config, self.client)
        self._agents[name] = agent
        return agent

    def get(self, name: str) -> Optional[MCPAgent]:
        """Get registered agent by name."""
        return self._agents.get(name)

    def list_agents(self) -> List[str]:
        """List all registered agent names."""
        return list(self._agents.keys())

    async def run(
        self,
        name: str,
        message: str,
        context: Optional[str] = None,
        on_progress: Optional[Callable[[StreamEvent], None]] = None
    ) -> AgentResult:
        """
        Run a registered agent.

        Args:
            name: Agent name
            message: Task message
            context: Additional context
            on_progress: Progress callback

        Returns:
            AgentResult from agent execution
        """
        agent = self._agents.get(name)
        if not agent:
            return AgentResult(
                content="",
                agent_name=name,
                success=False,
                error=f"Agent '{name}' not registered"
            )
        return await agent.run(message, context, on_progress)
