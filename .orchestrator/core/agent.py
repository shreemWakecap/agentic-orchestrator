"""
Agent: Runs Claude Code CLI as a subprocess.

Each agent spawns a Claude Code process with a specific system prompt.
This uses Claude Code directly - no API keys needed in the orchestrator.
"""
import subprocess
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class AgentResult:
    """Result from an agent execution."""
    content: str
    agent_name: str
    success: bool
    error: Optional[str] = None


class Agent:
    """
    A Claude Code subprocess agent.

    Usage:
        agent = Agent(
            name="scout",
            system_prompt="You are a codebase explorer...",
        )
        result = agent.run("Explore the authentication code")
    """

    def __init__(
        self,
        name: str,
        system_prompt: str,
        cwd: Optional[Path] = None,
    ):
        self.name = name
        self.system_prompt = system_prompt
        self.cwd = cwd or Path.cwd()

    def run(self, message: str, context: Optional[str] = None) -> AgentResult:
        """
        Run the agent using Claude Code CLI.

        Args:
            message: The user message to process
            context: Optional additional context to prepend

        Returns:
            AgentResult with the agent's response
        """
        try:
            # Build the full message
            full_message = message
            if context:
                full_message = f"## Context\n\n{context}\n\n## Task\n\n{message}"

            # Combine system prompt with message
            prompt = f"""<system>
{self.system_prompt}
</system>

{full_message}"""

            # Run Claude Code CLI
            result = subprocess.run(
                [
                    "claude",
                    "--print",  # Non-interactive, print output
                    "-p", prompt,  # The prompt
                ],
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
                error="Claude Code CLI not found. Install with: npm install -g @anthropic-ai/claude-code"
            )
        except Exception as e:
            return AgentResult(
                content="",
                agent_name=self.name,
                success=False,
                error=str(e)
            )

    def __repr__(self) -> str:
        return f"Agent(name={self.name!r})"
