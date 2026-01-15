#!/usr/bin/env python3
"""
SDLC Orchestrator CLI - Unified entry point.

Usage:
    uv run python .orchestrator/cli.py setup
    uv run python .orchestrator/cli.py plan "Add user authentication"
    uv run python .orchestrator/cli.py build .orchestrator/specs/pending/plan.md
    uv run python .orchestrator/cli.py review .orchestrator/specs/completed/plan.md
    uv run python .orchestrator/cli.py fix .orchestrator/specs/reviews/review.md
    uv run python .orchestrator/cli.py list
    uv run python .orchestrator/cli.py docs
    uv run python .orchestrator/cli.py experts
    uv run python .orchestrator/cli.py cost
    uv run python .orchestrator/cli.py test
    uv run python .orchestrator/cli.py portal
"""
import shutil
import sys
from pathlib import Path

# Setup paths
ORCHESTRATOR_DIR = Path(__file__).parent
PROJECT_ROOT = ORCHESTRATOR_DIR.parent
SPECS_DIR = ORCHESTRATOR_DIR / "specs"

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
    for d in ['specs', 'agents/experts', 'config', 'docs']:
        path = ORCHESTRATOR_DIR / d
        path.mkdir(parents=True, exist_ok=True)
        print(f"  [+] .orchestrator/{d}")

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

    request = " ".join(args)

    from workflows.planning import PlanningWorkflow
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
        print("\nExample: cli.py fix .orchestrator/specs/reviews/review-auth-20240115.md")
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
    """List all plans with their build status."""
    import json

    print("SDLC Plans\n" + "=" * 50)

    colors = {
        "pending": "\033[33m",
        "completed": "\033[32m", "failed": "\033[31m",
        "reviews": "\033[35m", "fixes": "\033[34m"
    }

    # Load state files for progress info
    state_dir = SPECS_DIR / "state"
    states = {}
    if state_dir.exists():
        for state_file in state_dir.glob("*.state.json"):
            try:
                data = json.loads(state_file.read_text(encoding="utf-8"))
                plan_id = state_file.stem.replace(".state", "")
                states[plan_id] = data
            except Exception:
                pass

    for status in colors:
        status_dir = SPECS_DIR / status
        if not status_dir.exists():
            continue
        # Find both folder-based plans (directories with numeric prefix) and legacy .md files
        plans = []
        for item in status_dir.iterdir():
            if item.is_dir() and item.name[0].isdigit():
                # Folder-based plan (e.g., "001_feature-name")
                plans.append(item)
            elif item.is_file() and item.suffix == ".md":
                # Legacy single-file plan
                plans.append(item)
        if plans:
            print(f"\n{colors[status]}{status.upper()}\033[0m ({len(plans)})")
            for p in sorted(plans, key=lambda x: x.name):
                if p.is_dir():
                    # Show folder with build state info
                    file_count = len(list(p.glob("*.md")))
                    state = states.get(p.stem)
                    if state:
                        completed = len(state.get("completed_steps", []))
                        total = state.get("total_steps", 0)
                        build_status = state.get("status", "pending")
                        if build_status == "paused":
                            print(f"  {p.name}/ \033[33m[PAUSED {completed}/{total}]\033[0m")
                        elif build_status == "building":
                            print(f"  {p.name}/ \033[36m[BUILDING {completed}/{total}]\033[0m")
                        elif build_status == "completed":
                            print(f"  {p.name}/ \033[32m[DONE {completed}/{total}]\033[0m")
                        elif build_status == "failed":
                            print(f"  {p.name}/ \033[31m[FAILED {completed}/{total}]\033[0m")
                        else:
                            print(f"  {p.name}/ ({file_count} files)")
                    else:
                        print(f"  {p.name}/ ({file_count} files)")
                else:
                    print(f"  {p.name}")

    # Show active builds from state
    active_builds = [s for s in states.values() if s.get("status") in ("building", "paused")]
    if active_builds:
        print(f"\n\033[36mACTIVE BUILDS\033[0m ({len(active_builds)})")
        for state in active_builds:
            plan_id = state.get("plan_id", "unknown")
            completed = len(state.get("completed_steps", []))
            total = state.get("total_steps", 0)
            status = state.get("status", "unknown")
            current = state.get("current_step", "")
            if status == "paused":
                print(f"  {plan_id}: \033[33mpaused\033[0m at step {current} ({completed}/{total})")
            else:
                print(f"  {plan_id}: \033[36mbuilding\033[0m ({completed}/{total})")

    return 0


