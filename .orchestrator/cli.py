#!/usr/bin/env python3
"""
SDLC Orchestrator CLI - Unified entry point.

Usage:
    uv run python .orchestrator/cli.py setup
    uv run python .orchestrator/cli.py plan "Add user authentication"
    uv run python .orchestrator/cli.py build .specs/pending/plan.md
    uv run python .orchestrator/cli.py review .specs/completed/plan.md
    uv run python .orchestrator/cli.py list
    uv run python .orchestrator/cli.py docs
    uv run python .orchestrator/cli.py experts
"""
import shutil
import sys
from pathlib import Path

# Setup paths
ORCHESTRATOR_DIR = Path(__file__).parent
PROJECT_ROOT = ORCHESTRATOR_DIR.parent
SPECS_DIR = PROJECT_ROOT / ".specs"

sys.path.insert(0, str(ORCHESTRATOR_DIR))


# =============================================================================
# Setup Command
# =============================================================================

def cmd_setup():
    """Initialize orchestrator environment."""
    from core.docs_loader import DocsLoader

    print("=== SDLC Orchestrator Setup ===\n")
    ok = True

    # 1. Prerequisites
    print("[1/3] Prerequisites...")
    for cmd in ['claude', 'uv']:
        if shutil.which(cmd):
            print(f"  [+] {cmd}")
        else:
            print(f"  [!] {cmd} missing")
            ok = False

    # 2. Directories
    print("\n[2/3] Directories...")
    for d in ['.specs', '.orchestrator/experts', '.orchestrator/config', 'ai_docs']:
        path = PROJECT_ROOT / d
        path.mkdir(parents=True, exist_ok=True)
        print(f"  [+] {d}")

    # 3. Docs
    print("\n[3/3] Documentation...")
    loader = DocsLoader(PROJECT_ROOT)
    status = loader.get_status()
    print(f"  URLs: {status['total']}, Fresh: {status['fresh']}, Missing: {len(status['missing'])}")

    if status['missing']:
        print(f"\n  Fetching {len(status['missing'])} docs...")
        result = loader.refresh(status['missing'])
        print(f"  Done: {result['updated']} fetched, {result['failed']} failed")
        if result['failed']:
            ok = False

    print("\n" + "=" * 40)
    print("Setup complete!" if ok else "Setup completed with issues")
    return 0 if ok else 1


# =============================================================================
# Workflow Commands
# =============================================================================

def cmd_plan(args):
    """Create an implementation plan."""
    if not args:
        print("Usage: cli.py plan 'Your request'")
        return 1

    from workflows.planning import PlanningWorkflow
    request = " ".join(args)
    workflow = PlanningWorkflow(project_root=PROJECT_ROOT)
    result = workflow.run(request)
    return 0 if result.success else 1


def cmd_build(args):
    """Execute a plan to build the feature."""
    if not args:
        print("Usage: cli.py build <plan-file>")
        cmd_list()
        return 1

    from workflows.building import BuildingWorkflow
    workflow = BuildingWorkflow(project_root=PROJECT_ROOT)
    result = workflow.run(args[0])
    return 0 if result.success else 1


def cmd_review(args):
    """Review a completed build."""
    if not args:
        print("Usage: cli.py review <plan-file>")
        cmd_list()
        return 1

    from workflows.reviewing import ReviewingWorkflow
    refresh_docs = "--refresh-docs" in args
    plan_path = [a for a in args if not a.startswith("--")][0]

    workflow = ReviewingWorkflow(project_root=PROJECT_ROOT, refresh_docs=refresh_docs)
    result = workflow.run(plan_path)

    if result.success and result.data:
        print(f"\nScore: {result.data.get('overall_score', 0):.0f}/100")
        print(f"Report: {result.output_file}")

    return 0 if result.success else 1


