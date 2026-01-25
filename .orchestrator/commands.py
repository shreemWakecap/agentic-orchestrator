"""Simple CLI commands - utilities that don't require workflow orchestration."""
import argparse
import json
import shutil
import socket
import sys
from pathlib import Path
from typing import Optional

ORCHESTRATOR_DIR = Path(__file__).parent
PROJECT_ROOT = ORCHESTRATOR_DIR.parent


# =============================================================================
# INIT COMMAND (Multi-Project Mode)
# =============================================================================

def run_init(args=None) -> int:
    """Initialize orchestrator for multi-project mode.

    This command sets up the orchestrator directory structure
    and prepares the database for multi-project use.
    """
    from config import get_config

    config = get_config()

    print("SDLC Orchestrator Initialization")
    print("=" * 50)

    home_path = config.orchestrator_home.home_path
    print(f"\nHome directory: {home_path}")

    # Create directory structure
    from core.home import OrchestratorHome

    home = OrchestratorHome(root=home_path)

    print("\nCreating directory structure...")
    home.ensure_structure()

    print(f"  [+] {home.config_dir}")
    print(f"  [+] {home.projects_dir}")
    print(f"  [+] {home.logs_dir}")

    # Check prerequisites
    print("\nChecking prerequisites...")
    ok = True
    for cmd in ['claude', 'git']:
        if shutil.which(cmd):
            print(f"  [+] {cmd}")
        else:
            print(f"  [!] {cmd} missing")
            ok = False

    # Check and initialize database
    print("\nInitializing database...")
    db_ok = _init_database()
    if not db_ok:
        ok = False

    # Summary
    print("\n" + "=" * 50)
    if ok:
        print("Initialization complete!")
        print("\nNext steps:")
        print("  1. Add a project: orch project add /path/to/your/project")
        print("  2. Switch to it:  orch project switch <project-name>")
        print("  3. Run scout:     orch scout")
    else:
        print("Initialization completed with warnings.")
        print("Please resolve the issues above before proceeding.")

    return 0 if ok else 1


