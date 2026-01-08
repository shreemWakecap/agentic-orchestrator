#!/usr/bin/env python3
"""
Post-tool-use hook for orchestrator.
Tracks file changes after Write/Edit operations.
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def get_changed_files():
    """Get list of changed files from git."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        pass
    return []


def main():
    try:
        # Read JSON input from stdin
        input_data = json.load(sys.stdin)

        # Extract tool info
        tool_name = input_data.get("tool_name", "unknown")
        tool_input = input_data.get("tool_input", {})
        session_id = input_data.get("session_id", "unknown")

        # Ensure directories exist
        project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
        log_dir = Path(project_dir) / "orchistrator" / "runs" / "_logs"
        last_dir = Path(project_dir) / "orchistrator" / "runs" / "_last"
        log_dir.mkdir(parents=True, exist_ok=True)
        last_dir.mkdir(parents=True, exist_ok=True)

        # Get changed files
        changed_files = get_changed_files()

        # Write changed files to _last directory
        changed_file = last_dir / "changed_files.txt"
        with open(changed_file, "w") as f:
            f.write("\n".join(changed_files))

        # Log to file
        log_file = log_dir / "tool_use.jsonl"
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "session_id": session_id,
            "hook": "post_tool_use",
            "tool_name": tool_name,
            "changed_files": changed_files,
            "file_path": tool_input.get("file_path", tool_input.get("path", ""))
        }

        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

        # Exit successfully
        sys.exit(0)

    except json.JSONDecodeError:
        sys.exit(0)
    except Exception:
        sys.exit(0)


if __name__ == "__main__":
    main()
