"""
JSONL Event Parser - Parses structured events from CLI output.

Converts CLI JSONL output into typed event objects for:
- Database storage
- SSE streaming
- Progress tracking
- Checkpoint handling
"""
import json
import re
import logging
from datetime import datetime
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Event types emitted by CLI."""
    START = "start"
    PROGRESS = "progress"
    LOG = "log"
    CHECKPOINT = "checkpoint"
    ERROR = "error"
    COMPLETE = "complete"
    CANCELLED = "cancelled"
    # Fallback for unstructured output
    RAW = "raw"


class LogLevel(str, Enum):
    """Log levels for log events."""
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


@dataclass
class BaseEvent:
    """Base class for all events."""
    type: EventType = field(default=EventType.RAW)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    raw_line: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/serialization."""
        d = asdict(self)
        d["type"] = self.type.value
        d["timestamp"] = self.timestamp.isoformat()
        return d


@dataclass
class StartEvent(BaseEvent):
    """Job started event."""
    type: EventType = field(default=EventType.START)
    phase: str = "init"


@dataclass
class ProgressEvent(BaseEvent):
    """Progress update event."""
    type: EventType = field(default=EventType.PROGRESS)
    phase: str = ""
    percent: int = 0
    message: Optional[str] = None


@dataclass
class LogEvent(BaseEvent):
    """Log message event."""
    type: EventType = field(default=EventType.LOG)
    level: LogLevel = LogLevel.INFO
    message: str = ""


@dataclass
class CheckpointEvent(BaseEvent):
    """Checkpoint event for job recovery."""
    type: EventType = field(default=EventType.CHECKPOINT)
    checkpoint_id: str = ""
    phase: str = ""
    percent: int = 0
    state_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ErrorEvent(BaseEvent):
    """Error event."""
    type: EventType = field(default=EventType.ERROR)
    message: str = ""
    details: Optional[str] = None


@dataclass
class CompleteEvent(BaseEvent):
    """Job completion event."""
    type: EventType = field(default=EventType.COMPLETE)
    exit_code: int = 0
    result: Optional[Dict[str, Any]] = None


@dataclass
class RawEvent(BaseEvent):
    """Fallback for unstructured output."""
    type: EventType = field(default=EventType.RAW)
    content: str = ""
    inferred_level: LogLevel = LogLevel.INFO


# Union type for all events
Event = Union[StartEvent, ProgressEvent, LogEvent, CheckpointEvent, ErrorEvent, CompleteEvent, RawEvent]