def cmd_status(args):
    """Show detailed build status for a plan."""
    import json
    from datetime import datetime

    if not args:
        print("Usage: cli.py status <plan-name>")
        print("\nShows detailed step-by-step build progress for a plan.")
        print("\nExample:")
        print("  cli.py status 001_simple-hello-world-feature")
        return 1

    plan_name = args[0]

    # Find state file
    state_file = SPECS_DIR / "state" / f"{plan_name}.state.json"
    if not state_file.exists():
        print(f"No build state found for: {plan_name}")
        print(f"Expected: {state_file}")
        return 1

    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Error reading state file: {e}")
        return 1

    # Display status
    print(f"\nBuild Status: {plan_name}")
    print("=" * 60)

    status = state.get("status", "unknown")
    status_colors = {
        "pending": "\033[33m",
        "building": "\033[36m",
        "paused": "\033[33m",
        "completed": "\033[32m",
        "failed": "\033[31m",
    }
    color = status_colors.get(status, "")
    print(f"Status: {color}{status.upper()}\033[0m")

    # Progress
    completed_steps = state.get("completed_steps", [])
    failed_steps = state.get("failed_steps", [])
    total_steps = state.get("total_steps", 0)
    print(f"Progress: {len(completed_steps)}/{total_steps} steps completed")

    if failed_steps:
        print(f"Failed steps: {len(failed_steps)}")

    # Timing
    started = state.get("started_at", "")
    updated = state.get("updated_at", "")
    if started:
        print(f"Started: {started[:19]}")
    if updated:
        print(f"Last update: {updated[:19]}")

    # Current step
    current_step = state.get("current_step", "")
    if current_step:
        print(f"Current step: {current_step}")

    # Last error
    last_error = state.get("last_error", "")
    if last_error:
        print(f"\n\033[31mLast error:\033[0m {last_error}")

    # Step details
    step_states = state.get("step_states", {})
    if step_states:
        print(f"\n{'─' * 60}")
        print("Step Details:")
        print(f"{'─' * 60}")

        for step_id, step_data in step_states.items():
            step_status = step_data.get("status", "unknown")
            retry_count = step_data.get("retry_count", 0)

            if step_status == "completed":
                icon = "\033[32m✓\033[0m"
            elif step_status == "failed":
                icon = "\033[31m✗\033[0m"
            elif step_status == "in_progress":
                icon = "\033[36m→\033[0m"
            else:
                icon = "\033[33m○\033[0m"

            retry_str = f" (retry {retry_count})" if retry_count > 0 else ""
            print(f"  {icon} {step_id}{retry_str}")

            if step_data.get("summary"):
                print(f"      {step_data['summary'][:50]}")
            if step_data.get("error"):
                print(f"      \033[31mError: {step_data['error'][:50]}\033[0m")

    # Files affected
    files_created = state.get("files_created", [])
    files_modified = state.get("files_modified", [])
    if files_created or files_modified:
        print(f"\n{'─' * 60}")
        print("Files Affected:")
        if files_created:
            print(f"  Created: {len(files_created)}")
            for f in files_created[:5]:
                print(f"    + {f}")
            if len(files_created) > 5:
                print(f"    ... and {len(files_created) - 5} more")
        if files_modified:
            print(f"  Modified: {len(files_modified)}")
            for f in files_modified[:5]:
                print(f"    ~ {f}")
            if len(files_modified) > 5:
                print(f"    ... and {len(files_modified) - 5} more")

    # Resume hint
    if status == "paused":
        print(f"\n\033[33mTo resume:\033[0m cli.py build {plan_name}")

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


def cmd_experts(args=None):
    """Manage expert agents (list, create, discover, auto-build)."""
    from core.expert_loader import ExpertLoader, ExpertType

    args = args or []

    if not args or args[0] == "list":
        return _experts_list()
    elif args[0] == "create":
        return _experts_create(args[1:])
    elif args[0] == "discover":
        return _experts_discover(args[1:])
    elif args[0] == "auto-build":
        return _experts_auto_build(args[1:])
    else:
        print(f"Unknown experts subcommand: {args[0]}")
        _experts_help()
        return 1


