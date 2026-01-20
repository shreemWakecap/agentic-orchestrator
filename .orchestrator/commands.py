"""Simple CLI commands - utilities that don't require workflow orchestration."""
import argparse
import json
import shutil
import socket
from pathlib import Path

ORCHESTRATOR_DIR = Path(__file__).parent
PROJECT_ROOT = ORCHESTRATOR_DIR.parent


def _find_free_port() -> int:
    """Find a random available port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


def run_portal(args=None) -> int:
    """Start web portal on random available port."""
    port = _find_free_port()
    print(f"Portal: http://127.0.0.1:{port}")
    print("Press Ctrl+C to stop\n")

    try:
        from portal.app import run_portal as start_portal
        start_portal(host="127.0.0.1", port=port)
    except ImportError:
        print("Install dependencies: uv pip install fastapi uvicorn jinja2")
        return 1
    except KeyboardInterrupt:
        print("\nStopped.")

    return 0


def run_setup(args=None) -> int:
    """Initialize orchestrator environment."""
    print("Setup\n" + "=" * 40)

    # Check prerequisites
    ok = True
    for cmd in ['claude', 'uv']:
        if shutil.which(cmd):
            print(f"  [+] {cmd}")
        else:
            print(f"  [!] {cmd} missing")
            ok = False

    # Create directories (only config and agents/experts remain file-based)
    for d in ['agents/experts', 'config', 'docs']:
        (ORCHESTRATOR_DIR / d).mkdir(parents=True, exist_ok=True)
    print("  [+] Directories created")

    # Initialize SQLite database
    try:
        from db import get_database, get_db_path
        db = get_database()
        print(f"  [+] Database initialized: {get_db_path()}")
    except Exception as e:
        print(f"  [!] Database error: {e}")
        ok = False

    # Check and refresh documentation
    try:
        from core.docs_loader import DocsLoader
        docs_loader = DocsLoader(PROJECT_ROOT)
        status = docs_loader.get_status()

        stale_count = len(status['stale'])
        missing_count = len(status['missing'])

        if stale_count > 0 or missing_count > 0:
            print(f"\n  Docs: {status['fresh']} fresh, {stale_count} stale, {missing_count} missing")
            print("  Refreshing documentation...")
            result = docs_loader.refresh()
            if result['updated'] > 0:
                print(f"  [+] Docs updated: {result['updated']} refreshed, {result['failed']} failed")
            elif result['failed'] > 0:
                print(f"  [!] Docs refresh failed: {result['failed']} errors")
                ok = False
        else:
            print(f"  [+] Docs: {status['total']} cached, all fresh")
    except Exception as e:
        print(f"  [!] Docs error: {e}")
        ok = False

    print("\n" + ("Setup complete!" if ok else "Setup completed with issues"))
    return 0 if ok else 1


def run_experts(args=None) -> int:
    """Manage expert agents."""
    import argparse

    parser = argparse.ArgumentParser(description="Manage expert agents")
    subparsers = parser.add_subparsers(dest="action", help="Action to perform")

    # List subcommand
    subparsers.add_parser("list", help="List all experts")

    # Create subcommand
    create_parser = subparsers.add_parser("create", help="Create an expert")
    create_parser.add_argument("name", help="Expert name")
    create_parser.add_argument(
        "--type", "-t",
        choices=["tech", "domain", "module"],
        default="tech",
        help="Expert type"
    )
    create_parser.add_argument(
        "--keywords", "-k",
        nargs="+",
        help="Domain keywords (for domain experts)"
    )

    # Generate subcommand
    gen_parser = subparsers.add_parser("generate", help="Auto-generate missing experts")
    gen_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Regenerate even if exists"
    )

    # Refresh subcommand
    subparsers.add_parser("refresh", help="Refresh structure expert")

    # Report subcommand
    subparsers.add_parser("report", help="Show what experts could be generated")

    parsed = parser.parse_args(args or [])

    if not parsed.action:
        parser.print_help()
        return 0

    from core.expert_loader import ExpertLoader, ExpertType
    from core.expert_generator import ExpertGenerator

    loader = ExpertLoader(PROJECT_ROOT)
    generator = ExpertGenerator(PROJECT_ROOT)

    if parsed.action == "list":
        experts = loader.list_experts()
        print("Experts\n" + "=" * 40)

        # Tech experts
        for category in ["language", "framework", "tool", "general"]:
            if experts["tech"][category]:
                print(f"\n{category.title()}:")
                for e in experts["tech"][category]:
                    print(f"  - {e['name']}: {e['description']}")

        # Domain experts
        if experts["domain"]:
            print("\nDomain:")
            for e in experts["domain"]:
                kws = f" [{', '.join(e['keywords'][:3])}]" if e.get("keywords") else ""
                print(f"  - {e['name']}: {e['description']}{kws}")

        # Module experts
        if experts["module"]:
            print("\nModule:")
            for e in experts["module"]:
                path = f" ({e['module_path']})" if e.get("module_path") else ""
                print(f"  - {e['name']}: {e['description']}{path}")

        total = sum(len(experts["tech"][c]) for c in experts["tech"]) + len(experts["domain"]) + len(experts["module"])
        print(f"\nTotal: {total} experts")
        return 0

    elif parsed.action == "create":
        expert_type = ExpertType(parsed.type)
        keywords = parsed.keywords or []

        print(f"Creating {parsed.type} expert: {parsed.name}")
        if loader.create_expert(
            parsed.name,
            expert_type=expert_type,
            domain_keywords=keywords,
            use_ultra_think=True,
        ):
            print(f"  Created: agents/experts/{parsed.name}.md")
            return 0
        else:
            print("  Failed to create expert")
            return 1

    elif parsed.action == "generate":
        print("Auto-generating missing experts...")
        generated = generator.generate_all(force=parsed.force)
        if generated:
            print(f"\nGenerated {len(generated)} experts:")
            for name in generated:
                print(f"  - {name}")
        else:
            print("No missing experts to generate")
        return 0

    elif parsed.action == "refresh":
        print("Refreshing structure expert...")
        if generator.refresh_structure_expert():
            print("  Updated: agents/experts/structure.md")
            return 0
        else:
            print("  Failed (run scout first to build knowledge)")
            return 1

    elif parsed.action == "report":
        report = generator.get_generation_report()
        print("Expert Generation Report\n" + "=" * 40)

        print(f"\nExisting experts ({len(report['existing'])}):")
        for name in report["existing"]:
            print(f"  - {name}")

        if report["missing_tech"]:
            print(f"\nMissing tech experts ({len(report['missing_tech'])}):")
            for name in report["missing_tech"]:
                print(f"  - {name}")

        if report["missing_domain"]:
            print(f"\nMissing domain experts ({len(report['missing_domain'])}):")
            for name in report["missing_domain"]:
                print(f"  - {name}")

        print(f"\nStructure expert: {'Yes' if report['has_structure'] else 'No'}")

        return 0

    return 0


def run_knowledge(args=None) -> int:
    """View knowledge store status (from SQLite database)."""
    from core.knowledge_store import KnowledgeStore

    store = KnowledgeStore(PROJECT_ROOT)

    print("Knowledge Store\n" + "=" * 40)

    if not store.exists():
        print("\nNo codebase knowledge found.")
        print("Run: uv run cli.py scout")
        return 0

    knowledge = store.load()
    if not knowledge:
        print("\nFailed to load knowledge")
        return 1

    # Project info
    if knowledge.project.name:
        print(f"\nProject: {knowledge.project.name}")
        print(f"  Type: {knowledge.project.type}")
        print(f"  Language: {knowledge.project.primary_language}")

    # Technologies
    all_tech = (
        [f"{t.name}" for t in knowledge.technologies.languages] +
        [f"{t.name}" for t in knowledge.technologies.frameworks] +
        [f"{t.name}" for t in knowledge.technologies.tools]
    )
    if all_tech:
        print(f"\nTechnologies: {', '.join(all_tech)}")

    # Architecture
    if knowledge.architecture.pattern != "unknown":
        print(f"\nArchitecture: {knowledge.architecture.pattern}")
        if knowledge.architecture.modules:
            print(f"  Modules: {len(knowledge.architecture.modules)}")

    # Domains
    if knowledge.domains:
        domain_names = [d.name for d in knowledge.domains]
        print(f"\nDomains: {', '.join(domain_names)}")

    # Statistics
    if knowledge.statistics:
        stats = knowledge.statistics
        if "total_files" in stats:
            print(f"\nStatistics:")
            print(f"  Files: {stats.get('total_files', 'N/A')}")
            if stats.get('test_files'):
                print(f"  Tests: {stats.get('test_files')}")

    # Last updated
    if knowledge.last_updated:
        print(f"\nLast updated: {knowledge.last_updated}")

    # Scan metadata
    meta = store.load_meta()
    if meta:
        print(f"  Scan type: {meta.scan_type}")
        print(f"  Duration: {meta.duration_seconds:.1f}s")

    return 0


def run_git_status(args=None) -> int:
    """Display git statistics using git commands only (no AI dependencies).

    Supports --json for JSON output and --verbose for detailed information.
    """
    parser = argparse.ArgumentParser(
        description="Show git repository statistics using git commands"
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        dest="json_output",
        help="Output in JSON format"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed information"
    )
    parser.add_argument(
        "--remote", "-r",
        default="origin",
        help="Remote name to compare against (default: origin)"
    )
    parser.add_argument(
        "--target", "-t",
        default="main",
        help="Target branch for merge status (default: main)"
    )

    parsed = parser.parse_args(args or [])

    from portal.services.git_statistics_service import GitStatisticsService

    service = GitStatisticsService(PROJECT_ROOT)

    # Check if we're in a git repository
    if not service.is_git_repository():
        if parsed.json_output:
            print(json.dumps({"error": "Not a git repository"}, indent=2))
        else:
            print("Error: Not a git repository")
        return 1

    # Get all statistics
    stats = service.get_all_statistics(
        remote=parsed.remote,
        target_branch=parsed.target
    )

    if parsed.json_output:
        # JSON output
        print(json.dumps(service.to_dict(stats), indent=2))
        return 0

    # Formatted console output
    print("Git Statistics\n" + "=" * 50)

    # Branch info
    branch = stats.branch_info
    print(f"\nBranch: {branch.name}")
    if branch.tracking_branch:
        print(f"  Tracking: {branch.tracking_branch}")
    if branch.is_detached:
        print("  (detached HEAD)")

    # Commit counts
    commits = stats.commit_count
    if not commits.error:
        print(f"\nCommits:")
        print(f"  Ahead of {commits.remote_branch}: {commits.ahead}")
        print(f"  Behind {commits.remote_branch}: {commits.behind}")
        if parsed.verbose:
            print(f"  Total local commits: {commits.total_local}")
    elif parsed.verbose:
        print(f"\nCommits: {commits.error}")

    # File statistics
    files = stats.file_statistics
    if not files.error:
        print(f"\nFiles:")
        print(f"  Tracked: {files.tracked_files}")
        if files.modified_files:
            print(f"  Modified: {files.modified_files}")
        if files.staged_files:
            print(f"  Staged: {files.staged_files}")
        if files.untracked_files:
            print(f"  Untracked: {files.untracked_files}")
        if parsed.verbose:
            if files.added_files:
                print(f"  Added: {files.added_files}")
            if files.deleted_files:
                print(f"  Deleted: {files.deleted_files}")
            if files.renamed_files:
                print(f"  Renamed: {files.renamed_files}")
            if files.ignored_files:
                print(f"  Ignored: {files.ignored_files}")

    # PR status
    pr = stats.pr_status
    if pr and not pr.error:
        print(f"\nPull Request: #{pr.number}")
        print(f"  Title: {pr.title}")
        print(f"  State: {pr.state}")
        print(f"  {pr.head_branch} -> {pr.base_branch}")
        if pr.mergeable:
            print(f"  Mergeable: {pr.mergeable}")
        if pr.checks_status:
            print(f"  Checks: {pr.checks_status}")
        if parsed.verbose:
            print(f"  Changes: +{pr.additions} -{pr.deletions} ({pr.changed_files} files)")
            if pr.review_decision:
                print(f"  Review: {pr.review_decision}")
            print(f"  URL: {pr.url}")
    elif parsed.verbose and pr and pr.error:
        print(f"\nPull Request: {pr.error}")

    # Merge status
    merge = stats.merge_status
    if not merge.error:
        print(f"\nMerge Status (vs {parsed.target}):")
        if merge.can_merge:
            print("  Can merge: Yes")
        elif merge.has_conflicts:
            print("  Can merge: No (conflicts)")
            if parsed.verbose and merge.conflict_files:
                print("  Conflict files:")
                for f in merge.conflict_files[:5]:
                    print(f"    - {f}")
                if len(merge.conflict_files) > 5:
                    print(f"    ... and {len(merge.conflict_files) - 5} more")
        if parsed.verbose and merge.merge_base:
            print(f"  Merge base: {merge.merge_base}")
    elif parsed.verbose:
        print(f"\nMerge Status: {merge.error}")

    # Remote info (verbose only)
    if parsed.verbose:
        remote = stats.remote_info
        if not remote.error:
            print(f"\nRemote ({remote.name}):")
            print(f"  URL: {remote.fetch_url}")
            if remote.head_branch:
                print(f"  Default branch: {remote.head_branch}")
            if remote.branches:
                print(f"  Branches: {len(remote.branches)}")

    return 0
