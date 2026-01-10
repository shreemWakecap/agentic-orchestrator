#!/usr/bin/env python3
"""
SDLC Orchestrator - Run Workflows

Usage:
    uv run python .orchestrator/run.py plan "Add user authentication"
    uv run python .orchestrator/run.py build .specs/pending/user-auth.md
    uv run python .orchestrator/run.py review .specs/completed/user-auth.md
    uv run python .orchestrator/run.py list
    uv run python .orchestrator/run.py docs [--refresh]
    uv run python .orchestrator/run.py experts
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
from workflows.reviewing import ReviewingWorkflow
from core.docs_loader import DocsLoader
from core.expert_loader import ExpertLoader


def list_plans():
    """List all plans in .specs directory."""
    print("SDLC Plans")
    print("=" * 60)

    for status in ["pending", "in-progress", "completed", "failed", "reviews"]:
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
            "failed": "\033[31m",       # Red
            "reviews": "\033[35m",      # Magenta
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


def check_docs(refresh: bool = False):
    """Check and optionally refresh AI documentation."""
    print("AI Documentation Status")
    print("=" * 60)

    loader = DocsLoader(PROJECT_ROOT)
    status = loader.check_freshness()

    print(f"\nTotal docs: {status['total_docs']}")
    print(f"Fresh docs: {status['fresh_docs']}")
    print(f"Stale docs: {len(status['stale_docs'])}")
    print(f"Missing docs: {len(status['missing_docs'])}")

    if status['stale_docs']:
        print("\nStale (older than 2 days):")
        for url in status['stale_docs'][:5]:
            print(f"  - {url[:60]}...")

    if status['missing_docs']:
        print("\nMissing:")
        for url in status['missing_docs'][:5]:
            print(f"  - {url[:60]}...")

    print(f"\n{status['recommendation']}")

    if refresh and status['needs_refresh']:
        print("\nRefreshing docs...")
        loader.refresh_docs(status['stale_docs'] + status['missing_docs'])
        print("Done!")


def list_experts():
    """List all available tech experts."""
    print("Tech Experts")
    print("=" * 60)

    loader = ExpertLoader(PROJECT_ROOT)
    experts = loader.list_experts()

    for category, items in experts.items():
        if not items:
            continue

        print(f"\n{category.upper()}")
        print("-" * 40)
        for expert in items:
            print(f"  {expert['name']}: {expert['description'][:50]}")

    # Show recommendations for this project
    recommended = loader.get_recommended_experts(PROJECT_ROOT)
    if recommended:
        print(f"\nRecommended for this project: {', '.join(recommended)}")


def main():
    if len(sys.argv) < 2:
        print("SDLC Orchestrator")
        print()
        print("Usage:")
        print("  uv run python .orchestrator/run.py plan 'Your request'")
        print("  uv run python .orchestrator/run.py build <plan-file>")
        print("  uv run python .orchestrator/run.py review <plan-file> [--refresh-docs]")
        print("  uv run python .orchestrator/run.py list")
        print("  uv run python .orchestrator/run.py docs [--refresh]")
        print("  uv run python .orchestrator/run.py experts")
        print()
        print("Workflows:")
        print("  plan     Create an implementation plan")
        print("  build    Execute a plan to build the feature")
        print("  review   Review a completed build for quality")
        print()
        print("Utilities:")
        print("  list     List all plans and their status")
        print("  docs     Check AI documentation freshness")
        print("  experts  List available tech experts")
        print()
        print("Examples:")
        print("  uv run python .orchestrator/run.py plan 'Add user authentication'")
        print("  uv run python .orchestrator/run.py build .specs/pending/user-auth.md")
        print("  uv run python .orchestrator/run.py review .specs/completed/user-auth.md")
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

    elif command == "review":
        if not args:
            print("Error: Please provide a plan file to review")
            print("Usage: uv run python .orchestrator/run.py review <plan-file> [--refresh-docs]")
            print()
            print("Completed plans:")
            list_plans()
            sys.exit(1)

        plan_path = args[0]
        refresh_docs = "--refresh-docs" in args

        workflow = ReviewingWorkflow(project_root=PROJECT_ROOT, refresh_docs=refresh_docs)
        result = workflow.run(plan_path)

        # Print summary
        if result.success and result.data:
            print()
            print(f"Overall Score: {result.data.get('overall_score', 0):.0f}/100")
            print(f"Report saved: {result.output_file}")

        sys.exit(0 if result.success else 1)

    elif command == "list":
        list_plans()
        sys.exit(0)

    elif command == "docs":
        refresh = "--refresh" in args
        check_docs(refresh=refresh)
        sys.exit(0)

    elif command == "experts":
        list_experts()
        sys.exit(0)

    else:
        print(f"Unknown command: {command}")
        print("Available: plan, build, review, list, docs, experts")
        sys.exit(1)


if __name__ == "__main__":
    main()
