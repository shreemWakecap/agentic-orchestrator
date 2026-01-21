#!/usr/bin/env python3
"""CLI - dispatcher for workflows and commands."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Workflows: complex multi-step agent orchestration
WORKFLOWS = {
    'plan': 'planning',
    'build': 'building',
    'sync': 'syncing',
    'scout': 'scouting',
    'smart-scout': 'smart_scouting',
}

# Commands: simple utilities
COMMANDS = {
    'portal': 'run_portal',
    'setup': 'run_setup',
    'experts': 'run_experts',
    'knowledge': 'run_knowledge',
    'git-status': 'run_git_status',
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ['-h', '--help']:
        print("Agentic Orchestrator\n")
        print("Workflows:")
        print("  plan <request>   Create implementation plan from request")
        print("  build <path>     Execute plan and implement code")
        print("  sync             Sync changes: create PR, merge, and pull to local")
        print("  scout            Analyze codebase and build knowledge store (legacy)")
        print("  smart-scout      Multi-phase, guided codebase analysis (recommended)")
        print("\nCommands:")
        print("  portal           Start web portal")
        print("  setup            Initialize orchestrator environment")
        print("  experts          Manage expert agents (list, create, refresh)")
        print("  knowledge        View knowledge store status")
        print("  git-status       Show git statistics (--json, --verbose)")
        return 0

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd in WORKFLOWS:
        module = __import__(f"workflows.{WORKFLOWS[cmd]}", fromlist=['run'])
        return module.run(args)

    if cmd in COMMANDS:
        import commands
        return getattr(commands, COMMANDS[cmd])(args)

    all_cmds = list(WORKFLOWS.keys()) + list(COMMANDS.keys())
    print(f"Unknown: {cmd}. Try: {', '.join(all_cmds)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
