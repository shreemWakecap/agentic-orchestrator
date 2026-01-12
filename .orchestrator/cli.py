#!/usr/bin/env python3
"""
SDLC Orchestrator CLI - Unified entry point.

Usage:
    uv run python .orchestrator/cli.py setup
    uv run python .orchestrator/cli.py plan "Add user authentication"
    uv run python .orchestrator/cli.py plan --mcp "Add user authentication"  # MCP mode
    uv run python .orchestrator/cli.py build .specs/pending/plan.md
    uv run python .orchestrator/cli.py review .specs/completed/plan.md
    uv run python .orchestrator/cli.py fix .specs/reviews/review.md
    uv run python .orchestrator/cli.py list
    uv run python .orchestrator/cli.py docs
    uv run python .orchestrator/cli.py experts
    uv run python .orchestrator/cli.py test
"""
import os
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
        print("Usage: cli.py plan [--mcp] [--server URL] 'Your request'")
        print("\nOptions:")
        print("  --mcp             Use MCP server for real-time streaming")
        print("  --server URL      MCP server URL (default: http://localhost:3000)")
        return 1

    # Check for MCP mode
    use_mcp = "--mcp" in args
    server_url = "http://localhost:3000"

    # Parse server URL
    for i, arg in enumerate(args):
        if arg == "--server" and i + 1 < len(args):
            server_url = args[i + 1]

    # Get request (non-option args)
    request_parts = [a for a in args if not a.startswith("--") and a != server_url]
    if not request_parts:
        print("Error: No request provided")
        return 1
    request = " ".join(request_parts)

    if use_mcp:
        return _cmd_plan_mcp(request, server_url)
    else:
        from workflows.planning import PlanningWorkflow
        workflow = PlanningWorkflow(project_root=PROJECT_ROOT)
        result = workflow.run(request)
        return 0 if result.success else 1


def _cmd_plan_mcp(request: str, server_url: str):
    """Run planning with MCP server for real-time streaming."""
    import asyncio

    async def run():
        from core.mcp_client import MCPClient, StreamEvent
        from workflows.async_planning import AsyncPlanningWorkflow

        api_key = os.environ.get("ANTHROPIC_API_KEY")

        print(f"Connecting to MCP server: {server_url}")

        async with MCPClient(
            server_url=server_url,
            api_key=api_key,
            transport_type="http-sse"
        ) as client:

            workflow = AsyncPlanningWorkflow(PROJECT_ROOT, client)

            # Set up progress callback for real-time token streaming
            def on_progress(agent_name: str, event: StreamEvent):
                if event.event_type == "token":
                    text = event.data.get("text", "")
                    print(text, end="", flush=True)
                elif event.event_type == "tool_use":
                    tool = event.data.get("tool", "")
                    print(f"\n  [Tool: {tool}]", end="", flush=True)

            workflow.on_progress(on_progress)

            result = await workflow.execute(request)

            print()  # Newline after streaming

            if result.success:
                print(f"\n[green]Plan created: {result.output_file}[/green]")
                print(f"Total tokens: {result.total_tokens}")
                return 0
            else:
                print(f"\n[red]Planning failed: {result.error}[/red]")
                return 1

    return asyncio.run(run())


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


def cmd_web(args):
    """Start web UI server."""
    host = "127.0.0.1"
    port = 8000

    # Parse arguments
    for i, arg in enumerate(args):
        if arg == "--host" and i + 1 < len(args):
            host = args[i + 1]
        elif arg == "--port" and i + 1 < len(args):
            port = int(args[i + 1])

    print(f"Starting SDLC Orchestrator Web UI\n" + "=" * 50)
    print(f"Server: http://{host}:{port}")
    print(f"Press Ctrl+C to stop\n")

    try:
        from server.app import run_server
        run_server(host=host, port=port)
    except ImportError as e:
        print(f"Error: Web dependencies not installed. Run:")
        print(f"  uv pip install fastapi uvicorn jinja2")
        return 1
    except KeyboardInterrupt:
        print("\nServer stopped.")

    return 0


