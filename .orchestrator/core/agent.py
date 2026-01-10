"""
Agent: A wrapper around Claude API calls.

Each agent has a system prompt and can process messages.
Agents are the building blocks of workflows.
"""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import anthropic
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AgentResult:
    """Result from an agent execution."""
    content: str
    agent_name: str
    success: bool
    error: Optional[str] = None
    tokens_used: int = 0


class Agent:
    """
    A Claude-powered agent with a specific system prompt.

    Usage:
        agent = Agent(
            name="scout",
            system_prompt="You are a codebase explorer...",
            model="claude-sonnet-4-20250514"
        )
        result = agent.run("Explore the authentication code")
    """

    def __init__(
        self,
        name: str,
        system_prompt: str,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
    ):
        self.name = name
        self.system_prompt = system_prompt
        self.model = model
        self.max_tokens = max_tokens
        self.client = anthropic.Anthropic()

    @classmethod
    def from_file(cls, agent_file: Path, **kwargs) -> "Agent":
        """
        Load an agent from a markdown file in .claude/agents/.

        The file should have YAML frontmatter with name and description,
        followed by the system prompt content.
        """
        content = agent_file.read_text(encoding="utf-8")

        # Parse frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = parts[1].strip()
                body = parts[2].strip()

                # Extract name from frontmatter
                name = None
                for line in frontmatter.split("\n"):
                    if line.startswith("name:"):
                        name = line.split(":", 1)[1].strip()
                        break

                if not name:
                    name = agent_file.stem

                return cls(name=name, system_prompt=body, **kwargs)

        # No frontmatter, use filename as name
        return cls(name=agent_file.stem, system_prompt=content, **kwargs)

    def run(self, message: str, context: Optional[str] = None) -> AgentResult:
        """
        Run the agent with a message.

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

            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.system_prompt,
                messages=[{"role": "user", "content": full_message}]
            )

            # Extract text content
            content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    content += block.text

            return AgentResult(
                content=content,
                agent_name=self.name,
                success=True,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens
            )

        except Exception as e:
            return AgentResult(
                content="",
                agent_name=self.name,
                success=False,
                error=str(e)
            )

    def __repr__(self) -> str:
        return f"Agent(name={self.name!r}, model={self.model!r})"
