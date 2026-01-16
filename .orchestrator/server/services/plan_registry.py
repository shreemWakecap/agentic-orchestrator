"""PlanRegistry implementation providing plan management operations.

This module implements the IPlanRegistry interface, providing concrete implementations
for listing, retrieving, and updating plan states. It uses the FileService for
all file system operations.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from .interfaces import IPlanRegistry, IFileService, Plan, PlanState


class PlanRegistryService(IPlanRegistry):
    """Concrete implementation of IPlanRegistry for plan management operations.

    This service provides plan management for the orchestrator server, including:
    - Listing all plans across all states (pending, in-progress, completed, failed)
    - Retrieving individual plans with full content
    - Updating plan states by moving them between directories

    Attributes:
        file_service: The IFileService instance for file system operations
    """

    def __init__(self, file_service: IFileService):
        """Initialize PlanRegistryService with a file service.

        Args:
            file_service: The IFileService instance to use for file operations.
        """
        self.file_service = file_service

    def list_plans(self) -> List[Plan]:
        """List all plans across all states.

        Iterates through pending, in-progress, completed, and failed directories,
        parses plan.md files to extract plan info, and returns a list of Plan objects
        sorted by numeric prefix (e.g., 001_, 002_).

        Returns:
            List of Plan objects sorted by numeric prefix.
        """
        plans: List[Plan] = []

        # Iterate through all state directories
        for state in [PlanState.PENDING, PlanState.IN_PROGRESS, PlanState.COMPLETED, PlanState.FAILED]:
            state_plans = self._list_plans_in_state(state)
            plans.extend(state_plans)

        # Sort by numeric prefix (001_, 002_, etc.)
        return sorted(plans, key=lambda p: self._extract_plan_number(p.id))

    def _list_plans_in_state(self, state: PlanState) -> List[Plan]:
        """List all plans in a specific state directory.

        Args:
            state: The PlanState to list plans from

        Returns:
            List of Plan objects in the specified state
        """
        plans: List[Plan] = []

        # Get all plan directories for this state
        plan_dirs = self.file_service.list_plan_dirs(state)

        for plan_dir in plan_dirs:
            plan = self._load_plan_from_dir(plan_dir, state)
            if plan is not None:
                plans.append(plan)

        return plans

    def _load_plan_from_dir(self, plan_dir: Path, state: PlanState) -> Optional[Plan]:
        """Load plan data from a plan directory.

        Args:
            plan_dir: Path to the plan directory
            state: The PlanState the plan is in

        Returns:
            Plan object if successfully loaded, None otherwise
        """
        plan_id = plan_dir.name

        # Get list of files in the plan directory (excluding hidden files)
        files = self.file_service.list_files(str(plan_dir))

        # Get modification time
        modified = self.file_service.get_modification_time(str(plan_dir))
        if modified is None:
            modified = datetime.now().isoformat()

        # Default name from plan ID (converted to title case)
        default_name = plan_id.replace("-", " ").replace("_", " ").title()

        # Extract info from plan.md headers
        plan_info = self._extract_plan_info(plan_dir)

        # Build Plan object
        plan = Plan(
            id=plan_id,
            name=plan_info.get("name", default_name),
            state=state,
            file=str(plan_dir),
            files=files,
            modified=modified,
            content=None,  # Content not loaded for list_plans
            request=plan_info.get("request"),
            complexity=plan_info.get("complexity"),
        )

        return plan

    def _extract_plan_info(self, plan_dir: Path) -> Dict[str, str]:
        """Extract plan info (name, request, complexity) from plan.md headers.

        Reads the plan.md file in the plan directory and extracts metadata
        from header lines in the format:
        - # Plan: <name>
        - Request: <request text>
        - Complexity: <low|medium|high>

        Args:
            plan_dir: Path to the plan directory

        Returns:
            Dictionary with extracted info: name, request, complexity (if present)
        """
        info: Dict[str, str] = {}
        plan_file = plan_dir / "plan.md"

        if not plan_file.exists():
            return info

        try:
            content = self.file_service.read_file(str(plan_file))
            lines = content.split("\n")[:10]  # Only check first 10 lines

            for line in lines:
                line = line.strip()
                # Extract title from "# Plan: XXX"
                if line.startswith("# Plan:"):
                    info["name"] = line[7:].strip()
                # Extract request from "Request: XXX"
                elif line.startswith("Request:"):
                    info["request"] = line[8:].strip()
                # Extract complexity from "Complexity: XXX"
                elif line.startswith("Complexity:"):
                    info["complexity"] = line[11:].strip()
        except (IOError, FileNotFoundError):
            pass

        return info

    def _extract_plan_number(self, plan_id: str) -> int:
        """Extract numeric prefix from plan ID (e.g., '001_feature' -> 1).

        Args:
            plan_id: The plan identifier

        Returns:
            The numeric prefix as an integer, or 999999 if no valid prefix found
        """
        try:
            prefix = plan_id.split('_')[0]
            return int(prefix)
        except (ValueError, IndexError):
            return 999999  # Sort plans without numeric prefix at the end

    def get_plan(self, plan_id: str) -> Optional[Plan]:
        """Get a specific plan by its ID with full content loaded.

        Searches through all state directories to find the plan, then loads
        the full content from plan.md (or 00_overview.md as fallback).

        Args:
            plan_id: The unique identifier of the plan (e.g., '001_feature-name')

        Returns:
            The Plan object with content loaded if found, None otherwise.
        """
        # Find the plan directory
        plan_dir = self.file_service.get_plan_dir(plan_id)
        if plan_dir is None:
            return None

        # Determine the state from the directory location
        state = self.file_service.get_plan_state(plan_id)
        if state is None:
            return None

        # Get list of files in the plan directory
        files = self.file_service.list_files(str(plan_dir))

        # Get modification time
        modified = self.file_service.get_modification_time(str(plan_dir))
        if modified is None:
            modified = datetime.now().isoformat()

        # Default name from plan ID
        default_name = plan_id.replace("-", " ").replace("_", " ").title()

        # Extract info from plan.md headers
        plan_info = self._extract_plan_info(plan_dir)

        # Load content from plan.md or fallback files
        content = self._load_plan_content(plan_dir)

        # Build Plan object with full content
        plan = Plan(
            id=plan_id,
            name=plan_info.get("name", default_name),
            state=state,
            file=str(plan_dir),
            files=files,
            modified=modified,
            content=content,
            request=plan_info.get("request"),
            complexity=plan_info.get("complexity"),
        )

        return plan

    def _load_plan_content(self, plan_dir: Path) -> str:
        """Load the content of a plan from its directory.

        Tries to load content in the following order:
        1. plan.md - the main plan file
        2. 00_overview.md - overview file
        3. Concatenation of all .md files in sorted order

        Args:
            plan_dir: Path to the plan directory

        Returns:
            The plan content as a string, or empty string if no content found
        """
        # Try plan.md first
        plan_file = plan_dir / "plan.md"
        if plan_file.exists():
            try:
                return self.file_service.read_file(str(plan_file))
            except (IOError, FileNotFoundError):
                pass

        # Try 00_overview.md
        overview_file = plan_dir / "00_overview.md"
        if overview_file.exists():
            try:
                return self.file_service.read_file(str(overview_file))
            except (IOError, FileNotFoundError):
                pass

        # Fallback: concatenate all .md files
        content_parts: List[str] = []
        for md_file in sorted(plan_dir.glob("*.md")):
            try:
                file_content = self.file_service.read_file(str(md_file))
                content_parts.append(f"# {md_file.stem}\n\n{file_content}\n\n")
            except (IOError, FileNotFoundError):
                continue

        return "".join(content_parts) if content_parts else ""

    def update_status(self, plan_id: str, status: PlanState) -> bool:
        """Update the state of a plan by moving it to the appropriate directory.

        This method changes a plan's state by:
        1. Moving the entire plan directory from its current state directory
           to the new state directory (e.g., pending/ -> in-progress/)
        2. Updating the plan's state file with the new status and timestamp

        The directory move is performed atomically using shutil.move via FileService.
        State file updates include the previous state for audit trail.

        Args:
            plan_id: The unique identifier of the plan
            status: The new state to set for the plan

        Returns:
            True if the status was successfully updated, False otherwise
            (e.g., if the plan was not found or the move failed).
        """
        # Find the current plan directory
        current_dir = self.file_service.get_plan_dir(plan_id)
        if current_dir is None:
            return False

        # Get current state for audit trail
        current_state = self.file_service.get_plan_state(plan_id)

        # Get the target state directory
        target_state_dir = self.file_service.get_state_dir_path(status)
        target_dir = target_state_dir / plan_id

        # If already in the target directory, just update state file
        if current_dir == target_dir:
            self._update_state_file(plan_id, status, current_state)
            return True

        # Move the plan directory to the new state directory
        move_success = self.file_service.move_file(str(current_dir), str(target_dir))

        if move_success:
            # Update the state file with new status and timestamp
            self._update_state_file(plan_id, status, current_state)

        return move_success

    def _update_state_file(self, plan_id: str, new_status: PlanState, previous_status: Optional[PlanState] = None) -> bool:
        """Update a plan's state file with new status information.

        Reads the existing state file (if any), updates it with the new status,
        and writes it back. Creates a new state file if one doesn't exist.

        Args:
            plan_id: The unique identifier of the plan
            new_status: The new PlanState to record
            previous_status: The previous PlanState (for audit trail)

        Returns:
            True if state file was successfully updated, False otherwise
        """
        # Read existing state data or create new
        state_data = self.file_service.read_state_file(plan_id)
        if state_data is None:
            state_data = {
                "plan_id": plan_id,
                "created_at": datetime.now().isoformat(),
                "status_history": []
            }

        # Update current status
        state_data["status"] = new_status.value
        state_data["updated_at"] = datetime.now().isoformat()

        # Add to status history for audit trail
        history_entry = {
            "status": new_status.value,
            "timestamp": datetime.now().isoformat()
        }
        if previous_status is not None:
            history_entry["previous_status"] = previous_status.value

        if "status_history" not in state_data:
            state_data["status_history"] = []
        state_data["status_history"].append(history_entry)

        # Write updated state file
        return self.file_service.write_state_file(plan_id, state_data)
