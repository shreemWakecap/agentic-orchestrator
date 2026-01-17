"""Simple CLI commands - utilities that don't require workflow orchestration."""
import shutil
import socket
from pathlib import Path

ORCHESTRATOR_DIR = Path(__file__).parent
SPECS_DIR = ORCHESTRATOR_DIR / "specs"


def list_plans(args=None) -> int:
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

    # Create directories
    for d in ['specs/pending', 'specs/completed', 'specs/failed', 'agents/experts', 'config']:
        (ORCHESTRATOR_DIR / d).mkdir(parents=True, exist_ok=True)
    print("  [+] Directories created")

    print("\n" + ("Setup complete!" if ok else "Setup completed with issues"))
    return 0 if ok else 1