def cmd_fix(args):
    """Fix issues from a review report."""
    if not args:
        print("Usage: cli.py fix <review-file> [options]")
        print("\nOptions:")
        print("  --dry-run         Show fixes without applying")
        print("  --min-severity    Minimum severity (critical|high|medium|low)")
        print("\nExample: cli.py fix .specs/reviews/review-auth-20240115.md")
        cmd_list()
        return 1

    from workflows.fixing import FixingWorkflow

    # Parse options
    dry_run = "--dry-run" in args
    min_severity = "low"

    # Find min-severity value
    for i, arg in enumerate(args):
        if arg == "--min-severity" and i + 1 < len(args):
            min_severity = args[i + 1]

    # Get review file (first non-option arg)
    review_path = [a for a in args if not a.startswith("--")][0]

    workflow = FixingWorkflow(
        project_root=PROJECT_ROOT,
        dry_run=dry_run,
        min_severity=min_severity
    )
    result = workflow.run(review_path)

    if result.success and result.data:
        print(f"\nFixes applied: {result.data.get('fixes_applied', 0)}")
        if result.data.get('fixes_failed', 0) > 0:
            print(f"Fixes failed: {result.data.get('fixes_failed', 0)}")
        if result.data.get('unfixable', 0) > 0:
            print(f"Unfixable issues: {result.data.get('unfixable', 0)}")
        if result.output_file:
            print(f"Report: {result.output_file}")

    return 0 if result.success else 1


# =============================================================================
# Utility Commands
# =============================================================================

def cmd_list():
    """List all plans."""
    print("SDLC Plans\n" + "=" * 50)

    colors = {
        "pending": "\033[33m", "in-progress": "\033[36m",
        "completed": "\033[32m", "failed": "\033[31m",
        "reviews": "\033[35m", "fixes": "\033[34m"
    }

    for status in colors:
        status_dir = SPECS_DIR / status
        if not status_dir.exists():
            continue
        plans = list(status_dir.glob("*.md"))
        if plans:
            print(f"\n{colors[status]}{status.upper()}\033[0m ({len(plans)})")
            for p in sorted(plans):
                print(f"  {p.name}")

    return 0


def cmd_docs(args):
    """Check/refresh documentation."""
    from core.docs_loader import DocsLoader

    loader = DocsLoader(PROJECT_ROOT)
    status = loader.get_status()

    print("AI Documentation\n" + "=" * 50)
    print(f"Total: {status['total']}, Fresh: {status['fresh']}")
    print(f"Stale: {len(status['stale'])}, Missing: {len(status['missing'])}")

    if "--refresh" in args and (status['stale'] or status['missing']):
        print("\nRefreshing...")
        loader.refresh()
        print("Done!")

    return 0


def cmd_experts():
    """List available experts."""
    from core.expert_loader import ExpertLoader

    print("Tech Experts\n" + "=" * 50)

    loader = ExpertLoader(PROJECT_ROOT)
    experts = loader.list_experts()

    for category, items in experts.items():
        if items:
            print(f"\n{category.upper()}")
            for e in items:
                print(f"  {e['name']}: {e['description'][:50]}")

    recommended = loader.get_recommended_experts(PROJECT_ROOT)
    if recommended:
        print(f"\nRecommended: {', '.join(recommended)}")

    return 0


# =============================================================================
# Main
# =============================================================================

COMMANDS = {
    'setup': (cmd_setup, "Initialize environment"),
    'plan': (cmd_plan, "Create implementation plan"),
    'build': (cmd_build, "Execute a plan"),
    'review': (cmd_review, "Review completed build"),
    'fix': (cmd_fix, "Fix issues from review"),
    'list': (cmd_list, "List all plans"),
    'docs': (cmd_docs, "Check documentation"),
    'experts': (cmd_experts, "List tech experts"),
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ['-h', '--help', 'help']:
        print("SDLC Orchestrator\n")
        print("Usage: cli.py <command> [args]\n")
        print("Commands:")
        for name, (_, desc) in COMMANDS.items():
            print(f"  {name:10} {desc}")
        print("\nExamples:")
        print("  cli.py setup")
        print("  cli.py plan 'Add user authentication'")
        print("  cli.py build .specs/pending/user-auth.md")
        print("  cli.py review .specs/completed/user-auth.md")
        print("  cli.py fix .specs/reviews/review-user-auth.md")
        print("  cli.py fix .specs/reviews/review.md --dry-run")
        return 1

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd not in COMMANDS:
        print(f"Unknown command: {cmd}")
        print(f"Available: {', '.join(COMMANDS.keys())}")
        return 1

    handler = COMMANDS[cmd][0]

    # Commands that don't take args
    if cmd in ['setup', 'list', 'experts']:
        return handler()
    else:
        return handler(args)


if __name__ == "__main__":
    sys.exit(main())
