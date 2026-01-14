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
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, TypeVar

from .config import get_agent_config, RetryConfig


def _get_claude_executable() -> str:
    """
    Get the full path to the claude executable.

    On Windows, subprocess.run with shell=False doesn't search PATH for .cmd files.
    Using shutil.which() properly resolves claude.cmd on Windows.
    """
    claude_path = shutil.which("claude")
    if claude_path is None:
        raise FileNotFoundError(
            "Claude Code CLI not found. Install: npm install -g @anthropic-ai/claude-code"
        )
    return claude_path

logger = logging.getLogger(__name__)

T = TypeVar("T")

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
class RetryState:
    """Tracks state across retry attempts."""
    attempt: int = 0
    last_error: Optional[str] = None


def _run_with_retry(
    execute_fn: Callable[[RetryState], T],
    retry_config: RetryConfig,
    error_prefix: str,
) -> T:
    """
    Execute a function with retry logic for transient errors.

    Args:
        execute_fn: Function to execute. Receives RetryState, returns result or raises.
                   Should raise TransientError for retryable errors.
        retry_config: Retry configuration settings
        error_prefix: Prefix for error messages (e.g., "Agent scout")

    Returns:
        Result from execute_fn on success

    Raises:
        The last exception if all retries exhausted
    """
    state = RetryState()

    for attempt in range(retry_config.max_attempts):
        state.attempt = attempt
        try:
            return execute_fn(state)
        except _TransientError as e:
            state.last_error = str(e)
            if attempt < retry_config.max_attempts - 1:
                delay = min(
                    retry_config.base_delay * (retry_config.backoff_multiplier ** attempt),
                    retry_config.max_delay
                )
                logger.warning(
                    f"{error_prefix} transient error (attempt {attempt + 1}/{retry_config.max_attempts}): "
                    f"{state.last_error}. Retrying in {delay:.1f}s..."
                )
                time.sleep(delay)
                continue
            raise
        except _NonTransientError:
            raise
        except Exception as e:
            # Check if it's transient
            if _is_transient_error(str(e)) and attempt < retry_config.max_attempts - 1:
                state.last_error = str(e)
                delay = min(
                    retry_config.base_delay * (retry_config.backoff_multiplier ** attempt),
                    retry_config.max_delay
                )
                logger.warning(
                    f"{error_prefix} error (attempt {attempt + 1}/{retry_config.max_attempts}): "
                    f"{state.last_error}. Retrying in {delay:.1f}s..."
                )
                time.sleep(delay)
                continue
            raise

    # Should not reach here, but just in case
    raise RuntimeError(f"Failed after {retry_config.max_attempts} attempts. Last error: {state.last_error}")


class _TransientError(Exception):
    """Internal: marks an error as transient (retryable)."""
    pass


