#!/usr/bin/env python3
"""
init_setup.py - Initialize SDLC Orchestrator environment.

Automatically:
1. Checks prerequisites (uv, claude CLI)
2. Creates required directories
3. Fetches missing ai_docs
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from core.docs_loader import DocsLoader


def check_command(name: str) -> bool:
    return shutil.which(name) is not None


def run_setup(project_root: Path) -> bool:
    """Run setup. Returns True if successful."""
    print("=== SDLC Orchestrator Setup ===\n")
    ok = True

    # 1. Prerequisites
    print("[1/3] Prerequisites...")
    if not check_command('claude'):
        print("  [!] claude CLI missing - install: npm i -g @anthropic-ai/claude-code")
        ok = False
    else:
        print("  [+] claude")

    if not check_command('uv'):
        print("  [!] uv missing")
        ok = False
    else:
        print("  [+] uv")

    # 2. Directories
    print("\n[2/3] Directories...")
    for d in ['.specs', '.orchestrator/experts', 'ai_docs']:
        (project_root / d).mkdir(parents=True, exist_ok=True)
        print(f"  [+] {d}")

    # 3. Docs - auto-fetch missing
    print("\n[3/3] Documentation...")
    loader = DocsLoader(project_root)
    status = loader.get_status()

    print(f"  URLs: {status['total']}, Fresh: {status['fresh']}, Missing: {len(status['missing'])}")

    if status['missing']:
        print(f"\n  Fetching {len(status['missing'])} docs...")
        result = loader.refresh(status['missing'])
        print(f"  Done: {result['updated']} fetched, {result['failed']} failed")
        if result['failed']:
            ok = False

    print("\n" + "=" * 35)
    print("Setup complete!" if ok else "Setup completed with issues")
    return ok


if __name__ == '__main__':
    project_root = Path(__file__).parent.parent.resolve()
    success = run_setup(project_root)
    sys.exit(0 if success else 1)
