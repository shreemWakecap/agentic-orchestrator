"""
Agent: Loads agent definitions from .orchestrator/agents/ and runs via Claude CLI.

The agent definitions (system prompts) live in .orchestrator/agents/*.md
The orchestrator loads these and runs them via Claude Code CLI.

Two modes:
- Print mode (--print): For planning/analysis agents that just output text
- Agentic mode: For builder agents that need to write files using tools
"""
import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Transient errors that warrant retry
TRANSIENT_ERRORS = (
    "timeout",
    "connection refused",
    "temporarily unavailable",
    "rate limit",
    "503",
    "502",
    "429",
)


def _is_transient_error(error: str) -> bool:
    """Check if an error is transient and should be retried."""
    error_lower = error.lower()
    return any(te in error_lower for te in TRANSIENT_ERRORS)


def _validate_cwd(cwd: Path) -> Path:
    """Validate working directory for subprocess execution."""
    resolved = cwd.resolve()
    if not resolved.exists():
        raise ValueError(f"Working directory does not exist: {resolved}")
    if not resolved.is_dir():
        raise ValueError(f"Working directory is not a directory: {resolved}")
    return resolved


def _safe_get(data: dict | list, key: str, default=None):
    """Safely get a value from a dict, returning default if not a dict or key missing."""
    if isinstance(data, dict):
        return data.get(key, default)
    return default


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
    tokens_used: int = 0  # Total tokens consumed by this agent


