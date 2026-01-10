"""
Agent: Loads agent definitions from .claude/agents/ and runs via Claude CLI.

The agent definitions (system prompts) live in .claude/agents/*.md
The orchestrator loads these and runs them via Claude Code CLI.
"""
import subprocess
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
    A Claude Code agent that loads its definition from .claude/agents/.

    Usage:
        # Load agent from .claude/agents/scout.md
        agent = Agent.load("scout", project_root=Path("."))
        result = agent.run("Explore the codebase")
    """

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

    def run(self, message: str, context: Optional[str] = None) -> AgentResult:
        """
        Run the agent using Claude Code CLI.

        Args:
            message: The task/message for the agent
            context: Optional context from previous agents

        Returns:
            AgentResult with the agent's response
        """
        try:
            # Build the full prompt
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

    def __repr__(self) -> str:
        return f"Agent(name={self.name!r})"
