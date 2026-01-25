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

from .config import get_agent_config, RetryConfig, ThinkingConfig


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

# Expected output markers for each agent type - used to validate responses
# If an agent's output doesn't contain these markers, it's likely a placeholder
AGENT_OUTPUT_MARKERS: dict[str, list[str]] = {
    # All agents use KEY: VALUE text format
    "scout": ["PROJECT_TYPE:", "STRUCTURE:"],
    "architect": ["APPROACH:", "FILES_TO_"],
    "planner": ["GOAL:", "STEPS:", "DO:"],
    "synthesizer": ["GOAL:", "STEPS:"],
    "validator": ["STATUS:", "SCORE:"],
    "analyzer": ["COMPLEXITY:", "STRATEGY:"],
    "decomposer": ["SUB_FEATURES:", "EXECUTION_ORDER:"],
    "parser": ['"phases"', '"steps"'],
    "syncer": ["COMMIT:", "PR_SUMMARY:"],
    # Markdown-output agents
    "fixer": ["## Fix", "##"],
    "reviewer": ["## Goals", "## Summary"],
    # Agentic agents (use tools, not text output)
    "builder": [],
    "tester": [],
    "integrator": [],
    # Expert agents (KEY: VALUE output for code review)
    "python": ["FINDINGS:", "SUMMARY:", "SCORE:"],
}

# Placeholder patterns that indicate the agent didn't follow its role
PLACEHOLDER_PATTERNS = [
    # Generic greetings
    "I'm ready to help you",
    "I'll help you with software engineering",
    "How can I help you",
    "What can I help",
    "Hello! How can I help",
    "Hi! How can I",
    "I'd be happy to help",
    # Confusion indicators
    "What would you like me to",
    "What would you like to work on",
    "Would you like me to",
    "I understand you've sent",
    "I understand. I'm ready to help",
    "I can see you're on the",
    "I can see you're working",
    "Let me know what",
    "Please let me know",
    # Empty message indicators
    "I see you've sent",
    "I see you've started",
    "you've sent an empty message",
    # Context confusion
    "working in the",
    "in your git working tree",
    "on the developmet branch",
    "on the main branch",
    # Meta-commentary
    "I'll analyze",
    "I'll start by",
    "Let me first",
    "First, I'll",
]


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


def _is_placeholder_response(content: str, agent_name: str) -> tuple[bool, str]:
    """
    Check if the response is a placeholder/greeting instead of actual agent output.

    Returns:
        Tuple of (is_placeholder, reason)
    """
    if not content:
        return True, "Empty response"

    content_stripped = content.strip()

    # Too short to be useful
    if len(content_stripped) < 50:
        return True, f"Response too short ({len(content_stripped)} chars)"

    content_lower = content_stripped.lower()

    # Check for placeholder patterns
    for pattern in PLACEHOLDER_PATTERNS:
        if pattern.lower() in content_lower:
            return True, f"Contains placeholder pattern: '{pattern}'"

    # Check for expected output markers
    markers = AGENT_OUTPUT_MARKERS.get(agent_name, [])
    if markers:
        found_marker = False
        for marker in markers:
            if marker.lower() in content_lower:
                found_marker = True
                break
        if not found_marker:
            return True, f"Missing expected markers for {agent_name}: {markers}"

    return False, ""


@dataclass
class RetryState:
    """Tracks state across retry attempts."""
    attempt: int = 0
    last_error: Optional[str] = None
    placeholder_retries: int = 0  # Track placeholder-specific retries


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