class JSONLParser:
    """
    Parses JSONL output from CLI.

    Usage:
        parser = JSONLParser()
        for line in output_lines:
            event = parser.parse_line(line)
            if event:
                process_event(event)
    """

    # Patterns for inferring log level from plain text
    ERROR_PATTERNS = [
        r'\berror\b',
        r'\bfailed\b',
        r'\bexception\b',
        r'\btraceback\b',
        r'\bcritical\b',
    ]
    WARN_PATTERNS = [
        r'\bwarning\b',
        r'\bwarn\b',
        r'\bdeprecated\b',
    ]
    DEBUG_PATTERNS = [
        r'\bdebug\b',
        r'\btrace\b',
        r'\bverbose\b',
    ]

    def __init__(self):
        self._error_re = re.compile('|'.join(self.ERROR_PATTERNS), re.IGNORECASE)
        self._warn_re = re.compile('|'.join(self.WARN_PATTERNS), re.IGNORECASE)
        self._debug_re = re.compile('|'.join(self.DEBUG_PATTERNS), re.IGNORECASE)

    def parse_line(self, line: str) -> Optional[Event]:
        """
        Parse a single line of output.

        Args:
            line: Raw line from CLI stdout

        Returns:
            Parsed event or None if line is empty
        """
        line = line.strip()
        if not line:
            return None

        # Try to parse as JSON
        if line.startswith("{"):
            try:
                data = json.loads(line)
                return self._parse_json_event(data, line)
            except json.JSONDecodeError:
                pass  # Fall through to plain text handling

        # Handle as plain text
        return self._parse_plain_text(line)

    def _parse_json_event(self, data: Dict[str, Any], raw_line: str) -> Event:
        """Parse a JSON event object."""
        event_type = data.get("type", "raw")
        timestamp = self._parse_timestamp(data.get("ts"))

        if event_type == "start":
            return StartEvent(
                timestamp=timestamp,
                raw_line=raw_line,
                phase=data.get("phase", "init"),
            )

        elif event_type == "progress":
            return ProgressEvent(
                timestamp=timestamp,
                raw_line=raw_line,
                phase=data.get("phase", ""),
                percent=int(data.get("percent", 0)),
                message=data.get("message"),
            )

        elif event_type == "log":
            # Handle case-insensitive log level
            level_str = data.get("level", "info").lower()
            return LogEvent(
                timestamp=timestamp,
                raw_line=raw_line,
                level=LogLevel(level_str),
                message=data.get("message", ""),
            )

        elif event_type == "checkpoint":
            return CheckpointEvent(
                timestamp=timestamp,
                raw_line=raw_line,
                checkpoint_id=data.get("id", ""),
                phase=data.get("phase", ""),
                percent=int(data.get("percent", 0)),
                state_data=data.get("state", {}),
            )

        elif event_type == "error":
            return ErrorEvent(
                timestamp=timestamp,
                raw_line=raw_line,
                message=data.get("message", "Unknown error"),
                details=data.get("details"),
            )

        elif event_type == "complete":
            return CompleteEvent(
                timestamp=timestamp,
                raw_line=raw_line,
                exit_code=int(data.get("exit_code", 0)),
                result=data.get("result"),
            )

        elif event_type == "cancelled":
            return ErrorEvent(
                type=EventType.CANCELLED,
                timestamp=timestamp,
                raw_line=raw_line,
                message=data.get("message", "Job cancelled"),
            )

        elif event_type == "raw":
            # Explicit raw type or no type specified
            return RawEvent(
                timestamp=timestamp,
                raw_line=raw_line,
                content=json.dumps(data),
                inferred_level=LogLevel.INFO,
            )

        else:
            # Unknown type, treat as log
            return LogEvent(
                timestamp=timestamp,
                raw_line=raw_line,
                level=LogLevel.INFO,
                message=json.dumps(data),
            )

    def _parse_plain_text(self, line: str) -> RawEvent:
        """Parse plain text line as raw event."""
        level = self._infer_log_level(line)
        return RawEvent(
            timestamp=datetime.utcnow(),
            raw_line=line,
            content=line,
            inferred_level=level,
        )

    def _parse_timestamp(self, ts: Optional[str]) -> datetime:
        """Parse ISO timestamp or return current time."""
        if not ts:
            return datetime.utcnow()

        try:
            # Handle various ISO formats
            ts = ts.replace("Z", "+00:00")
            if "+" not in ts and "-" not in ts[10:]:
                ts += "+00:00"
            return datetime.fromisoformat(ts.replace("+00:00", ""))
        except (ValueError, TypeError):
            return datetime.utcnow()

    def _infer_log_level(self, line: str) -> LogLevel:
        """Infer log level from plain text content."""
        if self._error_re.search(line):
            return LogLevel.ERROR
        if self._warn_re.search(line):
            return LogLevel.WARN
        if self._debug_re.search(line):
            return LogLevel.DEBUG
        return LogLevel.INFO


def event_to_db_dict(event: Event, job_id: str, sequence: int) -> Dict[str, Any]:
    """
    Convert event to dictionary for database insertion.

    Args:
        event: Parsed event
        job_id: Job identifier
        sequence: Sequence number within job

    Returns:
        Dictionary ready for JobEvent model
    """
    base = {
        "job_id": job_id,
        "sequence": sequence,
        "event_type": event.type.value,
        "timestamp": event.timestamp,
        "data": event.to_dict(),
    }

    # Add log_level for log-like events
    if isinstance(event, LogEvent):
        base["log_level"] = event.level.value
    elif isinstance(event, RawEvent):
        base["log_level"] = event.inferred_level.value
    elif isinstance(event, ErrorEvent):
        base["log_level"] = LogLevel.ERROR.value

    return base


def event_to_sse_dict(event: Event, sequence: int) -> Dict[str, Any]:
    """
    Convert event to dictionary for SSE streaming.

    Args:
        event: Parsed event
        sequence: Sequence number for SSE id

    Returns:
        Dictionary for SSE data field
    """
    if isinstance(event, ProgressEvent):
        return {
            "phase": event.phase,
            "percent": event.percent,
            "message": event.message,
            "timestamp": event.timestamp.isoformat(),
        }

    elif isinstance(event, LogEvent):
        return {
            "level": event.level.value,
            "message": event.message,
            "timestamp": event.timestamp.isoformat(),
        }

    elif isinstance(event, RawEvent):
        return {
            "level": event.inferred_level.value,
            "message": event.content,
            "timestamp": event.timestamp.isoformat(),
        }

    elif isinstance(event, CheckpointEvent):
        return {
            "id": event.checkpoint_id,
            "phase": event.phase,
            "percent": event.percent,
            "timestamp": event.timestamp.isoformat(),
        }

    elif isinstance(event, StartEvent):
        return {
            "phase": event.phase,
            "timestamp": event.timestamp.isoformat(),
        }

    elif isinstance(event, CompleteEvent):
        return {
            "exit_code": event.exit_code,
            "result": event.result,
            "timestamp": event.timestamp.isoformat(),
        }

    elif isinstance(event, ErrorEvent):
        return {
            "message": event.message,
            "details": event.details,
            "timestamp": event.timestamp.isoformat(),
        }

    return event.to_dict()
