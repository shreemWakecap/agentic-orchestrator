"""
Agent: Loads agent definitions from .claude/agents/ and runs via Claude CLI.

The agent definitions (system prompts) live in .claude/agents/*.md
The orchestrator loads these and runs them via Claude Code CLI.

Two modes:
- Print mode (--print): For planning/analysis agents that just output text
- Agentic mode: For builder agents that need to write files using tools
"""
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class AgentResult:
    """Result from an agent execution."""
    content: str
    agent_name: str
    success: bool
    error: Optional[str] = None
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    commands_run: list[str] = field(default_factory=list)


class Agent:
    """
    A Claude Code agent that loads its definition from .claude/agents/.

    Usage:
        # Load agent from .claude/agents/scout.md
        agent = Agent.load("scout", project_root=Path("."))

        # For planning/analysis (read-only)
        result = agent.run("Explore the codebase")

        # For building (can write files)
        result = agent.run_agentic("Create the user model")
    """

    # Agents that should run in agentic mode (can write files)
    AGENTIC_AGENTS = {"builder", "tester", "integrator"}

    # Tools allowed for agentic agents
    ALLOWED_TOOLS = [
        "Read", "Write", "Edit", "MultiEdit",
        "Glob", "Grep", "Bash",
        "TodoRead", "TodoWrite"
    ]

    def __init__(
        self,
        name: str,
        system_prompt: str,
        cwd: Path,
    ):
        self.name = name
        self.system_prompt = system_prompt
        self.cwd = cwd

    @classmethod
    def load(cls, name: str, project_root: Path) -> "Agent":
        """
        Load an agent from .claude/agents/<name>.md

        Args:
            name: Agent name (e.g., "scout" loads .claude/agents/scout.md)
            project_root: Project root directory

        Returns:
            Agent instance with loaded system prompt
        """
        agent_file = project_root / ".claude" / "agents" / f"{name}.md"

        if not agent_file.exists():
            raise FileNotFoundError(f"Agent not found: {agent_file}")

        content = agent_file.read_text(encoding="utf-8")

        # Parse frontmatter and extract body as system prompt
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                system_prompt = parts[2].strip()
            else:
                system_prompt = content
        else:
            system_prompt = content

        return cls(name=name, system_prompt=system_prompt, cwd=project_root)

    def _build_prompt(self, message: str, context: Optional[str] = None) -> str:
        """Build the full prompt with system prompt and context."""
        full_message = message
        if context:
            full_message = f"## Context\n\n{context}\n\n## Task\n\n{message}"

        return f"""<system>
{self.system_prompt}
</system>

{full_message}"""

    def run(self, message: str, context: Optional[str] = None) -> AgentResult:
        """
        Run the agent in print mode (read-only, no tool execution).

        Best for: planning, analysis, validation agents.

        Args:
            message: The task/message for the agent
            context: Optional context from previous agents

        Returns:
            AgentResult with the agent's response
        """
        # Auto-detect if this agent should run in agentic mode
        if self.name in self.AGENTIC_AGENTS:
            return self.run_agentic(message, context)

        try:
            prompt = self._build_prompt(message, context)

            # Run Claude Code CLI in print mode
            result = subprocess.run(
                ["claude", "--print", "-p", prompt],
                cwd=str(self.cwd),
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            if result.returncode != 0:
                return AgentResult(
                    content="",
                    agent_name=self.name,
                    success=False,
                    error=result.stderr or f"Exit code: {result.returncode}"
                )

            return AgentResult(
                content=result.stdout.strip(),
                agent_name=self.name,
                success=True,
            )

        except subprocess.TimeoutExpired:
            return AgentResult(
                content="",
                agent_name=self.name,
                success=False,
                error="Agent timed out after 5 minutes"
            )
        except FileNotFoundError:
            return AgentResult(
                content="",
                agent_name=self.name,
                success=False,
                error="Claude Code CLI not found. Install: npm install -g @anthropic-ai/claude-code"
            )
        except Exception as e:
            return AgentResult(
                content="",
                agent_name=self.name,
                success=False,
                error=str(e)
            )

    def run_agentic(
        self,
        message: str,
        context: Optional[str] = None,
        allowed_tools: Optional[list[str]] = None,
        timeout: int = 600,  # 10 minutes for agentic tasks
    ) -> AgentResult:
        """
        Run the agent in agentic mode (can execute tools, write files).

        Best for: builder, tester agents that need to modify code.

        Args:
            message: The task/message for the agent
            context: Optional context from previous agents
            allowed_tools: List of allowed tools (defaults to ALLOWED_TOOLS)
            timeout: Timeout in seconds

        Returns:
            AgentResult with the agent's response and file changes
        """
        try:
            prompt = self._build_prompt(message, context)
            tools = allowed_tools or self.ALLOWED_TOOLS

            # Build command with agentic flags
            cmd = [
                "claude",
                "-p", prompt,
                "--yes",  # Auto-accept prompts for unattended execution
                "--output-format", "json",  # Get structured output
                "--allowedTools", ",".join(tools),
            ]

            # Run Claude Code CLI in agentic mode
            result = subprocess.run(
                cmd,
                cwd=str(self.cwd),
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode != 0:
                return AgentResult(
                    content="",
                    agent_name=self.name,
                    success=False,
                    error=result.stderr or f"Exit code: {result.returncode}"
                )

            # Parse JSON output
            output = result.stdout.strip()
            files_created = []
            files_modified = []
            commands_run = []
            content = output

            try:
                # Try to parse as JSON to extract file operations
                data = json.loads(output)
                if isinstance(data, dict):
                    content = data.get("result", data.get("content", output))
                    # Extract file operations from tool calls if available
                    for msg in data.get("messages", []):
                        if msg.get("type") == "tool_use":
                            tool_name = msg.get("name", "")
                            tool_input = msg.get("input", {})
                            if tool_name == "Write":
                                files_created.append(tool_input.get("file_path", ""))
                            elif tool_name in ("Edit", "MultiEdit"):
                                files_modified.append(tool_input.get("file_path", ""))
                            elif tool_name == "Bash":
                                commands_run.append(tool_input.get("command", ""))
            except json.JSONDecodeError:
                # Not JSON, use raw output
                content = output

            return AgentResult(
                content=content,
                agent_name=self.name,
                success=True,
                files_created=files_created,
                files_modified=files_modified,
                commands_run=commands_run,
            )

        except subprocess.TimeoutExpired:
            return AgentResult(
                content="",
                agent_name=self.name,
                success=False,
                error=f"Agent timed out after {timeout} seconds"
            )
        except FileNotFoundError:
            return AgentResult(
                content="",
                agent_name=self.name,
                success=False,
                error="Claude Code CLI not found. Install: npm install -g @anthropic-ai/claude-code"
            )
        except Exception as e:
            return AgentResult(
                content="",
                agent_name=self.name,
                success=False,
                error=str(e)
            )

    def __repr__(self) -> str:
        return f"Agent(name={self.name!r}, agentic={self.name in self.AGENTIC_AGENTS})"