class _PlaceholderError(Exception):
    """Internal: agent returned placeholder instead of real output."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


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

    # Maximum placeholder retries before giving up
    MAX_PLACEHOLDER_RETRIES = 2

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

        Looks in the project's agents directory first, then falls back to the
        orchestrator's built-in agents directory for system agents like 'scout'.

        Args:
            name: Agent name (e.g., "scout" loads .orchestrator/agents/scout.md)
            project_root: Project root directory

        Returns:
            Agent instance with loaded system prompt
        """
        from config import ORCHESTRATOR_DIR

        # Try project's agents directory first
        agent_file = project_root / ".orchestrator" / "agents" / f"{name}.md"

        # Fall back to orchestrator's built-in agents directory
        if not agent_file.exists():
            agent_file = ORCHESTRATOR_DIR / "agents" / f"{name}.md"

        if not agent_file.exists():
            raise FileNotFoundError(f"Agent not found: {name}.md (searched in project and orchestrator agents directories)")

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

    def _build_enhanced_system_prompt(self, is_retry: bool = False) -> str:
        """
        Build an enhanced system prompt with strict output format enforcement.

        Args:
            is_retry: If True, add extra-strict formatting instructions
        """
        base_prompt = self.system_prompt

        # Add strict output format enforcement
        enforcement = """

## CRITICAL INSTRUCTIONS

You are operating as a specialized agent in an automated orchestration system.
Your output will be parsed programmatically - you MUST follow the exact output format specified above.

REQUIREMENTS:
1. Start your response with the first expected section header (e.g., "## Project Overview" or "## Implementation Steps")
2. Do NOT include any greeting, introduction, or preamble
3. Do NOT ask clarifying questions - work with what you're given
4. Do NOT say "I'll help you" or similar phrases
5. Do NOT reference the working directory, git branch, or file system state
6. Output ONLY the structured format specified in your role - nothing else
7. Begin immediately with the content in the required format
"""

        if is_retry:
            enforcement += """
IMPORTANT: Your previous response was rejected because it didn't follow the format.
This is a RETRY - you MUST output the structured format NOW, starting with the first header.
"""

        return base_prompt + enforcement

    def _build_user_message(
        self, message: str, context: Optional[str] = None, include_system: bool = False
    ) -> str:
        """
        Build the user message with task and optional context.

        Args:
            message: The task/message
            context: Optional context from previous agents
            include_system: If True, embed the system prompt in the message
                           (needed for Windows where command line is limited)
        """
        parts = []

        # On Windows, embed system prompt in user message to avoid cmd line limits
        if include_system:
            enhanced_prompt = self._build_enhanced_system_prompt(is_retry=False)
            parts.append(f"## Your Role\n\n{enhanced_prompt}")

        if context:
            parts.append(f"## Context\n\n{context}")

        parts.append(f"## Task\n\n{message}")

        return "\n\n".join(parts)

    def run(
        self,
        message: str,
        context: Optional[str] = None,
        max_retries: Optional[int] = None,
        retry_delay: Optional[float] = None,
        timeout: Optional[int] = None,
        thinking_enabled: Optional[bool] = None,
        thinking_budget: Optional[int] = None,
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
            thinking_enabled: Enable extended thinking (default from config)
            thinking_budget: Token budget for thinking (default from config)

        Returns:
            AgentResult with the agent's response
        """
        # Auto-detect if this agent should run in agentic mode
        if self.name in self.AGENTIC_AGENTS:
            return self.run_agentic(
                message, context, max_retries=max_retries,
                thinking_enabled=thinking_enabled, thinking_budget=thinking_budget
            )

        # Build retry config with overrides
        retry_config = RetryConfig(
            max_attempts=max_retries or self._config.retry.max_attempts,
            base_delay=retry_delay or self._config.retry.base_delay,
            backoff_multiplier=self._config.retry.backoff_multiplier,
            max_delay=self._config.retry.max_delay,
        )

        # Determine thinking settings
        use_thinking = thinking_enabled if thinking_enabled is not None else self._config.thinking.enabled
        effective_thinking_budget = thinking_budget or self._config.thinking.budget

        # Calculate timeout (multiply if thinking enabled)
        effective_timeout = timeout or self._config.timeouts.print_mode
        if use_thinking:
            effective_timeout = int(effective_timeout * self._config.thinking.timeout_multiplier)

        # Track placeholder retries separately
        placeholder_retries = 0

        def execute(state: RetryState) -> AgentResult:
            nonlocal placeholder_retries

            try:
                validated_cwd = _validate_cwd(self.cwd)

                # Build user message with embedded system prompt
                # (Windows has ~8000 char command line limit, so we embed in message)
                is_retry = placeholder_retries > 0

                # Build message with system prompt embedded for reliability
                user_message = self._build_user_message(
                    message, context, include_system=True
                )

                # Add retry emphasis if this is a retry
                if is_retry:
                    user_message = (
                        "IMPORTANT: Your previous response was rejected. "
                        "You MUST output the structured format NOW.\n\n"
                        + user_message
                    )

                # Use short append-system-prompt for output format enforcement
                # The full agent instructions are embedded in user message
                short_system = (
                    "You are a specialized agent. Follow the role instructions in the message exactly. "
                    "Output ONLY the structured format specified - no greetings, no preamble."
                )

                cmd = [
                    _get_claude_executable(),
                    "--print",
                    "--append-system-prompt", short_system,
                ]

                # Add extended thinking flags if enabled
                if use_thinking:
                    cmd.extend(["--thinking", "--thinking-budget", str(effective_thinking_budget)])

                result = subprocess.run(
                    cmd,
                    cwd=str(validated_cwd),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=effective_timeout,
                    shell=False,
                    input=user_message,
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

                content = result.stdout.strip()

                # Validate response isn't a placeholder
                is_placeholder, reason = _is_placeholder_response(content, self.name)
                if is_placeholder:
                    placeholder_retries += 1
                    if placeholder_retries <= self.MAX_PLACEHOLDER_RETRIES:
                        logger.warning(
                            f"Agent {self.name}: Placeholder response detected ({reason}). "
                            f"Retry {placeholder_retries}/{self.MAX_PLACEHOLDER_RETRIES}..."
                        )
                        raise _TransientError(f"Placeholder response: {reason}")
                    else:
                        # Exhausted placeholder retries - return what we got with warning
                        logger.error(
                            f"Agent {self.name}: Still getting placeholder after {placeholder_retries} retries. "
                            f"Returning response anyway."
                        )
                        return AgentResult(
                            content=content,
                            agent_name=self.name,
                            success=True,  # Mark as success but content may be bad
                            error=f"Warning: Response may be placeholder ({reason})"
                        )

                return AgentResult(
                    content=content,
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
        thinking_enabled: Optional[bool] = None,
        thinking_budget: Optional[int] = None,
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
            thinking_enabled: Enable extended thinking (default from config)
            thinking_budget: Token budget for thinking (default from config)

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

        # Determine thinking settings
        use_thinking = thinking_enabled if thinking_enabled is not None else self._config.thinking.enabled
        effective_thinking_budget = thinking_budget or self._config.thinking.budget

        # Calculate timeout (multiply if thinking enabled)
        effective_timeout = timeout or self._config.timeouts.agentic_mode
        if use_thinking:
            effective_timeout = int(effective_timeout * self._config.thinking.timeout_multiplier)

        tools = allowed_tools or self.ALLOWED_TOOLS

        def execute(state: RetryState) -> AgentResult:
            try:
                validated_cwd = _validate_cwd(self.cwd)

                # Build user message with embedded system prompt
                # (Windows has ~8000 char command line limit, so we embed in message)
                user_message = self._build_user_message(
                    message, context, include_system=True
                )

                if state.attempt > 0:
                    user_message = (
                        "IMPORTANT: Previous attempt failed. Execute the task now.\n\n"
                        + user_message
                    )

                # Use short append-system-prompt for enforcement
                short_system = (
                    "You are a specialized agent. Follow the role instructions exactly. "
                    "Use the tools provided to complete the task."
                )

                cmd = [
                    _get_claude_executable(),
                    "--permission-mode", "acceptEdits",
                    "--output-format", "json",
                    "--allowedTools", ",".join(tools),
                    "--append-system-prompt", short_system,
                ]

                # Add extended thinking flags if enabled
                if use_thinking:
                    cmd.extend(["--thinking", "--thinking-budget", str(effective_thinking_budget)])

                result = subprocess.run(
                    cmd,
                    cwd=str(validated_cwd),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=effective_timeout,
                    shell=False,
                    input=user_message,
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

            # Also check for costUSD field and estimate tokens from it
            if tokens_used == 0:
                cost_usd = _safe_get(data, "costUSD", 0) or 0
                if cost_usd > 0:
                    # Rough estimate: $0.015 per 1K tokens average
                    tokens_used = int(cost_usd / 0.000015)

            # Extract file operations from tool calls - check multiple locations
            messages = _safe_get(data, "messages", [])
            if not isinstance(messages, list):
                logger.debug(f"Agent {self.name}: 'messages' is not a list: {type(messages)}")
                messages = []

            for msg in messages:
                if not isinstance(msg, dict):
                    continue

                # Check for tool_use type
                if _safe_get(msg, "type") == "tool_use":
                    tool_name = _safe_get(msg, "name", "")
                    tool_input = _safe_get(msg, "input", {})
                    self._extract_file_ops(tool_name, tool_input, files_created, files_modified, commands_run)

                # Also check for nested content with tool_use
                msg_content = _safe_get(msg, "content", [])
                if isinstance(msg_content, list):
                    for item in msg_content:
                        if isinstance(item, dict) and _safe_get(item, "type") == "tool_use":
                            tool_name = _safe_get(item, "name", "")
                            tool_input = _safe_get(item, "input", {})
                            self._extract_file_ops(tool_name, tool_input, files_created, files_modified, commands_run)

            return (True, content, files_created, files_modified, commands_run, tokens_used)

        except json.JSONDecodeError as e:
            logger.debug(f"Agent {self.name}: JSON parse error: {e}")
            return (False, output, [], [], [], 0)
        except Exception as e:
            logger.warning(f"Agent {self.name}: Unexpected error parsing output: {e}")
            return (False, output, [], [], [], 0)

    def _extract_file_ops(
        self,
        tool_name: str,
        tool_input: dict,
        files_created: list[str],
        files_modified: list[str],
        commands_run: list[str],
    ) -> None:
        """Extract file operations from a tool call."""
        if not isinstance(tool_input, dict):
            return

        if tool_name == "Write":
            file_path = _safe_get(tool_input, "file_path", "")
            if file_path and file_path not in files_created:
                files_created.append(file_path)
        elif tool_name in ("Edit", "MultiEdit"):
            file_path = _safe_get(tool_input, "file_path", "")
            if file_path and file_path not in files_modified:
                files_modified.append(file_path)
        elif tool_name == "Bash":
            command = _safe_get(tool_input, "command", "")
            if command and command not in commands_run:
                commands_run.append(command)

    def __repr__(self) -> str:
        return f"Agent(name={self.name!r}, agentic={self.name in self.AGENTIC_AGENTS})"