def _experts_help():
    """Show expert commands help."""
    print("\nUsage: cli.py experts <subcommand>")
    print("\nSubcommands:")
    print("  list                     List all experts by type")
    print("  create <name> [options]  Create a new expert manually")
    print("  discover                 Analyze codebase and show missing experts")
    print("  auto-build [options]     Auto-create all missing experts")
    print("\nExamples:")
    print("  cli.py experts list")
    print("  cli.py experts discover")
    print("  cli.py experts auto-build --dry-run")
    print("  cli.py experts auto-build --confirm")
    print("  cli.py experts create auth --type domain --keywords auth,login,jwt")


def _experts_list():
    """List all available experts grouped by type."""
    from core.expert_loader import ExpertLoader

    print("Expert Agents\n" + "=" * 50)

    loader = ExpertLoader(PROJECT_ROOT)
    experts = loader.list_experts()

    # Tech experts (grouped by category)
    tech = experts.get("tech", {})
    if any(tech.values()):
        print("\nTECH EXPERTS")
        for category in ["language", "framework", "tool", "general"]:
            items = tech.get(category, [])
            if items:
                print(f"  [{category}]")
                for e in items:
                    desc = e['description'][:40] + "..." if len(e.get('description', '')) > 40 else e.get('description', '')
                    print(f"    {e['name']}: {desc}")

    # Domain experts
    domain = experts.get("domain", [])
    if domain:
        print("\nDOMAIN EXPERTS")
        for e in domain:
            desc = e['description'][:40] + "..." if len(e.get('description', '')) > 40 else e.get('description', '')
            print(f"  {e['name']}: {desc}")
            if e.get('keywords'):
                print(f"    Keywords: {', '.join(e['keywords'])}")

    # Module experts
    module = experts.get("module", [])
    if module:
        print("\nMODULE EXPERTS")
        for e in module:
            desc = e['description'][:40] + "..." if len(e.get('description', '')) > 40 else e.get('description', '')
            print(f"  {e['name']}: {desc}")
            if e.get('module_path'):
                print(f"    Module: {e['module_path']}")

    # Recommendations
    recommended = loader.get_recommended_experts(PROJECT_ROOT)
    if recommended:
        print(f"\nRecommended for this project: {', '.join(recommended)}")

    return 0


def _experts_create(args):
    """Create a new expert agent."""
    from core.expert_loader import ExpertLoader, ExpertType

    if not args:
        print("Usage: cli.py experts create <name> [options]")
        print("\nOptions:")
        print("  --type <tech|domain|module>  Expert type (default: tech)")
        print("  --module <path>              Module path (for module experts)")
        print("  --keywords <k1,k2,k3>        Domain keywords (for domain experts)")
        print("  --based-on <tech>            Base technology (for tech experts)")
        print("  --focus <description>        Specific focus area")
        print("\nExamples:")
        print("  cli.py experts create auth --type domain --keywords auth,login,jwt,session")
        print("  cli.py experts create core-api --type module --module src/api")
        print("  cli.py experts create fastapi --type tech --based-on python")
        return 1

    name = args[0]
    expert_type = ExpertType.TECH
    module_path = None
    keywords = []
    based_on = "python"
    focus = ""

    # Parse options
    i = 1
    while i < len(args):
        arg = args[i]
        if arg == "--type" and i + 1 < len(args):
            type_str = args[i + 1].lower()
            if type_str == "tech":
                expert_type = ExpertType.TECH
            elif type_str == "domain":
                expert_type = ExpertType.DOMAIN
            elif type_str == "module":
                expert_type = ExpertType.MODULE
            else:
                print(f"Unknown expert type: {type_str}")
                print("Valid types: tech, domain, module")
                return 1
            i += 2
        elif arg == "--module" and i + 1 < len(args):
            module_path = args[i + 1]
            i += 2
        elif arg == "--keywords" and i + 1 < len(args):
            keywords = [k.strip() for k in args[i + 1].split(",")]
            i += 2
        elif arg == "--based-on" and i + 1 < len(args):
            based_on = args[i + 1]
            i += 2
        elif arg == "--focus" and i + 1 < len(args):
            focus = args[i + 1]
            i += 2
        else:
            print(f"Unknown option: {arg}")
            return 1

    print(f"Creating {expert_type.value} expert: {name}")
    print("=" * 50)

    loader = ExpertLoader(PROJECT_ROOT)
    success = loader.create_expert(
        name=name,
        expert_type=expert_type,
        based_on=based_on,
        focus=focus,
        module_path=module_path,
        domain_keywords=keywords if keywords else None
    )

    if success:
        print(f"\nExpert '{name}' created successfully!")
        print(f"Location: .orchestrator/agents/experts/{name}.md")
        return 0
    else:
        print(f"\nFailed to create expert '{name}'")
        return 1


