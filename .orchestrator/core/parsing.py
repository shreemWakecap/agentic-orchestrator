"""Shared parsing utilities for agent responses.

This module consolidates the duplicate parsing logic that was previously
in building.py (lines 863-903) and syncing.py (lines 168-220).

Functions here are pure and have no side effects, making them easy to test.
"""
import json
import re
from typing import Optional, List, Dict, Any


def parse_json_from_response(content: str) -> Optional[Dict[str, Any]]:
    """Extract JSON object from agent response text.

    Handles JSON embedded in:
    - Markdown code blocks (```json ... ```)
    - Plain code blocks (``` ... ```)
    - Raw JSON in text

    Args:
        content: Agent response text that may contain JSON

    Returns:
        Parsed JSON as dict, or None if no valid JSON found
    """
    if not content:
        return None

    # Try to find JSON in code blocks first (more specific to less specific)
    patterns = [
        (r'```json\s*([\s\S]*?)\s*```', 1),  # JSON code block
        (r'```\s*([\s\S]*?)\s*```', 1),       # Any code block
        (r'(\{[\s\S]*\})', 0),                 # Raw JSON object
    ]

    for pattern, group in patterns:
        match = re.search(pattern, content)
        if match:
            try:
                json_str = match.group(group) if group else match.group(1)
                return json.loads(json_str)
            except json.JSONDecodeError:
                continue

    return None


def parse_json_array_from_response(content: str) -> Optional[List[Any]]:
    """Extract JSON array from agent response text.

    Similar to parse_json_from_response but looks for arrays.

    Args:
        content: Agent response text that may contain JSON array

    Returns:
        Parsed JSON as list, or None if no valid JSON array found
    """
    if not content:
        return None

    patterns = [
        r'```json\s*([\s\S]*?)\s*```',
        r'```\s*([\s\S]*?)\s*```',
        r'(\[[\s\S]*\])',
    ]

    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            try:
                result = json.loads(match.group(1))
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                continue

    return None


def parse_key_value_response(content: str) -> Dict[str, Any]:
    """Parse key-value formatted agent response.

    Handles formats like:
        KEY: value
        KEY:
        - item1
        - item2

    This consolidates the duplicate _parse_key_value() methods from
    building.py and syncing.py.

    Args:
        content: Agent response text with key-value pairs

    Returns:
        Dict with parsed key-value pairs
    """
    result = {}
    current_key = None
    current_list = []

    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue

        # Check for new key (line has : but doesn't start with -)
        if ':' in line and not line.startswith('-'):
            # Save previous key if exists
            if current_key and current_list:
                result[current_key] = current_list if len(current_list) > 1 else current_list[0]
                current_list = []

            key, _, value = line.partition(':')
            current_key = key.strip().lower().replace(' ', '_')
            value = value.strip()
            if value:
                result[current_key] = value
                current_key = None
        elif line.startswith('-') and current_key:
            # List item for current key
            current_list.append(line[1:].strip())

    # Save last key if still active
    if current_key and current_list:
        result[current_key] = current_list if len(current_list) > 1 else current_list[0]

    return result


def extract_code_blocks(content: str, language: Optional[str] = None) -> List[str]:
    """Extract fenced code blocks from markdown content.

    Args:
        content: Markdown content with code blocks
        language: Optional language filter (e.g., 'python', 'json')
                  If None, extracts all code blocks

    Returns:
        List of code block contents (without the fences)
    """
    if not content:
        return []

    if language:
        pattern = rf'```{re.escape(language)}\s*([\s\S]*?)\s*```'
    else:
        pattern = r'```(?:\w+)?\s*([\s\S]*?)\s*```'

    return re.findall(pattern, content)


def extract_file_path(content: str) -> Optional[str]:
    """Extract a file path from agent response.

    Looks for common patterns like:
    - File: path/to/file.py
    - Path: path/to/file.py
    - path/to/file.py (if it looks like a path)

    Args:
        content: Agent response text

    Returns:
        Extracted file path or None
    """
    if not content:
        return None

    # Try explicit labels first
    patterns = [
        r'(?:File|Path):\s*([^\s\n]+)',
        r'`([^`]+\.[a-zA-Z]+)`',  # Backtick-quoted paths
    ]

    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def extract_step_id(content: str) -> Optional[str]:
    """Extract a step ID from agent response.

    Looks for patterns like:
    - Step ID: step_1
    - step: step_1
    - [step_1]

    Args:
        content: Agent response text

    Returns:
        Extracted step ID or None
    """
    if not content:
        return None

    patterns = [
        r'(?:Step(?:\s+ID)?|step):\s*(\S+)',
        r'\[(\w+_\d+)\]',
    ]

    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def clean_response(content: str) -> str:
    """Clean agent response by removing common artifacts.

    Removes:
    - Leading/trailing whitespace
    - Multiple consecutive newlines
    - Common response prefixes

    Args:
        content: Raw agent response

    Returns:
        Cleaned response text
    """
    if not content:
        return ""

    # Remove common prefixes
    prefixes_to_remove = [
        "Here's ",
        "Here is ",
        "Sure, ",
        "Of course, ",
        "Certainly, ",
    ]

    result = content.strip()
    for prefix in prefixes_to_remove:
        if result.lower().startswith(prefix.lower()):
            result = result[len(prefix):]

    # Collapse multiple newlines to double newline
    result = re.sub(r'\n{3,}', '\n\n', result)

    return result.strip()


def parse_commit_info(content: str) -> Dict[str, Any]:
    """Parse commit information from agent response.

    Extracts:
    - commit_message: The commit message
    - files_changed: List of changed files
    - branch: Branch name if mentioned

    Args:
        content: Agent response about a commit

    Returns:
        Dict with parsed commit information
    """
    result = {}

    # Try to find commit message
    msg_patterns = [
        r'(?:Commit\s+)?[Mm]essage:\s*["\']?(.+?)["\']?\s*(?:\n|$)',
        r'```\s*\n(.+?)\n```',
    ]

    for pattern in msg_patterns:
        match = re.search(pattern, content)
        if match:
            result['commit_message'] = match.group(1).strip()
            break

    # Try to find files changed
    files_pattern = r'(?:Files?\s+changed|Modified|Changed):\s*\n((?:\s*[-*]\s*.+\n?)+)'
    files_match = re.search(files_pattern, content, re.IGNORECASE)
    if files_match:
        files_text = files_match.group(1)
        files = re.findall(r'[-*]\s*(.+)', files_text)
        result['files_changed'] = [f.strip() for f in files]

    # Try to find branch name
    branch_pattern = r'[Bb]ranch:\s*(\S+)'
    branch_match = re.search(branch_pattern, content)
    if branch_match:
        result['branch'] = branch_match.group(1)

    return result
