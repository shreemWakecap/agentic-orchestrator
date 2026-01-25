"""
Migration script to seed database from filesystem files.

This script reads agent definitions, expert definitions, and configuration
from the filesystem (.md and .json files) and inserts them into the database.

Usage:
    python -m db.migrations.seed_from_files [--dry-run]

Or via CLI:
    orchestrator migrate-to-db [--dry-run]
"""
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple


def parse_markdown_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """Parse YAML frontmatter from markdown content.

    Args:
        content: Markdown content with optional YAML frontmatter

    Returns:
        Tuple of (frontmatter_dict, body_content)
    """
    frontmatter = {}
    body = content

    # Check for YAML frontmatter (between --- markers)
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            import yaml
            try:
                frontmatter = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError:
                frontmatter = {}
            body = parts[2].strip()

    return frontmatter, body


def seed_agent_definitions(orchestrator_dir: Path, dry_run: bool = False) -> List[str]:
    """Seed agent definitions from .md files to database.

    Args:
        orchestrator_dir: Path to the .orchestrator directory
        dry_run: If True, only report what would be done

    Returns:
        List of agent names that were seeded
    """
    from db.repositories.agent_definition import get_agent_definition_repository

    agents_dir = orchestrator_dir / "agents"
    seeded = []

    if not agents_dir.exists():
        print(f"  agents/ directory not found at {agents_dir}")
        return seeded

    repo = get_agent_definition_repository()

    print("=== Seeding Agent Definitions ===")

    for agent_file in sorted(agents_dir.glob("*.md")):
        name = agent_file.stem
        content = agent_file.read_text(encoding="utf-8")
        frontmatter, body = parse_markdown_frontmatter(content)

        # Extract metadata from frontmatter
        description = frontmatter.get("description", "")
        tools = frontmatter.get("tools", [])
        model = frontmatter.get("model")
        is_agentic = frontmatter.get("is_agentic", False)
        output_markers = frontmatter.get("output_markers", [])

        print(f"  {name}: ", end="")

        if dry_run:
            print(f"would seed ({len(body)} chars)")
        else:
            # Check if exists, update or create
            if repo.exists(name):
                repo.update(
                    name,
                    system_prompt=body,
                    description=description,
                    tools=tools,
                    model=model,
                    is_agentic=is_agentic,
                    output_markers=output_markers,
                )
                print(f"updated ({len(body)} chars)")
            else:
                repo.create(
                    name=name,
                    system_prompt=body,
                    description=description,
                    tools=tools,
                    model=model,
                    is_agentic=is_agentic,
                    output_markers=output_markers,
                )
                print(f"created ({len(body)} chars)")

        seeded.append(name)

    if not seeded:
        print("  (no agent files found)")

    return seeded