def _experts_discover(args):
    """
    Explore system and show missing experts.

    Usage: cli.py experts discover [--json]
    """
    import json as json_lib
    from core.expert_loader import ExpertLoader

    as_json = "--json" in args

    if not as_json:
        print("Analyzing codebase...")

    loader = ExpertLoader(PROJECT_ROOT)
    gaps = loader.find_missing_experts()

    if as_json:
        print(json_lib.dumps(gaps, indent=2))
        return 0

    print(f"\n{'=' * 50}")
    print("EXPERT GAP ANALYSIS")
    print(f"{'=' * 50}")

    if not gaps:
        print("\nNo gaps found! All detected technologies have experts.")
        return 0

    print(f"\nFound {len(gaps)} missing expert(s):\n")

    for gap in gaps:
        print(f"  [{gap['type'].upper()}] {gap['name']}")
        print(f"       Confidence: {gap['confidence']:.0%}")
        if gap.get('category'):
            print(f"       Category: {gap['category']}")
        if gap.get('source'):
            print(f"       Source: {gap['source']}")
        print()

    print("\nTo auto-create missing experts:")
    print("  cli.py experts auto-build")
    print("\nTo auto-create with preview (dry run):")
    print("  cli.py experts auto-build --dry-run")

    return 0


def _experts_auto_build(args):
    """
    Auto-create all missing experts.

    Usage: cli.py experts auto-build [options]

    Options:
      --dry-run       Show what would be created without creating
      --confirm       Skip confirmation prompt
    """
    from core.expert_loader import ExpertLoader, ExpertType

    dry_run = "--dry-run" in args
    skip_confirm = "--confirm" in args

    loader = ExpertLoader(PROJECT_ROOT)
    gaps = loader.find_missing_experts()

    if not gaps:
        print("No missing experts to create.")
        return 0

    print(f"\nWill create {len(gaps)} expert(s):\n")
    for gap in gaps:
        category_str = f" ({gap['category']})" if gap.get('category') else ""
        print(f"  - {gap['name']} ({gap['type']}{category_str})")

    if dry_run:
        print("\n[DRY RUN] No experts created.")
        return 0

    if not skip_confirm:
        try:
            response = input("\nProceed? [y/N] ")
            if response.lower() != 'y':
                print("Cancelled.")
                return 0
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            return 0

    print("\nCreating experts (using ultra think mode)...")
    print("=" * 50)

    created = []
    failed = []

    for gap in gaps:
        name = gap["name"]
        print(f"\nCreating {name}...")
        success = loader.create_expert(
            name=name,
            expert_type=ExpertType.TECH,
            based_on=name,
            use_ultra_think=True
        )
        if success:
            created.append(name)
        else:
            failed.append(name)

    print(f"\nResults:")
    print(f"  Created: {len(created)}")
    print(f"  Failed:  {len(failed)}")

    if created:
        print(f"\nCreated experts: {', '.join(created)}")
    if failed:
        print(f"Failed experts: {', '.join(failed)}")

    return 0 if not failed else 1


def cmd_portal(args):
    """Start the management portal (dashboard UI)."""
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
        print("  cli.py cost estimate build --plan .orchestrator/specs/pending/auth.md")
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
# Sync Remote Command
# =============================================================================

def cmd_sync_remote(args=None):
    """Commit changes and create PR with AI-generated messages."""
    from workflows.syncing import SyncingWorkflow

    workflow = SyncingWorkflow(project_root=PROJECT_ROOT)
    result = workflow.run("")

    if result.success:
        print("\n" + "=" * 60)
        print("SYNC SUMMARY")
        print(f"  Branch: {result.data.get('branch_name')}")
        print(f"  Commit: {result.data.get('commit_hash')}")
        print(f"  PR: {result.data.get('pr_url')}")
        print("=" * 60)
        return 0
    else:
        print(f"\n[ERROR] Sync failed: {result.error}")
        if result.data.get('branch_name'):
            print(f"  Branch created: {result.data.get('branch_name')}")
        return 1


