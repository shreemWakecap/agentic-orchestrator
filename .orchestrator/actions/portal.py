"""Portal action - start web UI."""
import socket
from pathlib import Path


def find_free_port() -> int:
    """Find a random available port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


def run(args=None) -> int:
    """Start web portal on random available port."""
    port = find_free_port()
    print(f"Portal: http://127.0.0.1:{port}")
    print("Press Ctrl+C to stop\n")

    try:
        from portal.app import run_portal
        run_portal(host="127.0.0.1", port=port)
    except ImportError:
        print("Install dependencies: uv pip install fastapi uvicorn jinja2")
        return 1
    except KeyboardInterrupt:
        print("\nStopped.")

    return 0
