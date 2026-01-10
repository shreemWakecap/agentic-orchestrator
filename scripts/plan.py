#!/usr/bin/env python3
"""
Plan Runner Script

Runs the planning workflow to create an implementation plan.

Usage:
    python scripts/plan.py "Add user authentication with JWT"
    uv run python scripts/plan.py "Add user authentication"
"""
import sys
from pathlib import Path

# Add orchestrator to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / ".orchestrator"))

from workflows.planning import PlanningWorkflow


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/plan.py 'Your request here'")
        print()
        print("Example:")
        print("  python scripts/plan.py 'Add user authentication with JWT'")
        sys.exit(1)

    request = " ".join(sys.argv[1:])

    workflow = PlanningWorkflow(project_root=project_root)
    result = workflow.run(request)

    if result.success:
        print(f"\nPlan saved to: {result.output_file}")
    else:
        print(f"\nFailed: {result.error}")

    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