# =============================================================================
# Cache Command
# =============================================================================

def cmd_cache(args):
    """Manage planning cache."""
    from core.scout_cache import ScoutCache
    from core.checkpoint import CheckpointManager

    cache = ScoutCache(PROJECT_ROOT)
    checkpoint_mgr = CheckpointManager(SPECS_DIR)

    if not args or args[0] == "status":
        print("=== Cache Status ===\n")
        stats = cache.stats()
        print(f"Scout Cache:")
        print(f"  Entries: {stats['entries']}")
        print(f"  Size: {stats['size_mb']:.2f} MB")
        print(f"  TTL: {stats['ttl_hours']} hours")
        print(f"  Location: {stats['cache_dir']}")

        pending_checkpoints = checkpoint_mgr.list_pending()
        print(f"\nCheckpoints:")
        print(f"  Pending: {len(pending_checkpoints)}")
        if pending_checkpoints:
            for cp in pending_checkpoints[:5]:
                print(f"    - {cp['request'][:40]}... ({cp['phase']})")

    elif args[0] == "clear":
        what = args[1] if len(args) > 1 else "all"
        if what in ["all", "scout"]:
            cache.clear()
            print("Scout cache cleared")
        if what in ["all", "checkpoints"]:
            count = checkpoint_mgr.clear_all()
            print(f"Cleared {count} checkpoints")

    elif args[0] == "checkpoints":
        pending = checkpoint_mgr.list_pending()
        if not pending:
            print("No pending checkpoints")
            return 0
        print("=== Pending Checkpoints ===\n")
        for cp in pending:
            print(f"  {cp['request_hash'][:8]}: {cp['request'][:50]}")
            print(f"    Phase: {cp['phase']}, Attempts: {cp['attempt_count']}")
            print(f"    Created: {cp['created_at'][:19]}")
            print()

    else:
        print("Usage: cli.py cache [status|clear|checkpoints]")
        print("  status      - Show cache statistics")
        print("  clear       - Clear all caches")
        print("  clear scout - Clear only scout cache")
        print("  checkpoints - List pending checkpoints")
        return 1

    return 0


# =============================================================================
# Main
# =============================================================================

COMMANDS = {
    'setup': (cmd_setup, "Initialize environment"),
    'plan': (cmd_plan, "Create implementation plan"),
    'build': (cmd_build, "Execute a plan"),
    'status': (cmd_status, "Show build status for a plan"),
    'review': (cmd_review, "Review completed build"),
    'fix': (cmd_fix, "Fix issues from review"),
    'list': (cmd_list, "List all plans"),
    'docs': (cmd_docs, "Check documentation"),
    'experts': (cmd_experts, "Manage expert agents"),
    'cost': (cmd_cost, "Cost estimation and budgets"),
    'test': (cmd_test, "Run test suite"),
    'portal': (cmd_portal, "Start management portal"),
    'sync-remote': (cmd_sync_remote, "Sync changes to remote via PR"),
    'cache': (cmd_cache, "Manage planning cache"),
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
        print("  cli.py build .orchestrator/specs/pending/user-auth.md")
        print("  cli.py review .orchestrator/specs/completed/user-auth.md")
        print("  cli.py fix .orchestrator/specs/reviews/review-user-auth.md")
        print("  cli.py fix .orchestrator/specs/reviews/review.md --dry-run")
        print("  cli.py experts list                      # List all experts")
        print("  cli.py experts create auth --type domain --keywords auth,login")
        print("  cli.py test                              # Run all tests")
        print("  cli.py test --unit                       # Run unit tests only")
        print("  cli.py test --integration                # Run integration tests only")
        print("  cli.py test -v --cov                     # Verbose with coverage")
        print("  cli.py portal                            # Start management portal")
        print("  cli.py portal --port 8080                # Custom port")
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
    if cmd in ['setup', 'list', 'sync-remote']:
        return handler()
    else:
        return handler(args)


if __name__ == "__main__":
    sys.exit(main())
