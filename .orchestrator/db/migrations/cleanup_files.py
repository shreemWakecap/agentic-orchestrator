"""
Cleanup script to remove old filesystem files after migration to database.

This script deletes:
- Agent .md files from .orchestrator/agents/
- Expert .md files from .orchestrator/agents/experts/ (except _meta.md)
- Config JSON files from .orchestrator/config/

Usage:
    python -m db.migrations.cleanup_files [--dry-run]

Or via CLI:
    orchestrator cleanup-files [--dry-run]
"""
from pathlib import Path
from typing import List, Tuple


def cleanup_agent_files(orchestrator_dir: Path, dry_run: bool = False) -> List[str]:
    """Remove agent .md files from filesystem.

    Args:
        orchestrator_dir: Path to the .orchestrator directory
        dry_run: If True, only report what would be deleted

    Returns:
        List of deleted (or would-be-deleted) filenames
    """
    agents_dir = orchestrator_dir / "agents"
    deleted = []

    if not agents_dir.exists():
        print("  agents/ directory not found")
        return deleted

    for agent_file in sorted(agents_dir.glob("*.md")):
        if agent_file.is_file():
            print(f"  {agent_file.name}: ", end="")
            if dry_run:
                print("would delete")
            else:
                agent_file.unlink()
                print("deleted")
            deleted.append(agent_file.name)

    if not deleted:
        print("  (no agent files found)")

    return deleted


def cleanup_expert_files(orchestrator_dir: Path, dry_run: bool = False) -> List[str]:
    """Remove expert .md files from filesystem (except _meta.md).

    Args:
        orchestrator_dir: Path to the .orchestrator directory
        dry_run: If True, only report what would be deleted

    Returns:
        List of deleted (or would-be-deleted) filenames
    """
    experts_dir = orchestrator_dir / "agents" / "experts"
    deleted = []

    if not experts_dir.exists():
        print("  agents/experts/ directory not found")
        return deleted

    for expert_file in sorted(experts_dir.glob("*.md")):
        # Keep _meta.md for expert generation
        if expert_file.name == "_meta.md":
            print(f"  {expert_file.name}: keeping (meta-expert template)")
            continue

        if expert_file.is_file():
            print(f"  {expert_file.name}: ", end="")
            if dry_run:
                print("would delete")
            else:
                expert_file.unlink()
                print("deleted")
            deleted.append(expert_file.name)

    if not deleted:
        print("  (no expert files to delete)")

    return deleted


def cleanup_config_files(orchestrator_dir: Path, dry_run: bool = False) -> List[str]:
    """Remove config JSON files from filesystem.

    Args:
        orchestrator_dir: Path to the .orchestrator directory
        dry_run: If True, only report what would be deleted

    Returns:
        List of deleted (or would-be-deleted) filenames
    """
    config_dir = orchestrator_dir / "config"
    deleted = []
    config_files = ["agent.json", "budget.json"]

    if not config_dir.exists():
        print("  config/ directory not found")
        return deleted

    for filename in config_files:
        config_file = config_dir / filename
        if config_file.exists():
            print(f"  {filename}: ", end="")
            if dry_run:
                print("would delete")
            else:
                config_file.unlink()
                print("deleted")
            deleted.append(filename)
        else:
            print(f"  {filename}: not found (already deleted?)")

    return deleted


def run_cleanup(orchestrator_dir: Path, dry_run: bool = False) -> Tuple[List[str], List[str], List[str]]:
    """Run full cleanup of old filesystem files.

    Args:
        orchestrator_dir: Path to the .orchestrator directory
        dry_run: If True, only report what would be deleted

    Returns:
        Tuple of (agent_files, expert_files, config_files) that were deleted
    """
    print(f"Orchestrator directory: {orchestrator_dir}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}\n")

    print("=== Agent Files ===")
    agents = cleanup_agent_files(orchestrator_dir, dry_run=dry_run)

    print("\n=== Expert Files ===")
    experts = cleanup_expert_files(orchestrator_dir, dry_run=dry_run)

    print("\n=== Config Files ===")
    configs = cleanup_config_files(orchestrator_dir, dry_run=dry_run)

    action = "would be deleted" if dry_run else "deleted"
    print(f"\n=== Summary ===")
    print(f"Agent files: {len(agents)} {action}")
    print(f"Expert files: {len(experts)} {action}")
    print(f"Config files: {len(configs)} {action}")
    print(f"Total: {len(agents) + len(experts) + len(configs)} files")

    if dry_run:
        print("\nRe-run without --dry-run to delete files")

    return agents, experts, configs


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Cleanup old filesystem files after DB migration")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without deleting")
    args = parser.parse_args()

    # Determine orchestrator directory (this file is in db/migrations/)
    orchestrator_dir = Path(__file__).parent.parent.parent

    run_cleanup(orchestrator_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