class _NonTransientError(Exception):
    """Internal: marks an error as non-transient (fail immediately)."""
    pass


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
        self._config = get_agent_config(cwd)

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

    def _build_full_prompt(self, message: str, context: Optional[str] = None) -> str:
        """
        Build the complete prompt with embedded system instructions.

        On Windows, passing complex system prompts via --system-prompt flag causes
        issues with special characters (|, <, >, quotes, braces) being interpreted
        by cmd.exe even with shell=False (because claude.CMD is a batch file).

        Solution: Embed the system prompt in the user message and pass via stdin.
        This avoids all Windows command-line escaping issues.
        """
        # Build the user message part
        if context:
            user_message = f"## Context\n\n{context}\n\n## Task\n\n{message}"
        else:
            user_message = message

        # Embed system instructions with clear delimiters
        return f"""<system-instructions>
{self.system_prompt}
</system-instructions>

{user_message}"""

    def run(
        self,
        message: str,
        context: Optional[str] = None,
        max_retries: Optional[int] = None,
        retry_delay: Optional[float] = None,
        timeout: Optional[int] = None,
    ) -> AgentResult:
        """
        Run the agent in print mode (read-only, no tool execution).

        Best for: planning, analysis, validation agents.

        Args:
            message: The task/message for the agent
            context: Optional context from previous agents
            max_retries: Maximum retry attempts (default from config)
            retry_delay: Base delay between retries (default from config)
            timeout: Timeout in seconds (default from config)

        Returns:
            AgentResult with the agent's response
        """
        # Auto-detect if this agent should run in agentic mode
        if self.name in self.AGENTIC_AGENTS:
            return self.run_agentic(message, context, max_retries=max_retries)

        # Build retry config with overrides
        retry_config = RetryConfig(
            max_attempts=max_retries or self._config.retry.max_attempts,
            base_delay=retry_delay or self._config.retry.base_delay,
            backoff_multiplier=self._config.retry.backoff_multiplier,
            max_delay=self._config.retry.max_delay,
        )
        effective_timeout = timeout or self._config.timeouts.print_mode

        def execute(state: RetryState) -> AgentResult:
            try:
                validated_cwd = _validate_cwd(self.cwd)

                # Build full prompt with embedded system instructions
                # This avoids Windows command-line escaping issues with --system-prompt
                full_prompt = self._build_full_prompt(message, context)

                cmd = [
                    _get_claude_executable(),
                    "--print",
                ]

                result = subprocess.run(
                    cmd,
                    cwd=str(validated_cwd),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=effective_timeout,
                    shell=False,
                    input=full_prompt,  # Pass everything via stdin
                )

                if result.returncode != 0:
                    error_msg = result.stderr or f"Exit code: {result.returncode}"
                    if _is_transient_error(error_msg):
                        raise _TransientError(error_msg)
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
                raise _TransientError(f"Agent timed out after {effective_timeout} seconds")
            except FileNotFoundError:
                raise _NonTransientError(
                    "Claude Code CLI not found. Install: npm install -g @anthropic-ai/claude-code"
                )
            except ValueError as e:
                raise _NonTransientError(str(e))

        try:
            return _run_with_retry(execute, retry_config, f"Agent {self.name}")
        except _TransientError as e:
            return AgentResult(
                content="",
                agent_name=self.name,
                success=False,
                error=f"Failed after {retry_config.max_attempts} attempts. Last error: {e}"
            )
        except _NonTransientError as e:
            return AgentResult(
                content="",
                agent_name=self.name,
                success=False,
                error=str(e)
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
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
        retry_delay: Optional[float] = None,
    ) -> AgentResult:
        """
        Run the agent in agentic mode (can execute tools, write files).

        Best for: builder, tester agents that need to modify code.

        Args:
            message: The task/message for the agent
            context: Optional context from previous agents
            allowed_tools: List of allowed tools (defaults to ALLOWED_TOOLS)
            timeout: Timeout in seconds (default from config)
            max_retries: Maximum retry attempts (default from config)
            retry_delay: Base delay between retries (default from config)

        Returns:
            AgentResult with the agent's response and file changes
        """
        # Build retry config with overrides (agentic uses longer delays)
        retry_config = RetryConfig(
            max_attempts=max_retries or self._config.retry.max_attempts,
            base_delay=retry_delay or self._config.retry.agentic_base_delay,
            backoff_multiplier=self._config.retry.backoff_multiplier,
            max_delay=self._config.retry.max_delay,
        )
        effective_timeout = timeout or self._config.timeouts.agentic_mode
        tools = allowed_tools or self.ALLOWED_TOOLS

        def execute(state: RetryState) -> AgentResult:
            try:
                validated_cwd = _validate_cwd(self.cwd)

                # Build full prompt with embedded system instructions
                # This avoids Windows command-line escaping issues with --system-prompt
                full_prompt = self._build_full_prompt(message, context)

                cmd = [
                    _get_claude_executable(),
                    "--permission-mode", "acceptEdits",
                    "--output-format", "json",
                    "--allowedTools", ",".join(tools),
                ]

                result = subprocess.run(
                    cmd,
                    cwd=str(validated_cwd),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=effective_timeout,
                    shell=False,
                    input=full_prompt,  # Pass everything via stdin
                )

                if result.returncode != 0:
                    error_msg = result.stderr or f"Exit code: {result.returncode}"
                    if _is_transient_error(error_msg):
                        raise _TransientError(error_msg)
                    return AgentResult(
                        content="",
                        agent_name=self.name,
                        success=False,
                        error=error_msg
                    )

                # Parse output
                output = result.stdout.strip()
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
                raise _TransientError(f"Agent timed out after {effective_timeout} seconds")
            except FileNotFoundError:
                raise _NonTransientError(
                    "Claude Code CLI not found. Install: npm install -g @anthropic-ai/claude-code"
                )
            except ValueError as e:
                raise _NonTransientError(str(e))

        try:
            return _run_with_retry(execute, retry_config, f"Agent {self.name}")
        except _TransientError as e:
            return AgentResult(
                content="",
                agent_name=self.name,
                success=False,
                error=f"Failed after {retry_config.max_attempts} attempts. Last error: {e}"
            )
        except _NonTransientError as e:
            return AgentResult(
                content="",
                agent_name=self.name,
                success=False,
                error=str(e)
            )
        except Exception as e:
            return AgentResult(
                content="",
                agent_name=self.name,
                success=False,
                error=str(e)
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
            usage = _safe_get(data, "usage", {})
            if isinstance(usage, dict):
                input_tokens = _safe_get(usage, "input_tokens", 0) or 0
                output_tokens = _safe_get(usage, "output_tokens", 0) or 0
                tokens_used = input_tokens + output_tokens

            if tokens_used == 0:
                tokens_used = _safe_get(data, "total_tokens", 0) or 0

            if tokens_used == 0:
                stats = _safe_get(data, "stats", {})
                if isinstance(stats, dict):
                    tokens_used = _safe_get(stats, "total_tokens", 0) or 0

            # Extract file operations from tool calls
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
