"""List action - show all plans."""
from pathlib import Path

ORCHESTRATOR_DIR = Path(__file__).parent.parent
SPECS_DIR = ORCHESTRATOR_DIR / "specs"


def run(args=None) -> int:
    """List all plans by status."""
    print("Plans\n" + "=" * 40)

    for status in ["pending", "completed", "failed"]:
        status_dir = SPECS_DIR / status
        if not status_dir.exists():
            continue

        plans = [p for p in status_dir.iterdir() if p.is_dir() or p.suffix == ".md"]
        if plans:
            print(f"\n{status.upper()} ({len(plans)})")
            for p in sorted(plans, key=lambda x: x.name):
                print(f"  {p.name}")

    return 0