def _init_database() -> bool:
    """Initialize the database for multi-project mode."""
    try:
        from db.config import DatabaseConfig
        config = DatabaseConfig.load()

        # Connect to PostgreSQL and create database if needed
        import psycopg2
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

        try:
            admin_conn = psycopg2.connect(
                host=config.host,
                port=config.port,
                user=config.user,
                password=config.password,
                database="postgres"
            )
            admin_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = admin_conn.cursor()

            # Check if database exists
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (config.name,))
            exists = cursor.fetchone()

            if not exists:
                print(f"  [*] Creating database '{config.name}'...")
                cursor.execute(f'CREATE DATABASE "{config.name}"')
                print(f"  [+] Database '{config.name}' created")
            else:
                print(f"  [+] Database '{config.name}' exists")

            cursor.close()
            admin_conn.close()

        except psycopg2.OperationalError as e:
            if "connection refused" in str(e).lower():
                print(f"  [!] PostgreSQL server not running at {config.host}:{config.port}")
            else:
                print(f"  [!] PostgreSQL error: {e}")
            return False

        # Connect and run migrations
        from db import get_database
        db = get_database()
        print(f"  [+] Connected: {config.host}:{config.port}/{config.name}")

        # Run Alembic migrations
        try:
            import subprocess
            result = subprocess.run(
                ["alembic", "-c", "db/alembic.ini", "upgrade", "head"],
                cwd=ORCHESTRATOR_DIR,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                print("  [+] Database migrations applied")
            else:
                stderr = result.stderr.strip()
                if stderr:
                    print(f"  [*] Migration note: {stderr[:100]}")
        except FileNotFoundError:
            print("  [!] Alembic not found - run: pip install alembic")
            return False

        return True

    except Exception as e:
        print(f"  [!] Database error: {e}")
        return False


# =============================================================================
# PROJECT COMMAND (Multi-Project Mode)
# =============================================================================

def run_project(args=None) -> int:
    """Manage projects.

    Subcommands:
        list [--all]              List projects
        add <path>                Add local project
        add --git <url> --dest <path>  Clone git project
        switch <name|id>          Activate project
        info [name|id]            Show project details
        archive <name|id>         Archive project
        restore <name|id>         Restore archived project
        remove <name|id>          Remove project
        fetch [name|id]           Git fetch
        pull [name|id]            Git pull
        status [name|id]          Git status
    """
    parser = argparse.ArgumentParser(
        prog="orch project",
        description="Manage projects"
    )
    subparsers = parser.add_subparsers(dest="action", help="Action")

    # list
    list_parser = subparsers.add_parser("list", help="List projects")
    list_parser.add_argument("--all", "-a", action="store_true", help="Include archived")

    # add
    add_parser = subparsers.add_parser("add", help="Add project")
    add_parser.add_argument("path", nargs="?", help="Local project path")
    add_parser.add_argument("--git", "-g", help="Git repository URL")
    add_parser.add_argument("--dest", "-d", help="Clone destination path")
    add_parser.add_argument("--branch", "-b", help="Git branch")
    add_parser.add_argument("--name", "-n", help="Project name (optional)")

    # switch
    switch_parser = subparsers.add_parser("switch", help="Switch active project")
    switch_parser.add_argument("name", help="Project name or ID")

    # info
    info_parser = subparsers.add_parser("info", help="Show project info")
    info_parser.add_argument("name", nargs="?", help="Project name or ID")

    # archive
    archive_parser = subparsers.add_parser("archive", help="Archive project")
    archive_parser.add_argument("name", help="Project name or ID")

    # restore
    restore_parser = subparsers.add_parser("restore", help="Restore archived project")
    restore_parser.add_argument("name", help="Project name or ID")

    # remove
    remove_parser = subparsers.add_parser("remove", help="Remove project")
    remove_parser.add_argument("name", help="Project name or ID")
    remove_parser.add_argument("--force", "-f", action="store_true", help="Skip confirmation")
    remove_parser.add_argument("--delete-files", action="store_true", help="Delete project files")

    # fetch
    fetch_parser = subparsers.add_parser("fetch", help="Git fetch")
    fetch_parser.add_argument("name", nargs="?", help="Project name or ID")

    # pull
    pull_parser = subparsers.add_parser("pull", help="Git pull")
    pull_parser.add_argument("name", nargs="?", help="Project name or ID")

    # status
    status_parser = subparsers.add_parser("status", help="Git status")
    status_parser.add_argument("name", nargs="?", help="Project name or ID")

    parsed = parser.parse_args(args or [])

    if not parsed.action:
        parser.print_help()
        return 0

    # Import project management components (database is source of truth)
    from db.repositories.project import get_project_repository
    from db.models import ProjectSourceType, ProjectStatus

    repo = get_project_repository()

    if parsed.action == "list":
        return _project_list(repo, include_archived=parsed.all)

    elif parsed.action == "add":
        if parsed.git:
            return _project_add_git(repo, parsed.git, parsed.dest, parsed.branch, parsed.name)
        elif parsed.path:
            return _project_add_local(repo, parsed.path, parsed.name)
        else:
            print("Error: Provide a path or --git URL")
            return 1

    elif parsed.action == "switch":
        return _project_switch(repo, parsed.name)

    elif parsed.action == "info":
        return _project_info(repo, parsed.name)

    elif parsed.action == "archive":
        return _project_archive(repo, parsed.name)

    elif parsed.action == "restore":
        return _project_restore(repo, parsed.name)

    elif parsed.action == "remove":
        return _project_remove(repo, parsed.name, parsed.force, parsed.delete_files)

    elif parsed.action == "fetch":
        return _project_git_fetch(repo, parsed.name)

    elif parsed.action == "pull":
        return _project_git_pull(repo, parsed.name)

    elif parsed.action == "status":
        return _project_git_status(repo, parsed.name)

    return 0


def _project_list(repo, include_archived: bool = False) -> int:
    """List all projects."""
    projects = repo.list_all(include_archived=include_archived, as_dict=True)

    if not projects:
        print("No projects found.")
        print("\nAdd one with: orch project add /path/to/project")
        return 0

    print("Projects")
    print("=" * 60)

    active = repo.get_active(as_dict=True)
    active_slug = active['slug'] if active else None

    for p in projects:
        marker = "*" if p['slug'] == active_slug else " "
        status_indicator = {
            "pending": "[...]",
            "indexing": "[IDX]",
            "ready": "[RDY]",
            "active": "[ACT]",
            "archived": "[ARC]",
        }.get(p['status'], "[???]")

        print(f"{marker} {status_indicator} {p['name']}")
        print(f"    Slug: {p['slug']}")
        print(f"    Path: {p['path']}")
        if p.get('git_url'):
            print(f"    Git:  {p['git_url']}")
        print()

    print(f"Total: {len(projects)} project(s)")
    if active:
        print(f"Active: {active['name']}")

    return 0


def _project_add_local(repo, path: str, name: Optional[str] = None) -> int:
    """Add a local project."""
    from core.home import get_orchestrator_home
    from db.models import ProjectSourceType, ProjectStatus

    path = Path(path).resolve()

    if not path.exists():
        print(f"Error: Path does not exist: {path}")
        return 1

    if not path.is_dir():
        print(f"Error: Path is not a directory: {path}")
        return 1

    # Check if already registered
    existing = repo.get_by_path(str(path), as_dict=True)
    if existing:
        print(f"Error: Project already registered as '{existing['name']}' ({existing['slug']})")
        return 1

    # Determine name
    if not name:
        name = path.name

    print(f"Adding local project: {name}")
    print(f"  Path: {path}")

    # Create project directly in database
    project = repo.create_with_auto_slug(
        name=name,
        path=str(path),
        source_type=ProjectSourceType.LOCAL,
    )

    # Create project data directory
    home = get_orchestrator_home()
    home.ensure_project_structure(project['slug'])

    # Update status to ready (no cloning needed)
    repo.update_status(project['id'], ProjectStatus.READY)

    print(f"\n[+] Project added: {project['name']} ({project['slug']})")
    print(f"\nNext steps:")
    print(f"  orch project switch {project['slug']}")
    print(f"  orch scout")

    return 0


def _project_add_git(repo, git_url: str, dest: Optional[str], branch: Optional[str], name: Optional[str]) -> int:
    """Add a git project by cloning."""
    from core.home import get_orchestrator_home
    from db.models import ProjectSourceType, ProjectStatus

    if not dest:
        print("Error: --dest is required for git projects")
        return 1

    dest_path = Path(dest).resolve()

    if dest_path.exists():
        print(f"Error: Destination already exists: {dest_path}")
        return 1

    # Determine name from URL if not provided
    if not name:
        # Extract name from git URL
        name = git_url.rstrip('/').split('/')[-1]
        if name.endswith('.git'):
            name = name[:-4]

    print(f"Cloning git project: {name}")
    print(f"  URL:    {git_url}")
    print(f"  Dest:   {dest_path}")
    if branch:
        print(f"  Branch: {branch}")

    # Clone repository
    import subprocess
    clone_cmd = ["git", "clone", git_url, str(dest_path)]
    if branch:
        clone_cmd.extend(["--branch", branch])

    print("\nCloning...")
    result = subprocess.run(clone_cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error: Clone failed: {result.stderr}")
        return 1

    print("  [+] Clone complete")

    # Create project directly in database
    project = repo.create_with_auto_slug(
        name=name,
        path=str(dest_path),
        source_type=ProjectSourceType.GIT,
        git_url=git_url,
        git_branch=branch,
    )

    # Create project data directory
    home = get_orchestrator_home()
    home.ensure_project_structure(project['slug'])

    # Update status to ready
    repo.update_status(project['id'], ProjectStatus.READY)

    print(f"\n[+] Project added: {project['name']} ({project['slug']})")
    print(f"\nNext steps:")
    print(f"  orch project switch {project['slug']}")
    print(f"  orch scout")

    return 0


def _project_switch(repo, name: str) -> int:
    """Switch to a project."""
    project = repo.get_by_slug_or_id(name, as_dict=True)

    if not project:
        print(f"Error: Project not found: {name}")
        return 1

    if project['status'] == "archived":
        print(f"Error: Project is archived. Restore it first:")
        print(f"  orch project restore {name}")
        return 1

    repo.set_active(project['id'])
    print(f"Switched to: {project['name']}")

    return 0


def _project_info(repo, name: Optional[str]) -> int:
    """Show project info."""
    if name:
        project = repo.get_by_slug_or_id(name, as_dict=True)
    else:
        project = repo.get_active(as_dict=True)
        if not project:
            print("No active project. Specify a project name.")
            return 1

    if not project:
        print(f"Error: Project not found: {name}")
        return 1

    print(f"Project: {project['name']}")
    print("=" * 50)
    print(f"  ID:          {project['id']}")
    print(f"  Slug:        {project['slug']}")
    print(f"  Path:        {project['path']}")
    print(f"  Status:      {project['status']}")
    print(f"  Source:      {project['source_type']}")
    if project.get('git_url'):
        print(f"  Git URL:     {project['git_url']}")
    if project.get('git_branch'):
        print(f"  Git Branch:  {project['git_branch']}")
    print(f"  Added:       {project.get('added_at')}")
    if project.get('last_accessed'):
        print(f"  Last Access: {project['last_accessed']}")
    if project.get('indexed_at'):
        print(f"  Indexed:     {project['indexed_at']}")

    return 0


def _project_archive(repo, name: str) -> int:
    """Archive a project."""
    project = repo.get_by_slug_or_id(name, as_dict=True)

    if not project:
        print(f"Error: Project not found: {name}")
        return 1

    repo.archive(project['id'])
    print(f"Archived: {project['name']}")

    return 0


def _project_restore(repo, name: str) -> int:
    """Restore an archived project."""
    project = repo.get_by_slug_or_id(name, as_dict=True)

    if not project:
        print(f"Error: Project not found: {name}")
        return 1

    repo.restore(project['id'])
    print(f"Restored: {project['name']}")

    return 0


def _project_remove(repo, name: str, force: bool, delete_files: bool) -> int:
    """Remove a project."""
    project = repo.get_by_slug_or_id(name, as_dict=True)

    if not project:
        print(f"Error: Project not found: {name}")
        return 1

    if not force:
        print(f"Remove project: {project['name']}?")
        print(f"  Path: {project['path']}")
        if delete_files:
            print("  WARNING: Project files will be deleted!")
        response = input("\nType 'yes' to confirm: ")
        if response.lower() != 'yes':
            print("Cancelled.")
            return 0

    # Remove project data directory
    from core.home import get_orchestrator_home
    home = get_orchestrator_home()
    project_dir = home.project_dir(project['slug'])

    if project_dir.exists():
        import shutil
        shutil.rmtree(project_dir)
        print(f"  [+] Removed project data: {project_dir}")

    # Optionally delete project files
    if delete_files:
        project_path = Path(project['path'])
        if project_path.exists():
            import shutil
            shutil.rmtree(project_path)
            print(f"  [+] Removed project files: {project_path}")

    # Remove from database
    repo.delete(project['id'])
    print(f"\n[+] Project removed: {project['name']}")

    return 0


def _project_git_fetch(repo, name: Optional[str]) -> int:
    """Git fetch for a project."""
    if name:
        project = repo.get_by_slug_or_id(name, as_dict=True)
    else:
        project = repo.get_active(as_dict=True)

    if not project:
        print("Error: No project specified and no active project")
        return 1

    import subprocess
    result = subprocess.run(
        ["git", "fetch", "--all"],
        cwd=project['path'],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return 1

    print(f"Fetched: {project['name']}")
    if result.stdout:
        print(result.stdout)

    return 0


def _project_git_pull(repo, name: Optional[str]) -> int:
    """Git pull for a project."""
    if name:
        project = repo.get_by_slug_or_id(name, as_dict=True)
    else:
        project = repo.get_active(as_dict=True)

    if not project:
        print("Error: No project specified and no active project")
        return 1

    import subprocess
    result = subprocess.run(
        ["git", "pull"],
        cwd=project['path'],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return 1

    print(f"Pulled: {project['name']}")
    if result.stdout:
        print(result.stdout)

    return 0


def _project_git_status(repo, name: Optional[str]) -> int:
    """Git status for a project."""
    if name:
        project = repo.get_by_slug_or_id(name, as_dict=True)
    else:
        project = repo.get_active(as_dict=True)

    if not project:
        print("Error: No project specified and no active project")
        return 1

    import subprocess
    result = subprocess.run(
        ["git", "status", "--short", "--branch"],
        cwd=project['path'],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return 1

    print(f"Git status: {project['name']}")
    print(f"Path: {project['path']}")
    print()
    if result.stdout:
        print(result.stdout)
    else:
        print("(clean)")

    return 0


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

    # Initialize PostgreSQL database
    db_ok = False
    try:
        from db.config import DatabaseConfig
        config = DatabaseConfig.load()

        # Step 1: Check PostgreSQL server and create database if needed
        import psycopg2
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

        # Connect to 'postgres' database to check server and create our database
        try:
            admin_conn = psycopg2.connect(
                host=config.host,
                port=config.port,
                user=config.user,
                password=config.password,
                database="postgres"
            )
            admin_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = admin_conn.cursor()

            # Check if our database exists
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (config.name,))
            exists = cursor.fetchone()

            if not exists:
                print(f"  [*] Creating database '{config.name}'...")
                cursor.execute(f'CREATE DATABASE "{config.name}"')
                print(f"  [+] Database '{config.name}' created")

            cursor.close()
            admin_conn.close()

        except psycopg2.OperationalError as e:
            if "connection refused" in str(e).lower():
                print(f"  [!] PostgreSQL server not running at {config.host}:{config.port}")
            else:
                print(f"  [!] PostgreSQL error: {e}")
            print(f"      Ensure PostgreSQL is running and ORCH_DB_* environment variables are set")
            ok = False

        # Step 2: Connect to our database and create tables
        if ok:
            from db import get_database
            db = get_database()
            print(f"  [+] Database connected: {config.host}:{config.port}/{config.name}")
            db_ok = True

    except Exception as e:
        print(f"  [!] Database error: {e}")
        print(f"      Set ORCH_DB_* environment variables to configure PostgreSQL")
        ok = False

    # Run database migrations (only if database is connected)
    if db_ok:
        try:
            import subprocess
            result = subprocess.run(
                ["alembic", "-c", "db/alembic.ini", "upgrade", "head"],
                cwd=ORCHESTRATOR_DIR,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                print("  [+] Database migrations applied")
            else:
                # Log error but don't fail setup - tables might already exist
                stderr = result.stderr.strip()
                if stderr:
                    print(f"  [*] Migration note: {stderr[:100]}")
        except FileNotFoundError:
            print("  [!] Alembic not found - run: uv sync")
            ok = False
        except Exception as e:
            print(f"  [!] Migration error: {e}")
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