class Agent:
    """
    A Claude Code agent that loads its definition from .orchestrator/agents/.

    Usage:
        # Load agent from .orchestrator/agents/scout.md
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
        Load an agent from .orchestrator/agents/<name>.md

        Args:
            name: Agent name (e.g., "scout" loads .orchestrator/agents/scout.md)
            project_root: Project root directory

        Returns:
            Agent instance with loaded system prompt
        """
        agent_file = project_root / ".orchestrator" / "agents" / f"{name}.md"

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

    def run(
        self,
        message: str,
        context: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> AgentResult:
        """
        Run the agent in print mode (read-only, no tool execution).

        Best for: planning, analysis, validation agents.

        Args:
            message: The task/message for the agent
            context: Optional context from previous agents
            max_retries: Maximum retry attempts for transient failures
            retry_delay: Base delay between retries (exponential backoff)

        Returns:
            AgentResult with the agent's response
        """
        # Auto-detect if this agent should run in agentic mode
        if self.name in self.AGENTIC_AGENTS:
            return self.run_agentic(message, context, max_retries=max_retries)

        last_error: Optional[str] = None

        for attempt in range(max_retries):
            try:
                # Validate working directory
                validated_cwd = _validate_cwd(self.cwd)
                prompt = self._build_prompt(message, context)

                # Run Claude Code CLI in print mode
                # shell=False is default with list args, but explicit for security
                result = subprocess.run(
                    ["claude", "--print", "-p", prompt],
                    cwd=str(validated_cwd),
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 minute timeout
                    shell=False,  # Explicit for security - prevents shell injection
                )

                if result.returncode != 0:
                    error_msg = result.stderr or f"Exit code: {result.returncode}"
                    # Check if transient and should retry
                    if _is_transient_error(error_msg) and attempt < max_retries - 1:
                        last_error = error_msg
                        delay = retry_delay * (2 ** attempt)  # Exponential backoff
                        logger.warning(
                            f"Agent {self.name} transient error (attempt {attempt + 1}/{max_retries}): "
                            f"{error_msg}. Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                        continue

                    return AgentResult(
                        content="",
                        agent_name=self.name,
                        success=False,
                        error=error_msg
                    )

                return AgentResult(
                    content=result.stdout.strip(),
                    agent_name=self.name,
                    success=True,
                )

            except subprocess.TimeoutExpired:
                last_error = "Agent timed out after 5 minutes"
                if attempt < max_retries - 1:
                    delay = retry_delay * (2 ** attempt)
                    logger.warning(
                        f"Agent {self.name} timeout (attempt {attempt + 1}/{max_retries}). "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    continue
            except FileNotFoundError:
                # Non-transient error - don't retry
                return AgentResult(
                    content="",
                    agent_name=self.name,
                    success=False,
                    error="Claude Code CLI not found. Install: npm install -g @anthropic-ai/claude-code"
                )
            except ValueError as e:
                # CWD validation error - non-transient
                return AgentResult(
                    content="",
                    agent_name=self.name,
                    success=False,
                    error=str(e)
                )
            except Exception as e:
                last_error = str(e)
                if _is_transient_error(last_error) and attempt < max_retries - 1:
                    delay = retry_delay * (2 ** attempt)
                    logger.warning(
                        f"Agent {self.name} error (attempt {attempt + 1}/{max_retries}): "
                        f"{last_error}. Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    continue

                return AgentResult(
                    content="",
                    agent_name=self.name,
                    success=False,
                    error=last_error
                )

        # All retries exhausted
        return AgentResult(
            content="",
            agent_name=self.name,
            success=False,
            error=f"Failed after {max_retries} attempts. Last error: {last_error}"
        )

    def run_agentic(
        self,
        message: str,
        context: Optional[str] = None,
        allowed_tools: Optional[list[str]] = None,
        timeout: int = 600,  # 10 minutes for agentic tasks
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ) -> AgentResult:
        """
        Run the agent in agentic mode (can execute tools, write files).

        Best for: builder, tester agents that need to modify code.

        Args:
            message: The task/message for the agent
            context: Optional context from previous agents
            allowed_tools: List of allowed tools (defaults to ALLOWED_TOOLS)
            timeout: Timeout in seconds
            max_retries: Maximum retry attempts for transient failures
            retry_delay: Base delay between retries (exponential backoff)

        Returns:
            AgentResult with the agent's response and file changes
        """
        last_error: Optional[str] = None

        for attempt in range(max_retries):
            try:
                # Validate working directory
                validated_cwd = _validate_cwd(self.cwd)
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
                # shell=False is default with list args, but explicit for security
                result = subprocess.run(
                    cmd,
                    cwd=str(validated_cwd),
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    shell=False,  # Explicit for security - prevents shell injection
                )

                if result.returncode != 0:
                    error_msg = result.stderr or f"Exit code: {result.returncode}"
                    # Check if transient and should retry
                    if _is_transient_error(error_msg) and attempt < max_retries - 1:
                        last_error = error_msg
                        delay = retry_delay * (2 ** attempt)
                        logger.warning(
                            f"Agent {self.name} transient error (attempt {attempt + 1}/{max_retries}): "
                            f"{error_msg}. Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                        continue

                    return AgentResult(
                        content="",
                        agent_name=self.name,
                        success=False,
                        error=error_msg
                    )

                # Parse JSON output with robust error handling
                output = result.stdout.strip()
                files_created: list[str] = []
                files_modified: list[str] = []
                commands_run: list[str] = []
                tokens_used: int = 0
                content = output

                parsed_ok, content, files_created, files_modified, commands_run, tokens_used = (
                    self._parse_agentic_output(output)
                )

                if not parsed_ok:
                    logger.debug(f"Agent {self.name}: Output was not valid JSON, using raw output")

                return AgentResult(
                    content=content,
                    agent_name=self.name,
                    success=True,
                    files_created=files_created,
                    files_modified=files_modified,
                    commands_run=commands_run,
                    tokens_used=tokens_used,
                )

            except subprocess.TimeoutExpired:
                last_error = f"Agent timed out after {timeout} seconds"
                if attempt < max_retries - 1:
                    delay = retry_delay * (2 ** attempt)
                    logger.warning(
                        f"Agent {self.name} timeout (attempt {attempt + 1}/{max_retries}). "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    continue
            except FileNotFoundError:
                # Non-transient error - don't retry
                return AgentResult(
                    content="",
                    agent_name=self.name,
                    success=False,
                    error="Claude Code CLI not found. Install: npm install -g @anthropic-ai/claude-code"
                )
            except ValueError as e:
                # CWD validation error - non-transient
                return AgentResult(
                    content="",
                    agent_name=self.name,
                    success=False,
                    error=str(e)
                )
            except Exception as e:
                last_error = str(e)
                if _is_transient_error(last_error) and attempt < max_retries - 1:
                    delay = retry_delay * (2 ** attempt)
                    logger.warning(
                        f"Agent {self.name} error (attempt {attempt + 1}/{max_retries}): "
                        f"{last_error}. Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    continue

                return AgentResult(
                    content="",
                    agent_name=self.name,
                    success=False,
                    error=last_error
                )

        # All retries exhausted
        return AgentResult(
            content="",
            agent_name=self.name,
            success=False,
            error=f"Failed after {max_retries} attempts. Last error: {last_error}"
        )

    def _parse_agentic_output(
        self, output: str
    ) -> tuple[bool, str, list[str], list[str], list[str], int]:
        """
        Parse agentic output JSON with robust type checking.

        Returns:
            Tuple of (parsed_ok, content, files_created, files_modified, commands_run, tokens_used)
        """
        files_created: list[str] = []
        files_modified: list[str] = []
        commands_run: list[str] = []
        tokens_used: int = 0
        content = output

        try:
            data = json.loads(output)

            if not isinstance(data, dict):
                logger.debug(f"Agent {self.name}: JSON output is not a dict: {type(data)}")
                return (False, output, [], [], [], 0)

            # Extract content with fallback chain
            content = _safe_get(data, "result") or _safe_get(data, "content") or output

            # Extract token usage from various possible locations in JSON
            # Claude CLI may include usage stats at different places
            usage = _safe_get(data, "usage", {})
            if isinstance(usage, dict):
                input_tokens = _safe_get(usage, "input_tokens", 0) or 0
                output_tokens = _safe_get(usage, "output_tokens", 0) or 0
                tokens_used = input_tokens + output_tokens

            # Alternative: check for total_tokens directly
            if tokens_used == 0:
                tokens_used = _safe_get(data, "total_tokens", 0) or 0

            # Check in stats section
            if tokens_used == 0:
                stats = _safe_get(data, "stats", {})
                if isinstance(stats, dict):
                    tokens_used = _safe_get(stats, "total_tokens", 0) or 0

            # Extract file operations from tool calls if available
            messages = _safe_get(data, "messages", [])
            if not isinstance(messages, list):
                logger.debug(f"Agent {self.name}: 'messages' is not a list: {type(messages)}")
                messages = []

            for msg in messages:
                if not isinstance(msg, dict):
                    continue

                if _safe_get(msg, "type") != "tool_use":
                    continue

                tool_name = _safe_get(msg, "name", "")
                tool_input = _safe_get(msg, "input", {})

                if not isinstance(tool_input, dict):
                    logger.debug(
                        f"Agent {self.name}: tool_input is not a dict for {tool_name}: {type(tool_input)}"
                    )
                    continue

                # Extract file paths, filtering empty strings
                if tool_name == "Write":
                    file_path = _safe_get(tool_input, "file_path", "")
                    if file_path:
                        files_created.append(file_path)
                elif tool_name in ("Edit", "MultiEdit"):
                    file_path = _safe_get(tool_input, "file_path", "")
                    if file_path:
                        files_modified.append(file_path)
                elif tool_name == "Bash":
                    command = _safe_get(tool_input, "command", "")
                    if command:
                        commands_run.append(command)

            return (True, content, files_created, files_modified, commands_run, tokens_used)

        except json.JSONDecodeError as e:
            logger.debug(f"Agent {self.name}: JSON parse error: {e}")
            return (False, output, [], [], [], 0)
        except Exception as e:
            logger.warning(f"Agent {self.name}: Unexpected error parsing output: {e}")
            return (False, output, [], [], [], 0)

    def __repr__(self) -> str:
        return f"Agent(name={self.name!r}, agentic={self.name in self.AGENTIC_AGENTS})"
