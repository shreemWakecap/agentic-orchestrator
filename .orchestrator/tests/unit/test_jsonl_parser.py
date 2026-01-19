"""
Unit tests for JSONL parser.
"""
import pytest
from datetime import datetime


class TestJSONLParser:
    """Tests for JSONL parsing."""

    @pytest.fixture
    def parser(self):
        from portal.services.jsonl_parser import JSONLParser
        return JSONLParser()

    def test_parse_start_event(self, parser):
        """Test parsing start event."""
        from portal.services.jsonl_parser import StartEvent, EventType

        line = '{"type":"start","phase":"init","ts":"2025-01-19T10:30:00Z"}'
        event = parser.parse_line(line)

        assert isinstance(event, StartEvent)
        assert event.type == EventType.START
        assert event.phase == "init"

    def test_parse_progress_event(self, parser):
        """Test parsing progress event."""
        from portal.services.jsonl_parser import ProgressEvent

        line = '{"type":"progress","phase":"analyzing","percent":50,"message":"Working"}'
        event = parser.parse_line(line)

        assert isinstance(event, ProgressEvent)
        assert event.phase == "analyzing"
        assert event.percent == 50
        assert event.message == "Working"

    def test_parse_log_event(self, parser):
        """Test parsing log event."""
        from portal.services.jsonl_parser import LogEvent, LogLevel

        line = '{"type":"log","level":"warn","message":"Something happened"}'
        event = parser.parse_line(line)

        assert isinstance(event, LogEvent)
        assert event.level == LogLevel.WARN
        assert event.message == "Something happened"

    def test_parse_log_event_default_level(self, parser):
        """Test log event defaults to info level."""
        from portal.services.jsonl_parser import LogEvent, LogLevel

        line = '{"type":"log","message":"Info message"}'
        event = parser.parse_line(line)

        assert isinstance(event, LogEvent)
        assert event.level == LogLevel.INFO
        assert event.message == "Info message"

    def test_parse_checkpoint_event(self, parser):
        """Test parsing checkpoint event."""
        from portal.services.jsonl_parser import CheckpointEvent

        line = '{"type":"checkpoint","id":"chk_001","phase":"processing","percent":75,"state":{"items":100}}'
        event = parser.parse_line(line)

        assert isinstance(event, CheckpointEvent)
        assert event.checkpoint_id == "chk_001"
        assert event.phase == "processing"
        assert event.percent == 75
        assert event.state_data == {"items": 100}

    def test_parse_error_event(self, parser):
        """Test parsing error event."""
        from portal.services.jsonl_parser import ErrorEvent

        line = '{"type":"error","message":"Something failed","details":"Stack trace here"}'
        event = parser.parse_line(line)

        assert isinstance(event, ErrorEvent)
        assert event.message == "Something failed"
        assert event.details == "Stack trace here"

    def test_parse_complete_event(self, parser):
        """Test parsing complete event."""
        from portal.services.jsonl_parser import CompleteEvent

        line = '{"type":"complete","exit_code":0,"result":{"output":"file.txt"}}'
        event = parser.parse_line(line)

        assert isinstance(event, CompleteEvent)
        assert event.exit_code == 0
        assert event.result == {"output": "file.txt"}

    def test_parse_complete_event_with_error(self, parser):
        """Test parsing complete event with non-zero exit code."""
        from portal.services.jsonl_parser import CompleteEvent

        line = '{"type":"complete","exit_code":1}'
        event = parser.parse_line(line)

        assert isinstance(event, CompleteEvent)
        assert event.exit_code == 1

    def test_parse_plain_text(self, parser):
        """Test plain text fallback."""
        from portal.services.jsonl_parser import RawEvent, LogLevel

        line = "Just a regular log line"
        event = parser.parse_line(line)

        assert isinstance(event, RawEvent)
        assert event.content == line
        assert event.inferred_level == LogLevel.INFO

    def test_infer_error_level(self, parser):
        """Test error level inference from text."""
        from portal.services.jsonl_parser import RawEvent, LogLevel

        line = "ERROR: Something failed badly"
        event = parser.parse_line(line)

        assert isinstance(event, RawEvent)
        assert event.inferred_level == LogLevel.ERROR

    def test_infer_error_level_exception(self, parser):
        """Test error level inference for exceptions."""
        from portal.services.jsonl_parser import RawEvent, LogLevel

        line = "Exception occurred: ValueError"
        event = parser.parse_line(line)

        assert isinstance(event, RawEvent)
        assert event.inferred_level == LogLevel.ERROR

    def test_infer_warning_level(self, parser):
        """Test warning level inference from text."""
        from portal.services.jsonl_parser import RawEvent, LogLevel

        line = "WARNING: Deprecated API used"
        event = parser.parse_line(line)

        assert isinstance(event, RawEvent)
        assert event.inferred_level == LogLevel.WARN

    def test_infer_debug_level(self, parser):
        """Test debug level inference from text."""
        from portal.services.jsonl_parser import RawEvent, LogLevel

        line = "DEBUG: Internal state info"
        event = parser.parse_line(line)

        assert isinstance(event, RawEvent)
        assert event.inferred_level == LogLevel.DEBUG

    def test_empty_line(self, parser):
        """Test empty line returns None."""
        assert parser.parse_line("") is None
        assert parser.parse_line("   ") is None

    def test_invalid_json(self, parser):
        """Test invalid JSON falls back to plain text."""
        from portal.services.jsonl_parser import RawEvent

        line = "{this is not valid json"
        event = parser.parse_line(line)

        assert isinstance(event, RawEvent)
        assert event.content == line

    def test_json_without_type(self, parser):
        """Test JSON without type field falls back to raw."""
        from portal.services.jsonl_parser import RawEvent

        line = '{"message":"No type field"}'
        event = parser.parse_line(line)

        assert isinstance(event, RawEvent)

    def test_timestamp_parsing(self, parser):
        """Test timestamp is parsed correctly."""
        from portal.services.jsonl_parser import ProgressEvent

        line = '{"type":"progress","phase":"test","percent":10,"ts":"2025-01-19T10:30:00Z"}'
        event = parser.parse_line(line)

        assert isinstance(event, ProgressEvent)
        assert event.timestamp is not None
        assert isinstance(event.timestamp, datetime)

    def test_event_to_dict(self, parser):
        """Test event serialization to dict."""
        line = '{"type":"progress","phase":"test","percent":50}'
        event = parser.parse_line(line)

        d = event.to_dict()
        assert d["type"] == "progress"
        assert d["phase"] == "test"
        assert d["percent"] == 50
        assert "timestamp" in d

    def test_parse_multiple_lines(self, parser, mock_cli_output):
        """Test parsing multiple lines of CLI output."""
        events = [parser.parse_line(line) for line in mock_cli_output]

        # All lines should parse successfully
        assert len([e for e in events if e is not None]) == 6

    def test_case_insensitive_level(self, parser):
        """Test that log levels are case-insensitive."""
        from portal.services.jsonl_parser import LogEvent, LogLevel

        line = '{"type":"log","level":"ERROR","message":"Test"}'
        event = parser.parse_line(line)

        assert isinstance(event, LogEvent)
        # Level should be normalized
        assert event.level in [LogLevel.ERROR, "ERROR", "error"]
