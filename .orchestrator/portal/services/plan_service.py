"""Plan service for business logic related to plans."""
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from db import PlanRepository
from db.repositories.build_state import BuildStateRepository


# Plans are considered stuck if no update in this many minutes
STUCK_THRESHOLD_MINUTES = 5


class PlanService:
    """Service for plan-related business logic.

    Encapsulates plan data transformation and enrichment logic
    that was previously scattered across route handlers.
    """

    def __init__(self, plan_repo: PlanRepository, build_state_repo: BuildStateRepository = None):
        self.plan_repo = plan_repo
        self.build_state_repo = build_state_repo

    async def get_all_plans(self) -> List[Dict]:
        """Get all plans from database, sorted by created_at DESC."""
        db_plans = self.plan_repo.list_all()
        plans = []

        for db_plan in db_plans:
            plan_data = self._build_plan_data(db_plan)
            plans.append(plan_data)

        return plans

    async def get_plan_by_id(self, plan_id: str) -> Optional[Dict]:
        """Get a specific plan by ID from database."""
        db_plan = self.plan_repo.get_by_id(plan_id)

        if not db_plan:
            return None

        return self._build_plan_data(db_plan, include_content=True)

    def _build_plan_data(self, db_plan: Dict, include_content: bool = False) -> Dict:
        """Build plan data dict from database record.

        This consolidates the duplicated plan data construction logic
        that was previously in both _get_all_plans() and _get_plan_by_id().
        """
        plan_id = db_plan.get("plan_id", "")
        raw_content = db_plan.get("raw_content", "")
        status = db_plan.get("status") or "pending"

        plan_data = {
            "id": plan_id,
            "name": plan_id.replace("-", " ").replace("_", " ").title(),
            "state": status,
            "files": ["plan.md"],
            "created": db_plan.get("created_at") or "",
            "modified": db_plan.get("updated_at") or db_plan.get("created_at") or "",
            "request": db_plan.get("request") or "",
            "goal": db_plan.get("goal") or "",
            "is_stuck": False,
            "last_update": None,
            "recovery_options": [],
        }

        # Calculate stuck status and recovery options from build state
        if self.build_state_repo:
            build_state = self.build_state_repo.get(plan_id)
            if build_state:
                plan_data["last_update"] = build_state.get("updated_at")
                build_status = build_state.get("status", "")

                # Check if plan is stuck
                is_stuck = self._is_plan_stuck(build_status, build_state.get("updated_at"))
                plan_data["is_stuck"] = is_stuck

                # Calculate recovery options based on state
                plan_data["recovery_options"] = self._get_recovery_options(
                    status, build_status, is_stuck, build_state
                )

        if include_content:
            plan_data["content"] = raw_content

        # Extract info from raw content headers
        plan_info = self._extract_plan_info_from_content(raw_content)
        if plan_info.get("name"):
            plan_data["name"] = plan_info["name"]
        if plan_info.get("request"):
            plan_data["request"] = plan_info["request"]
        if plan_info.get("complexity"):
            plan_data["complexity"] = plan_info["complexity"]

        return plan_data

    def _is_plan_stuck(self, build_status: str, updated_at: Optional[str]) -> bool:
        """Check if a plan is stuck based on status and last update time."""
        # Only building/in_progress states can be stuck
        stuck_statuses = {"building", "in_progress", "running"}
        if build_status.lower() not in stuck_statuses:
            return False

        if not updated_at:
            return False

        try:
            last_update = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            threshold = datetime.now(last_update.tzinfo) if last_update.tzinfo else datetime.now()
            threshold = threshold - timedelta(minutes=STUCK_THRESHOLD_MINUTES)
            return last_update < threshold
        except (ValueError, TypeError):
            return False

    def _get_recovery_options(self, plan_status: str, build_status: str,
                               is_stuck: bool, build_state: Dict) -> List[str]:
        """Determine available recovery options for a plan."""
        options = []

        # If stuck, offer reset and resume
        if is_stuck:
            options.append("reset")
            options.append("resume")

        # If there are failed steps, offer retry and skip
        failed_steps = build_state.get("failed_steps", [])
        if failed_steps:
            options.append("retry_step")
            options.append("skip_step")

        # If build exists but is not complete, offer reset
        if build_status and build_status not in ("completed", "pending"):
            if "reset" not in options:
                options.append("reset")

        # If there's a last error, always offer reset
        if build_state.get("last_error"):
            if "reset" not in options:
                options.append("reset")
            if "resume" not in options:
                options.append("resume")

        return options

    @staticmethod
    def _extract_plan_number(plan_id: str) -> int:
        """Extract numeric prefix from plan ID (e.g., '001_feature' -> 1)."""
        try:
            prefix = plan_id.split("_")[0]
            return int(prefix)
        except (ValueError, IndexError):
            return 999999  # Sort plans without numeric prefix at the end

    @staticmethod
    def _extract_plan_info_from_content(content: str) -> Dict[str, str]:
        """Extract plan info (name, request, complexity) from plan content headers."""
        info = {}
        if not content:
            return info

        try:
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
        except Exception:
            pass

        return info
