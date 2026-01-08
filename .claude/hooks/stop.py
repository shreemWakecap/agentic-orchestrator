#!/usr/bin/env python3
"""
Stop hook for orchestrator.
Logs session completion and saves final state.
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

        # Extract session info
        session_id = input_data.get("session_id", "unknown")
        stop_hook_active = input_data.get("stop_hook_active", False)

        # Ensure log directory exists
        project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
        log_dir = Path(project_dir) / "orchistrator" / "runs" / "_logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        # Read existing stop log or initialize
        stop_log_file = log_dir / "stop.json"
        if stop_log_file.exists():
            try:
                with open(stop_log_file, "r") as f:
                    log_data = json.load(f)
            except (json.JSONDecodeError, ValueError):
                log_data = []
        else:
            log_data = []

        # Append new entry
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "session_id": session_id,
            "stop_hook_active": stop_hook_active,
            "input_data": input_data
        }
        log_data.append(log_entry)

        # Write back to file
        with open(stop_log_file, "w") as f:
            json.dump(log_data, f, indent=2)

        # Also log to jsonl for consistency
        jsonl_file = log_dir / "tool_use.jsonl"
        jsonl_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "session_id": session_id,
            "hook": "stop",
            "stop_hook_active": stop_hook_active
        }
        with open(jsonl_file, "a") as f:
            f.write(json.dumps(jsonl_entry) + "\n")

        sys.exit(0)

    except json.JSONDecodeError:
        sys.exit(0)
    except Exception:
        sys.exit(0)


if __name__ == "__main__":
    main()