def cmd_cost(args):
    """Cost estimation and budget management."""
    from pathlib import Path
    from core.cost import CostEstimator, CostReporter, BudgetManager, Budget

    if not args:
        print("Usage: cli.py cost <subcommand> [options]")
        print("\nSubcommands:")
        print("  estimate <workflow>  Estimate cost for a workflow")
        print("  report <period>      Show cost report (daily|weekly|monthly)")
        print("  budget show          Show budget status")
        print("  budget set           Set budget limits")
        print("\nExamples:")
        print("  cli.py cost estimate plan --request 'Add authentication'")
        print("  cli.py cost estimate build --plan .specs/pending/auth.md")
        print("  cli.py cost report daily")
        print("  cli.py cost budget show")
        print("  cli.py cost budget set --daily 10.00 --monthly 100.00")
        return 1

    subcommand = args[0]
    sub_args = args[1:]

    estimator = CostEstimator(ORCHESTRATOR_DIR / "cost_history.json")
    reporter = CostReporter(estimator)
    budget_manager = BudgetManager(
        ORCHESTRATOR_DIR / "config" / "budget.json",
        estimator
    )

    if subcommand == "estimate":
        return _cost_estimate(sub_args, estimator)
    elif subcommand == "report":
        return _cost_report(sub_args, reporter)
    elif subcommand == "budget":
        return _cost_budget(sub_args, budget_manager)
    else:
        print(f"Unknown subcommand: {subcommand}")
        return 1


def _cost_estimate(args, estimator):
    """Handle cost estimate subcommand."""
    if not args:
        print("Usage: cli.py cost estimate <workflow> [options]")
        print("  Workflows: plan, build, review")
        return 1

    workflow = args[0]
    request = ""
    plan_path = None
    complexity = "medium"

    # Parse options
    for i, arg in enumerate(args):
        if arg == "--request" and i + 1 < len(args):
            request = args[i + 1]
        elif arg == "--plan" and i + 1 < len(args):
            plan_path = Path(args[i + 1])
        elif arg == "--complexity" and i + 1 < len(args):
            complexity = args[i + 1]

    if workflow == "plan":
        if not request:
            print("Error: --request required for plan estimation")
            return 1
        estimate = estimator.estimate_planning(len(request), complexity)
    elif workflow == "build":
        if not plan_path:
            print("Error: --plan required for build estimation")
            return 1
        estimate = estimator.estimate_building(plan_path)
    elif workflow == "review":
        if not plan_path:
            print("Error: --plan required for review estimation")
            return 1
        estimate = estimator.estimate_reviewing(plan_path)
    else:
        print(f"Unknown workflow: {workflow}")
        return 1

    print(f"\nCost Estimate: {workflow}")
    print("=" * 40)
    print(f"Total tokens: {estimate.total_estimate.total_tokens:,}")
    print(f"Estimated cost: ${estimate.total_cost:.4f}")
    print(f"Confidence: {estimate.confidence:.0%}")
    print(f"\nAgent breakdown:")
    for agent, tokens in estimate.agents.items():
        print(f"  {agent}: {tokens.total_tokens:,} tokens (${tokens.estimated_cost:.4f})")
    return 0


def _cost_report(args, reporter):
    """Handle cost report subcommand."""
    if not args:
        print("Usage: cli.py cost report <period>")
        print("  Periods: daily, weekly, monthly")
        return 1

    period = args[0]

    if period == "daily":
        report = reporter.daily_report()
        title = f"Daily Cost Report ({report['date']})"
    elif period == "weekly":
        report = reporter.weekly_report()
        title = f"Weekly Cost Report ({report['period']})"
    elif period == "monthly":
        report = reporter.monthly_report()
        title = f"Monthly Cost Report ({report['month']})"
    else:
        print(f"Unknown period: {period}")
        return 1

    print(f"\n{title}")
    print("=" * 40)
    print(f"Total runs: {report['total_runs']}")
    print(f"Total tokens: {report['total_tokens']:,}")
    print(f"Total cost: ${report['total_cost']:.4f}")

    if report['by_workflow']:
        print(f"\nBy workflow:")
        for wf, data in report["by_workflow"].items():
            print(f"  {wf}: {data['runs']} runs, {data['tokens']:,} tokens, ${data['cost']:.4f}")
    return 0