def seed_expert_definitions(orchestrator_dir: Path, dry_run: bool = False) -> List[str]:
    """Seed expert definitions from .md files to database.

    Args:
        orchestrator_dir: Path to the .orchestrator directory
        dry_run: If True, only report what would be done

    Returns:
        List of expert names that were seeded
    """
    from db.repositories.expert_definition import get_expert_definition_repository

    experts_dir = orchestrator_dir / "agents" / "experts"
    seeded = []

    if not experts_dir.exists():
        print(f"  agents/experts/ directory not found at {experts_dir}")
        return seeded

    repo = get_expert_definition_repository()

    print("\n=== Seeding Expert Definitions ===")

    for expert_file in sorted(experts_dir.glob("*.md")):
        # Skip _meta.md (template file)
        if expert_file.name == "_meta.md":
            print(f"  {expert_file.name}: skipping (meta template)")
            continue

        name = expert_file.stem
        content = expert_file.read_text(encoding="utf-8")
        frontmatter, body = parse_markdown_frontmatter(content)

        # Extract metadata from frontmatter
        description = frontmatter.get("description", "")
        expert_type = frontmatter.get("type", "tech")
        category = frontmatter.get("category", "general")
        domain_keywords = frontmatter.get("keywords", [])
        module_path = frontmatter.get("module_path")
        trigger_keywords = frontmatter.get("trigger_keywords", [])
        trigger_paths = frontmatter.get("trigger_paths", [])
        trigger_topics = frontmatter.get("trigger_topics", [])
        weight = frontmatter.get("weight", 1.0)

        print(f"  {name}: ", end="")

        if dry_run:
            print(f"would seed ({len(body)} chars)")
        else:
            # Check if exists, update or create
            if repo.exists(name):
                repo.update(
                    name,
                    system_prompt=body,
                    description=description,
                    expert_type=expert_type,
                    category=category,
                    domain_keywords=domain_keywords,
                    module_path=module_path,
                    trigger_keywords=trigger_keywords,
                    trigger_paths=trigger_paths,
                    trigger_topics=trigger_topics,
                    weight=weight,
                )
                print(f"updated ({len(body)} chars)")
            else:
                repo.create(
                    name=name,
                    system_prompt=body,
                    description=description,
                    expert_type=expert_type,
                    category=category,
                    domain_keywords=domain_keywords,
                    module_path=module_path,
                    trigger_keywords=trigger_keywords,
                    trigger_paths=trigger_paths,
                    trigger_topics=trigger_topics,
                    weight=weight,
                )
                print(f"created ({len(body)} chars)")

        seeded.append(name)

    if not seeded:
        print("  (no expert files found)")

    return seeded


def seed_config(orchestrator_dir: Path, dry_run: bool = False) -> List[str]:
    """Seed configuration from .json files to database.

    Args:
        orchestrator_dir: Path to the .orchestrator directory
        dry_run: If True, only report what would be done

    Returns:
        List of config types that were seeded
    """
    from db.repositories.config_repository import get_config_repository

    config_dir = orchestrator_dir / "config"
    seeded = []

    if not config_dir.exists():
        print(f"  config/ directory not found at {config_dir}")
        return seeded

    repo = get_config_repository()

    print("\n=== Seeding Configuration ===")

    config_files = [
        ("agent.json", "agent"),
        ("budget.json", "budget"),
    ]

    for filename, config_type in config_files:
        config_file = config_dir / filename
        if not config_file.exists():
            print(f"  {filename}: not found, skipping")
            continue

        content = config_file.read_text(encoding="utf-8")
        try:
            config_data = json.loads(content)
        except json.JSONDecodeError as e:
            print(f"  {filename}: invalid JSON - {e}")
            continue

        print(f"  {filename}: ", end="")

        if dry_run:
            print(f"would seed ({len(config_data)} keys)")
        else:
            repo.set_config(config_type, config_data)
            print(f"seeded ({len(config_data)} keys)")

        seeded.append(config_type)

    if not seeded:
        print("  (no config files found)")

    return seeded


def run_migration(orchestrator_dir: Path, dry_run: bool = False) -> Tuple[List[str], List[str], List[str]]:
    """Run full migration from files to database.

    Args:
        orchestrator_dir: Path to the .orchestrator directory
        dry_run: If True, only report what would be done

    Returns:
        Tuple of (agents, experts, configs) that were seeded
    """
    print(f"Orchestrator directory: {orchestrator_dir}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}\n")

    agents = seed_agent_definitions(orchestrator_dir, dry_run=dry_run)
    experts = seed_expert_definitions(orchestrator_dir, dry_run=dry_run)
    configs = seed_config(orchestrator_dir, dry_run=dry_run)

    action = "would be seeded" if dry_run else "seeded"
    print(f"\n=== Summary ===")
    print(f"Agents: {len(agents)} {action}")
    print(f"Experts: {len(experts)} {action}")
    print(f"Configs: {len(configs)} {action}")

    if dry_run:
        print("\nRe-run without --dry-run to apply changes")

    return agents, experts, configs


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Seed database from filesystem files")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    args = parser.parse_args()

    # Determine orchestrator directory (this file is in db/migrations/)
    orchestrator_dir = Path(__file__).parent.parent.parent

    run_migration(orchestrator_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
