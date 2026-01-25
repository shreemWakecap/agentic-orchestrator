#!/usr/bin/env python3
"""CLI - dispatcher for workflows and commands.

This is the main entry point for the SDLC Orchestrator.
Supports both single-project mode (embedded) and multi-project mode (standalone).

Multi-Project Mode:
    Set SDLC_ORCHESTRATOR_HOME environment variable to enable.
    Example: export SDLC_ORCHESTRATOR_HOME=/path/to/orchestrator/home

Usage:
    orch init                          Initialize orchestrator home
    orch project list                  List all projects
    orch project add <path>            Add local project
    orch project switch <name>         Switch to project
    orch plan "request"                Create plan (requires active project)
    orch build [plan_id]               Execute plan
    orch scout                         Analyze codebase
    orch sync                          Sync to git
    orch portal                        Start web portal
"""
import sys
from pathlib import Path

# Add orchestrator directory to path
ORCHESTRATOR_DIR = Path(__file__).parent
sys.path.insert(0, str(ORCHESTRATOR_DIR))

# Import unified config to ensure dotenv is loaded
import config as _config  # noqa: F401

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
    'init': 'run_init',
    'project': 'run_project',
    'migrate-to-db': 'run_migrate_to_db',
    'cleanup-files': 'run_cleanup_files',
}


def _print_help():
    """Print help message."""
    config = _config.get_config()
    mode = "multi-project" if config.is_multi_project_mode else "single-project"

    print("SDLC Orchestrator (orch)")
    print(f"Mode: {mode}")
    if config.is_multi_project_mode:
        print(f"Home: {config.orchestrator_home.home_path}")
    print()

    print("Initialization:")
    print("  init               Initialize orchestrator (multi-project mode)")
    print()

    print("Project Management (multi-project mode):")
    print("  project list       List all projects")
    print("  project add        Add a project (local or git)")
    print("  project switch     Switch active project")
    print("  project info       Show project details")
    print("  project archive    Archive a project")
    print("  project remove     Remove a project")
    print()

    print("Workflows (require active project in multi-project mode):")
    print("  plan <request>     Create implementation plan from request")
    print("  build [plan_id]    Execute plan and implement code")
    print("  sync               Sync changes: create PR, merge, and pull")
    print("  scout              Analyze codebase (legacy)")
    print("  smart-scout        Multi-phase codebase analysis (recommended)")
    print()

    print("Commands:")
    print("  portal             Start web portal")
    print("  setup              Initialize environment (single-project mode)")
    print("  experts            Manage expert agents")
    print("  knowledge          View knowledge store status")
    print("  git-status         Show git statistics")
    print("  migrate-to-db      Migrate agents/experts/config from files to DB")
    print("  cleanup-files      Remove old files after DB migration")
    print()

    print("Options:")
    print("  -h, --help         Show this help message")
    print("  -v, --version      Show version")


def _print_version():
    """Print version information."""
    print("SDLC Orchestrator v2.0.0")


def main():
    """Main entry point."""
    if len(sys.argv) < 2 or sys.argv[1] in ['-h', '--help']:
        _print_help()
        return 0

    if sys.argv[1] in ['-v', '--version']:
        _print_version()
        return 0

    cmd = sys.argv[1]
    args = sys.argv[2:]

    # Handle workflows
    if cmd in WORKFLOWS:
        module = __import__(f"workflows.{WORKFLOWS[cmd]}", fromlist=['run'])
        return module.run(args)

    # Handle commands
    if cmd in COMMANDS:
        import commands
        return getattr(commands, COMMANDS[cmd])(args)

    # Unknown command
    all_cmds = list(WORKFLOWS.keys()) + list(COMMANDS.keys())
    print(f"Unknown command: {cmd}")
    print(f"Available: {', '.join(sorted(all_cmds))}")
    print("\nRun 'orch --help' for usage information.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
