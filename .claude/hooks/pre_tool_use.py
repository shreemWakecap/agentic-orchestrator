#!/usr/bin/env python3
"""
Pre-tool-use hook for orchestrator.
Logs tool invocations for audit trail.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path


def main():
    try:
        # Read JSON input from stdin
        input_data = json.load(sys.stdin)

        # Extract tool info
        tool_name = input_data.get("tool_name", "unknown")
        tool_input = input_data.get("tool_input", {})
        session_id = input_data.get("session_id", "unknown")

        # Ensure log directory exists
        project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
        log_dir = Path(project_dir) / "orchistrator" / "runs" / "_logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        # Log to file
        log_file = log_dir / "tool_use.jsonl"
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "session_id": session_id,
            "hook": "pre_tool_use",
            "tool_name": tool_name,
            "tool_input_keys": list(tool_input.keys()) if isinstance(tool_input, dict) else []
        }

        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

        # Exit successfully (don't block the tool)
        sys.exit(0)

    except json.JSONDecodeError:
        # Invalid JSON input, exit silently
        sys.exit(0)
    except Exception:
        # Any other error, exit silently
        sys.exit(0)


if __name__ == "__main__":
    main()
