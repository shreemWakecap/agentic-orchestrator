#!/usr/bin/env python3
"""
SDLC Orchestrator - Run Workflows

Usage:
    uv run python .orchestrator/run.py plan "Add user authentication"
    uv run python .orchestrator/run.py plan "Build a REST API"
"""
import sys
from pathlib import Path

# Project root is parent of .orchestrator
PROJECT_ROOT = Path(__file__).parent.parent

# Add .orchestrator to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from workflows.planning import PlanningWorkflow


def main():
    if len(sys.argv) < 2:
        print("SDLC Orchestrator")
        print()
        print("Usage:")
        print("  uv run python .orchestrator/run.py plan 'Your request'")
        print()
        print("Workflows:")
        print("  plan    Create an implementation plan")
        print()
        print("Example:")
        print("  uv run python .orchestrator/run.py plan 'Add user authentication'")
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
    else:
        print(f"Unknown command: {command}")
        print("Available: plan")
        sys.exit(1)


if __name__ == "__main__":
    main()
