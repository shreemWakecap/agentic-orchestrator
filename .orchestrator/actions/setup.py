"""Setup action - initialize orchestrator environment."""
import shutil
from pathlib import Path

ORCHESTRATOR_DIR = Path(__file__).parent.parent
PROJECT_ROOT = ORCHESTRATOR_DIR.parent


def run(args=None) -> int:
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

    # Create directories
    for d in ['specs/pending', 'specs/completed', 'specs/failed', 'agents/experts', 'config']:
        (ORCHESTRATOR_DIR / d).mkdir(parents=True, exist_ok=True)
    print("  [+] Directories created")

    print("\n" + ("Setup complete!" if ok else "Setup completed with issues"))
    return 0 if ok else 1
