#!/usr/bin/env python3
"""
SDLC Orchestrator - Run Workflows

Usage:
    uv run python .orchestrator/run.py plan "Add user authentication"
    uv run python .orchestrator/run.py build .specs/pending/user-auth.md
    uv run python .orchestrator/run.py list
"""
import sys
from pathlib import Path

# Project root is parent of .orchestrator
PROJECT_ROOT = Path(__file__).parent.parent
SPECS_DIR = PROJECT_ROOT / ".specs"

# Add .orchestrator to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from workflows.planning import PlanningWorkflow
from workflows.building import BuildingWorkflow


def list_plans():
    """List all plans in .specs directory."""
    print("SDLC Plans")
    print("=" * 60)

    for status in ["pending", "in-progress", "completed", "failed"]:
        status_dir = SPECS_DIR / status
        if not status_dir.exists():
            continue

        plans = list(status_dir.glob("*.md"))
        if not plans:
            continue

        color = {
            "pending": "\033[33m",      # Yellow
            "in-progress": "\033[36m",  # Cyan
            "completed": "\033[32m",    # Green
            "failed": "\033[31m"        # Red
        }.get(status, "")
        reset = "\033[0m"

        print(f"\n{color}{status.upper()}{reset} ({len(plans)})")
        print("-" * 40)
        for plan in sorted(plans):
            print(f"  {plan.name}")

    # Also check root
    root_plans = list(SPECS_DIR.glob("*.md"))
    if root_plans:
        print(f"\n[ROOT] ({len(root_plans)})")
        print("-" * 40)
        for plan in sorted(root_plans):
            print(f"  {plan.name}")


def main():
    if len(sys.argv) < 2:
        print("SDLC Orchestrator")
        print()
        print("Usage:")
        print("  uv run python .orchestrator/run.py plan 'Your request'")
        print("  uv run python .orchestrator/run.py build <plan-file>")
        print("  uv run python .orchestrator/run.py list")
        print()
        print("Workflows:")
        print("  plan     Create an implementation plan")
        print("  build    Execute a plan to build the feature")
        print("  list     List all plans and their status")
        print()
        print("Examples:")
        print("  uv run python .orchestrator/run.py plan 'Add user authentication'")
        print("  uv run python .orchestrator/run.py build .specs/pending/user-auth.md")
        print("  uv run python .orchestrator/run.py build user-auth.md")
        sys.exit(1)

    command = sys.argv[1]
    args = sys.argv[2:]

    if command == "plan":
        if not args:
            print("Error: Please provide a request")
            print("Usage: uv run python .orchestrator/run.py plan 'Your request'")
            sys.exit(1)

        request = " ".join(args)
        workflow = PlanningWorkflow(project_root=PROJECT_ROOT)
        result = workflow.run(request)

        sys.exit(0 if result.success else 1)

    elif command == "build":
        if not args:
            print("Error: Please provide a plan file")
            print("Usage: uv run python .orchestrator/run.py build <plan-file>")
            print()
            print("Available plans:")
            list_plans()
            sys.exit(1)

        plan_path = args[0]
        workflow = BuildingWorkflow(project_root=PROJECT_ROOT)
        result = workflow.run(plan_path)

        sys.exit(0 if result.success else 1)

    elif command == "list":
        list_plans()
        sys.exit(0)

    else:
        print(f"Unknown command: {command}")
        print("Available: plan, build, list")
        sys.exit(1)


if __name__ == "__main__":
    main()
