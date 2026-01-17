"""Tests for the parsing utilities.

These are pure function tests that don't require any mocking.
"""
import pytest
import sys
from pathlib import Path

# Add orchestrator to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.parsing import (
    parse_json_from_response,
    parse_json_array_from_response,
    parse_key_value_response,
    extract_code_blocks,
    extract_file_path,
    clean_response,
)


class TestParseJsonFromResponse:
    """Tests for parse_json_from_response."""

    def test_empty_content(self):
        """Should return None for empty content."""
        assert parse_json_from_response("") is None
        assert parse_json_from_response(None) is None

    def test_json_code_block(self):
        """Should extract JSON from code block."""
        content = '''Here's the result:
```json
{"key": "value", "number": 42}
```
'''
        result = parse_json_from_response(content)
        assert result == {"key": "value", "number": 42}

    def test_plain_code_block(self):
        """Should extract JSON from plain code block."""
        content = '''Result:
```
{"status": "ok"}
```
'''
        result = parse_json_from_response(content)
        assert result == {"status": "ok"}

    def test_raw_json(self):
        """Should extract raw JSON object."""
        content = 'The response is {"name": "test"} as expected.'
        result = parse_json_from_response(content)
        assert result == {"name": "test"}

    def test_invalid_json(self):
        """Should return None for invalid JSON."""
        content = '{"invalid": json}'
        result = parse_json_from_response(content)
        assert result is None


class TestParseKeyValueResponse:
    """Tests for parse_key_value_response."""

    def test_simple_key_value(self):
        """Should parse simple key-value pairs."""
        content = """Name: Test
Status: completed
Count: 5"""
        result = parse_key_value_response(content)
        assert result["name"] == "Test"
        assert result["status"] == "completed"
        assert result["count"] == "5"

    def test_key_with_list(self):
        """Should parse keys with list values."""
        content = """Files:
- file1.py
- file2.py
- file3.py"""
        result = parse_key_value_response(content)
        assert result["files"] == ["file1.py", "file2.py", "file3.py"]

    def test_mixed_content(self):
        """Should handle mix of values and lists."""
        content = """Status: success
Modified Files:
- src/main.py
- tests/test.py
Message: All done"""
        result = parse_key_value_response(content)
        assert result["status"] == "success"
        assert result["modified_files"] == ["src/main.py", "tests/test.py"]
        assert result["message"] == "All done"

    def test_empty_content(self):
        """Should return empty dict for empty content."""
        assert parse_key_value_response("") == {}


class TestExtractCodeBlocks:
    """Tests for extract_code_blocks."""

    def test_single_block(self):
        """Should extract single code block."""
        content = '''Here's some code:
```python
print("hello")
```
'''
        blocks = extract_code_blocks(content, "python")
        assert len(blocks) == 1
        assert 'print("hello")' in blocks[0]

    def test_multiple_blocks(self):
        """Should extract multiple code blocks."""
        content = '''
```python
code1
```
Some text
```python
code2
```
'''
        blocks = extract_code_blocks(content, "python")
        assert len(blocks) == 2

    def test_any_language(self):
        """Should extract blocks of any language when no filter."""
        content = '''
```python
python code
```
```javascript
js code
```
'''
        blocks = extract_code_blocks(content)
        assert len(blocks) == 2

    def test_no_blocks(self):
        """Should return empty list when no blocks found."""
        assert extract_code_blocks("no code here") == []


class TestExtractFilePath:
    """Tests for extract_file_path."""

    def test_file_label(self):
        """Should extract path with File: label."""
        content = "File: src/main.py"
        assert extract_file_path(content) == "src/main.py"

    def test_path_label(self):
        """Should extract path with Path: label."""
        content = "Path: tests/test_file.py"
        assert extract_file_path(content) == "tests/test_file.py"

    def test_backtick_path(self):
        """Should extract path in backticks."""
        content = "The file `src/utils.py` was modified."
        assert extract_file_path(content) == "src/utils.py"

    def test_no_path(self):
        """Should return None when no path found."""
        assert extract_file_path("no file path here") is None


class TestCleanResponse:
    """Tests for clean_response."""

    def test_removes_prefix(self):
        """Should remove common response prefixes."""
        content = "Here's the result: some text"
        assert clean_response(content) == "the result: some text"

    def test_strips_whitespace(self):
        """Should strip leading/trailing whitespace."""
        content = "   some text   "
        assert clean_response(content) == "some text"

    def test_collapses_newlines(self):
        """Should collapse multiple newlines."""
        content = "line1\n\n\n\nline2"
        assert clean_response(content) == "line1\n\nline2"

    def test_empty_content(self):
        """Should return empty string for empty input."""
        assert clean_response("") == ""
        assert clean_response(None) == ""