def _cost_budget(args, budget_manager):
    """Handle cost budget subcommand."""
    from core.cost import Budget

    if not args:
        print("Usage: cli.py cost budget <action> [options]")
        print("  Actions: show, set")
        return 1

    action = args[0]

    if action == "show":
        remaining = budget_manager.get_remaining_budget()
        print("\nBudget Status")
        print("=" * 40)
        for period, data in remaining.items():
            if data["limit"]:
                pct = (data["used"] / data["limit"]) * 100 if data["limit"] else 0
                print(f"{period.capitalize()}: ${data['used']:.2f} / ${data['limit']:.2f} ({pct:.0f}%)")
                if data["remaining"]:
                    print(f"  Remaining: ${data['remaining']:.2f}")
            else:
                print(f"{period.capitalize()}: ${data['used']:.2f} (no limit set)")
        return 0

    elif action == "set":
        daily = None
        weekly = None
        monthly = None
        per_workflow = None

        for i, arg in enumerate(args):
            if arg == "--daily" and i + 1 < len(args):
                daily = float(args[i + 1])
            elif arg == "--weekly" and i + 1 < len(args):
                weekly = float(args[i + 1])
            elif arg == "--monthly" and i + 1 < len(args):
                monthly = float(args[i + 1])
            elif arg == "--per-workflow" and i + 1 < len(args):
                per_workflow = float(args[i + 1])

        budget = Budget(
            daily_limit=daily,
            weekly_limit=weekly,
            monthly_limit=monthly,
            per_workflow_limit=per_workflow
        )
        budget_manager.save_budget(budget)
        print("Budget updated successfully!")
        print(f"  Daily: ${daily:.2f}" if daily else "  Daily: not set")
        print(f"  Weekly: ${weekly:.2f}" if weekly else "  Weekly: not set")
        print(f"  Monthly: ${monthly:.2f}" if monthly else "  Monthly: not set")
        print(f"  Per-workflow: ${per_workflow:.2f}" if per_workflow else "  Per-workflow: not set")
        return 0

    else:
        print(f"Unknown action: {action}")
        return 1


def cmd_test(args):
    """Run test suite."""
    import subprocess

    print("Running SDLC Orchestrator Tests\n" + "=" * 50)

    # Build pytest command
    pytest_args = [sys.executable, "-m", "pytest", str(ORCHESTRATOR_DIR / "tests")]

    # Pass through common pytest options
    if "-v" in args or "--verbose" in args:
        pytest_args.append("-v")
    if "-x" in args:
        pytest_args.append("-x")
    if "--cov" in args:
        pytest_args.extend(["--cov=.", "--cov-report=term-missing"])

    # Filter by test type
    if "--unit" in args:
        pytest_args.append(str(ORCHESTRATOR_DIR / "tests" / "unit"))
    elif "--integration" in args:
        pytest_args.append(str(ORCHESTRATOR_DIR / "tests" / "integration"))

    # Pass specific test file or pattern
    for arg in args:
        if arg.endswith(".py") or "::" in arg:
            pytest_args.append(arg)

    print(f"Command: {' '.join(pytest_args)}\n")

    result = subprocess.run(pytest_args, cwd=PROJECT_ROOT)
    return result.returncode


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
    'cost': (cmd_cost, "Cost estimation and budgets"),
    'test': (cmd_test, "Run test suite"),
    'web': (cmd_web, "Start web UI server"),
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
        print("  cli.py plan --mcp 'Add authentication'   # MCP streaming mode")
        print("  cli.py build .specs/pending/user-auth.md")
        print("  cli.py review .specs/completed/user-auth.md")
        print("  cli.py fix .specs/reviews/review-user-auth.md")
        print("  cli.py fix .specs/reviews/review.md --dry-run")
        print("  cli.py test                              # Run all tests")
        print("  cli.py test --unit                       # Run unit tests only")
        print("  cli.py test --integration                # Run integration tests only")
        print("  cli.py test -v --cov                     # Verbose with coverage")
        print("  cli.py web                               # Start web UI")
        print("  cli.py web --port 8080                   # Custom port")
        print("  cli.py cost estimate plan --request 'Add auth'")
        print("  cli.py cost report daily                 # Daily cost report")
        print("  cli.py cost budget show                  # Show budget status")
        print("  cli.py cost budget set --daily 10.00     # Set daily limit")
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
