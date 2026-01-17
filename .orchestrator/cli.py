#!/usr/bin/env python3
"""CLI - thin wrapper for actions."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

ACTIONS = {
    'plan': 'planning',
    'build': 'building',
    'sync': 'syncing',
    'setup': 'setup',
    'list': 'list',
    'portal': 'portal',
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ['-h', '--help']:
        print("Agentic Orchestrator\n")
        print("Commands:")
        print("  plan <request>   Create implementation plan from request")
        print("  build <path>     Execute plan and implement code")
        print("  portal           Start web portal")
        print("  list             List all plans")
        print("  sync             Sync changes: create PR, merge, and pull to local")
        return 0

    cmd = sys.argv[1]
    if cmd not in ACTIONS:
        print(f"Unknown: {cmd}. Try: {', '.join(ACTIONS.keys())}")
        return 1

    module = __import__(f"actions.{ACTIONS[cmd]}", fromlist=['run'])
    return module.run(sys.argv[2:])


if __name__ == "__main__":
    sys.exit(main())
