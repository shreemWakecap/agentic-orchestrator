"""FileService implementation providing file system operations for the orchestrator.

This module implements the IFileService interface, providing concrete implementations
for reading, writing, and moving files, as well as plan-specific path resolution
and directory operations.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from .interfaces import IFileService, PlanState


class FileService(IFileService):
    """Concrete implementation of IFileService for file system operations.

    This service provides file operations for the orchestrator server, including:
    - Basic file read/write/move operations
    - Plan-specific path resolution (plan directories, state files)
    - Directory listing and existence checks
    - State file management

    Attributes:
        base_dir: The base directory for file operations (typically ORCHESTRATOR_DIR)
        specs_dir: The specs directory containing plan folders
        state_dir: The state directory containing plan state files
    """

    # Mapping from PlanState enum to directory names
    # Note: "in-progress" uses hyphen in directory name
    STATE_DIR_NAMES = {
        PlanState.PENDING: "pending",
        PlanState.IN_PROGRESS: "in-progress",  # hyphenated directory name
        PlanState.COMPLETED: "completed",
        PlanState.FAILED: "failed",
    }

    # All state directory names for iteration
    ALL_STATE_DIRS = ["pending", "in-progress", "completed", "failed"]

    def __init__(self, base_dir: Path):
        """Initialize FileService with base directory.

        Args:
            base_dir: The base directory for operations (ORCHESTRATOR_DIR).
                      All relative paths are resolved against this directory.
        """
        self.base_dir = Path(base_dir)
        self.specs_dir = self.base_dir / "specs"
        self.state_dir = self.specs_dir / "state"

    # ============== Plan Path Resolution Methods ==============

    def get_plan_dir(self, plan_id: str, state: Optional[PlanState] = None) -> Optional[Path]:
        """Get the directory path for a plan by ID.

        Searches through state directories to find the plan. If state is provided,
        only checks that specific state directory.

        Args:
            plan_id: The unique identifier of the plan (e.g., '001_feature-name')
            state: Optional state to limit search to a specific directory

        Returns:
            Path to the plan directory if found, None otherwise.
        """
        if state is not None:
            # Check specific state directory
            state_dir_name = self.STATE_DIR_NAMES.get(state)
            if state_dir_name:
                plan_dir = self.specs_dir / state_dir_name / plan_id
                if plan_dir.exists() and plan_dir.is_dir():
                    return plan_dir
            return None

        # Search all state directories
        for state_dir_name in self.ALL_STATE_DIRS:
            plan_dir = self.specs_dir / state_dir_name / plan_id
            if plan_dir.exists() and plan_dir.is_dir():
                return plan_dir

        return None

    def get_state_file_path(self, plan_id: str) -> Path:
        """Get the path to a plan's state file.

        State files are stored in specs/state/ directory with .state.json extension.

        Args:
            plan_id: The unique identifier of the plan

        Returns:
            Path to the state file (may not exist yet)
        """
        return self.state_dir / f"{plan_id}.state.json"

    def list_plan_dirs(self, state: Optional[PlanState] = None) -> List[Path]:
        """List all plan directories, optionally filtered by state.

        Args:
            state: Optional state to filter plans. If None, returns all plans.

        Returns:
            List of Path objects for each plan directory, sorted by name.
        """
        plan_dirs = []

        if state is not None:
            # List from specific state directory
            state_dir_name = self.STATE_DIR_NAMES.get(state)
            if state_dir_name:
                state_path = self.specs_dir / state_dir_name
                if state_path.exists():
                    plan_dirs.extend(self._list_dirs_in(state_path))
        else:
            # List from all state directories
            for state_dir_name in self.ALL_STATE_DIRS:
                state_path = self.specs_dir / state_dir_name
                if state_path.exists():
                    plan_dirs.extend(self._list_dirs_in(state_path))

        return sorted(plan_dirs, key=lambda p: p.name)

    def _list_dirs_in(self, directory: Path) -> List[Path]:
        """List subdirectories in a directory, excluding hidden ones.

        Args:
            directory: The directory to list

        Returns:
            List of Path objects for each subdirectory
        """
        if not directory.exists():
            return []
        return [
            d for d in directory.iterdir()
            if d.is_dir() and not d.name.startswith('.')
        ]

    def get_state_dir_for_plan(self, plan_id: str) -> Optional[str]:
        """Determine which state directory a plan is in.

        Args:
            plan_id: The unique identifier of the plan

        Returns:
            The state directory name (e.g., 'pending', 'in-progress') if found,
            None if the plan doesn't exist.
        """
        for state_dir_name in self.ALL_STATE_DIRS:
            plan_dir = self.specs_dir / state_dir_name / plan_id
            if plan_dir.exists() and plan_dir.is_dir():
                return state_dir_name
        return None

    def get_plan_state(self, plan_id: str) -> Optional[PlanState]:
        """Get the current state of a plan based on its directory location.

        Args:
            plan_id: The unique identifier of the plan

        Returns:
            PlanState enum value if found, None if plan doesn't exist
        """
        state_dir_name = self.get_state_dir_for_plan(plan_id)
        if state_dir_name is None:
            return None

        # Map directory name back to PlanState
        for state, dir_name in self.STATE_DIR_NAMES.items():
            if dir_name == state_dir_name:
                return state
        return None

    # ============== State File Operations ==============

    def read_state_file(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Read and parse a plan's state file.

        Args:
            plan_id: The unique identifier of the plan

        Returns:
            Dictionary containing state data if file exists and is valid JSON,
            None if file doesn't exist or is invalid.
        """
        state_path = self.get_state_file_path(plan_id)
        if not state_path.exists():
            return None

        try:
            content = state_path.read_text(encoding="utf-8")
            return json.loads(content)
        except (json.JSONDecodeError, IOError):
            return None

    def write_state_file(self, plan_id: str, state_data: Dict[str, Any]) -> bool:
        """Write a plan's state file.

        Creates the state directory if it doesn't exist.

        Args:
            plan_id: The unique identifier of the plan
            state_data: Dictionary containing state data to write

        Returns:
            True if successfully written, False otherwise
        """
        state_path = self.get_state_file_path(plan_id)

        try:
            # Ensure state directory exists
            state_path.parent.mkdir(parents=True, exist_ok=True)

            # Write state file with pretty formatting
            content = json.dumps(state_data, indent=2)
            state_path.write_text(content, encoding="utf-8")
            return True
        except IOError:
            return False

    # ============== Directory Operations ==============

    def directory_exists(self, path: str) -> bool:
        """Check if a directory exists.

        Args:
            path: Path to check (absolute or relative to base_dir)

        Returns:
            True if path exists and is a directory, False otherwise
        """
        full_path = self._resolve_path(path)
        return full_path.exists() and full_path.is_dir()

    def file_exists(self, path: str) -> bool:
        """Check if a file exists.

        Args:
            path: Path to check (absolute or relative to base_dir)

        Returns:
            True if path exists and is a file, False otherwise
        """
        full_path = self._resolve_path(path)
        return full_path.exists() and full_path.is_file()

    def ensure_directory(self, path: str) -> bool:
        """Ensure a directory exists, creating it if necessary.

        Args:
            path: Path to the directory (absolute or relative to base_dir)

        Returns:
            True if directory exists or was created, False on failure
        """
        full_path = self._resolve_path(path)
        try:
            full_path.mkdir(parents=True, exist_ok=True)
            return True
        except (IOError, OSError):
            return False

    def list_files(self, path: str, pattern: str = "*") -> List[str]:
        """List files in a directory matching a pattern.

        Args:
            path: Directory path (absolute or relative to base_dir)
            pattern: Glob pattern to match files (default: "*")

        Returns:
            List of filenames matching the pattern
        """
        full_path = self._resolve_path(path)
        if not full_path.exists() or not full_path.is_dir():
            return []

        return sorted([
            f.name for f in full_path.glob(pattern)
            if f.is_file() and not f.name.startswith('.')
        ])

    def get_modification_time(self, path: str) -> Optional[str]:
        """Get the modification time of a file or directory.

        Args:
            path: Path to check (absolute or relative to base_dir)

        Returns:
            ISO format timestamp string if path exists, None otherwise
        """
        full_path = self._resolve_path(path)
        if not full_path.exists():
            return None

        try:
            mtime = full_path.stat().st_mtime
            return datetime.fromtimestamp(mtime).isoformat()
        except (IOError, OSError):
            return None

    # ============== IFileService Interface Implementation ==============

    def read_file(self, path: str) -> str:
        """Read the contents of a file.

        Args:
            path: Path to the file (absolute or relative to base_dir)

        Returns:
            The contents of the file as a string.

        Raises:
            FileNotFoundError: If the file does not exist.
            PermissionError: If the file cannot be read due to permissions.
            IOError: If an I/O error occurs during reading.
        """
        full_path = self._resolve_path(path)

        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        if not full_path.is_file():
            raise IOError(f"Path is not a file: {path}")

        return full_path.read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> bool:
        """Write content to a file.

        Creates the file if it doesn't exist, or overwrites it if it does.
        Also creates any necessary parent directories.

        Args:
            path: Path to the file (absolute or relative to base_dir)
            content: The content to write to the file.

        Returns:
            True if the file was successfully written, False otherwise.
        """
        full_path = self._resolve_path(path)

        try:
            # Ensure parent directory exists
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Write the file
            full_path.write_text(content, encoding="utf-8")
            return True
        except (IOError, OSError):
            return False

    def move_file(self, src: str, dest: str) -> bool:
        """Move a file or directory from source to destination.

        Creates any necessary parent directories for the destination.

        Args:
            src: Source path (absolute or relative to base_dir)
            dest: Destination path (absolute or relative to base_dir)

        Returns:
            True if successfully moved, False otherwise.
        """
        src_path = self._resolve_path(src)
        dest_path = self._resolve_path(dest)

        if not src_path.exists():
            return False

        try:
            # Ensure destination parent directory exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Move the file or directory
            shutil.move(str(src_path), str(dest_path))
            return True
        except (IOError, OSError, shutil.Error):
            return False

    # ============== Helper Methods ==============

    def _resolve_path(self, path: str) -> Path:
        """Resolve a path, making it absolute if relative.

        Args:
            path: Path string (absolute or relative)

        Returns:
            Absolute Path object
        """
        path_obj = Path(path)
        if path_obj.is_absolute():
            return path_obj
        return self.base_dir / path

    def get_specs_dir(self) -> Path:
        """Get the specs directory path.

        Returns:
            Path to the specs directory
        """
        return self.specs_dir

    def get_state_dir(self) -> Path:
        """Get the state directory path.

        Returns:
            Path to the state directory (specs/state/)
        """
        return self.state_dir

    def get_state_dir_path(self, state: PlanState) -> Path:
        """Get the directory path for a specific plan state.

        Args:
            state: The PlanState enum value

        Returns:
            Path to the state directory (e.g., specs/pending/, specs/in-progress/)
        """
        dir_name = self.STATE_DIR_NAMES.get(state, "pending")
        return self.specs_dir / dir_name
