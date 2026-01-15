"""
Scout result caching based on codebase state.

Caches scout results to avoid redundant codebase exploration.
Cache key: {codebase_hash}_{request_hash}
TTL: 4 hours
"""
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


class ScoutCache:
    """Cache scout results keyed by codebase hash."""

    TTL_HOURS = 4
    MAX_ENTRIES = 50

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.cache_dir = project_root / ".orchestrator" / "cache" / "scout"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _compute_codebase_hash(self) -> str:
        """
        Compute a hash representing the current codebase state.
        Based on directory structure and key config file contents.
        """
        hasher = hashlib.sha256()

        # Hash top-level directory structure
        try:
            for item in sorted(self.project_root.iterdir()):
                if item.name.startswith('.'):
                    continue
                hasher.update(f"{item.name}:{item.is_dir()}".encode())
                if item.is_file():
                    # Include file modification time
                    hasher.update(str(int(item.stat().st_mtime)).encode())
        except Exception:
            pass

        # Hash key config files (first 1KB)
        config_files = [
            "package.json",
            "pyproject.toml",
            "Cargo.toml",
            "go.mod",
            "requirements.txt",
        ]
        for cfg in config_files:
            cfg_path = self.project_root / cfg
            if cfg_path.exists():
                try:
                    hasher.update(cfg_path.read_bytes()[:1024])
                except Exception:
                    pass

        return hasher.hexdigest()[:12]

    def _compute_request_hash(self, request: str) -> str:
        """Hash the request string."""
        return hashlib.sha256(request.encode()).hexdigest()[:12]

    def _get_cache_path(self, request: str) -> Path:
        """Get the cache file path for a request."""
        codebase_hash = self._compute_codebase_hash()
        request_hash = self._compute_request_hash(request)
        key = f"{codebase_hash}_{request_hash}"
        return self.cache_dir / f"{key}.json"

    def get(self, request: str) -> Optional[str]:
        """
        Get cached scout result if fresh.

        Args:
            request: The user request string

        Returns:
            Cached scout content if valid, None otherwise
        """
        cache_path = self._get_cache_path(request)

        if not cache_path.exists():
            return None

        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            cached_at = datetime.fromisoformat(data["cached_at"])

            # Check TTL
            if datetime.now() - cached_at > timedelta(hours=self.TTL_HOURS):
                cache_path.unlink()
                return None

            return data["content"]
        except Exception:
            # Invalid cache file, remove it
            try:
                cache_path.unlink()
            except Exception:
                pass
            return None

    def set(self, request: str, content: str) -> None:
        """
        Cache scout result.

        Args:
            request: The user request string
            content: The scout result to cache
        """
        cache_path = self._get_cache_path(request)

        data = {
            "cached_at": datetime.now().isoformat(),
            "request": request[:200],  # Store truncated request for debugging
            "content": content,
        }

        try:
            cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass  # Cache write failure is not critical

        # Cleanup old entries if over limit
        self._cleanup_old_entries()

    def _cleanup_old_entries(self) -> None:
        """Remove oldest entries if cache exceeds MAX_ENTRIES."""
        try:
            cache_files = list(self.cache_dir.glob("*.json"))
            if len(cache_files) <= self.MAX_ENTRIES:
                return

            # Sort by modification time, oldest first
            cache_files.sort(key=lambda f: f.stat().st_mtime)

            # Remove oldest entries
            for f in cache_files[: len(cache_files) - self.MAX_ENTRIES]:
                try:
                    f.unlink()
                except Exception:
                    pass
        except Exception:
            pass

    def clear(self) -> None:
        """Clear all cache entries."""
        try:
            for f in self.cache_dir.glob("*.json"):
                f.unlink()
        except Exception:
            pass

    def count(self) -> int:
        """Get number of cache entries."""
        try:
            return len(list(self.cache_dir.glob("*.json")))
        except Exception:
            return 0

    def size_mb(self) -> float:
        """Get total cache size in MB."""
        try:
            total = sum(f.stat().st_size for f in self.cache_dir.glob("*.json"))
            return total / (1024 * 1024)
        except Exception:
            return 0.0

    def stats(self) -> dict:
        """Get cache statistics."""
        return {
            "entries": self.count(),
            "size_mb": round(self.size_mb(), 2),
            "ttl_hours": self.TTL_HOURS,
            "max_entries": self.MAX_ENTRIES,
            "cache_dir": str(self.cache_dir),
        }
