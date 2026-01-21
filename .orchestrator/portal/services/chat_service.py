"""
Chat Service for the Portal.

Handles chat message parsing, intent detection, and action routing.
"""
import asyncio
import logging
import re
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from core.knowledge_store import KnowledgeStore
from core.staleness_checker import StalenessChecker, get_staleness_summary
from db import get_knowledge_repository, get_plan_repository

logger = logging.getLogger(__name__)


class IntentType(Enum):
    """Types of intents detected from user messages."""
    QUERY_KNOWLEDGE = "query_knowledge"
    TRIGGER_SCOUT = "trigger_scout"
    CREATE_PLAN = "create_plan"
    SHOW_REPORT = "show_report"
    LIST_PLANS = "list_plans"
    SHOW_RULES = "show_rules"
    CHECK_STALENESS = "check_staleness"
    GENERAL = "general"


class Intent:
    """Detected intent from user message."""

    def __init__(self, intent_type: IntentType, query: str = "", target: str = "", report_type: str = ""):
        self.type = intent_type
        self.query = query
        self.target = target
        self.report_type = report_type


class ChatSession:
    """Represents a chat session with history."""

    def __init__(self, session_id: str, context: str = None):
        self.session_id = session_id
        self.context = context
        self.history: list[dict] = []
        self.created_at = datetime.now()

    def add_message(self, role: str, content: str):
        self.history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })

    def get_recent_history(self, max_messages: int = 10) -> list[dict]:
        return self.history[-max_messages:]


class ChatService:
    """
    Service for handling chat messages and routing actions.

    Parses user intent and routes to appropriate actions:
    - Query knowledge base
    - Trigger scout scans
    - Create plans
    - Show reports
    """

    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path(__file__).parent.parent.parent.parent
        self.sessions: dict[str, ChatSession] = {}
        self.knowledge_store = KnowledgeStore(self.project_root)
        self._knowledge_repo = get_knowledge_repository()
        self._plan_repo = get_plan_repository()

    def create_session(self, session_id: str, context: str = None) -> ChatSession:
        """Create a new chat session."""
        session = ChatSession(session_id, context)
        self.sessions[session_id] = session
        return session

    def has_session(self, session_id: str) -> bool:
        """Check if session exists."""
        return session_id in self.sessions

    def end_session(self, session_id: str):
        """End a chat session."""
        if session_id in self.sessions:
            del self.sessions[session_id]

    async def handle_message(self, message: str, session_id: str) -> dict:
        """
        Handle a chat message and return a response.

        Args:
            message: User's message
            session_id: Session ID

        Returns:
            Dictionary with response, action, and optional data
        """
        # Get or create session
        session = self.sessions.get(session_id)
        if not session:
            session = self.create_session(session_id)

        # Add user message to history
        session.add_message("user", message)

        # Parse intent
        intent = self.parse_intent(message)

        # Route to appropriate handler
        try:
            result = await self._route_intent(intent, session)

            # Add assistant message to history
            session.add_message("assistant", result.get("response", ""))

            return result
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            error_response = f"I encountered an error: {str(e)}"
            session.add_message("assistant", error_response)
            return {"response": error_response, "action": None, "data": None}

    def parse_intent(self, message: str) -> Intent:
        """
        Parse user message to determine intent.

        Args:
            message: User's message

        Returns:
            Intent object with type and parameters
        """
        message_lower = message.lower().strip()

        # Check for scout/scan triggers
        scout_patterns = [
            r"^scan\s*(.*)?$",
            r"^scout\s*(.*)?$",
            r"^run scout\s*(.*)?$",
            r"^analyze\s*(.*)?$",
            r"^refresh knowledge\s*(.*)?$",
        ]
        for pattern in scout_patterns:
            match = re.match(pattern, message_lower)
            if match:
                target = match.group(1).strip() if match.group(1) else ""
                return Intent(IntentType.TRIGGER_SCOUT, target=target)

        # Check for plan creation triggers
        plan_patterns = [
            r"^(create|make|generate)\s+(a\s+)?plan\s+(for\s+)?(.+)$",
            r"^plan\s+(.+)$",
            r"^i want to\s+(.+)$",
            r"^implement\s+(.+)$",
            r"^add\s+(.+)$",
        ]
        for pattern in plan_patterns:
            match = re.match(pattern, message_lower)
            if match:
                # Get the description part
                groups = match.groups()
                description = groups[-1] if groups[-1] else message
                return Intent(IntentType.CREATE_PLAN, query=description)

        # Check for knowledge queries
        knowledge_patterns = [
            r"^what\s+(technologies?|tech|stack|frameworks?|languages?|tools?)\s*(are|is|do|does)?\s*(used|using)?",
            r"^(show|list|get|display)\s+(tech|technologies?|stack|frameworks?|tools?|languages?)",
            r"^tech\s*stack",
            r"^stack\s*(info)?",
        ]
        for pattern in knowledge_patterns:
            if re.match(pattern, message_lower):
                return Intent(IntentType.QUERY_KNOWLEDGE, query="tech_stack")

        # Check for domains query
        if re.match(r"^(what|show|list)\s*(are\s+)?(the\s+)?domains?", message_lower):
            return Intent(IntentType.QUERY_KNOWLEDGE, query="domains")

        # Check for architecture query
        if re.match(r"^(what|show|describe)\s*(is\s+)?(the\s+)?architecture", message_lower):
            return Intent(IntentType.QUERY_KNOWLEDGE, query="architecture")

        # Check for coding rules
        if re.match(r"^(show|list|what\s+are)\s*(the\s+)?(coding\s+)?rules?", message_lower):
            return Intent(IntentType.SHOW_RULES)

        # Check for staleness check
        staleness_patterns = [
            r"^(is\s+)?(knowledge\s+)?(stale|outdated|current|up.?to.?date)",
            r"^check\s+(staleness|freshness)",
            r"^(when\s+was\s+)?last\s+scan",
        ]
        for pattern in staleness_patterns:
            if re.match(pattern, message_lower):
                return Intent(IntentType.CHECK_STALENESS)

        # Check for plans list
        if re.match(r"^(show|list|get)\s+(my\s+)?plans?", message_lower):
            return Intent(IntentType.LIST_PLANS)

        # Check for report types
        report_patterns = [
            (r"^(show|get|display)\s+(knowledge\s+)?report", "knowledge"),
            (r"^(show|get|display)\s+summary", "summary"),
            (r"^overview", "summary"),
        ]
        for pattern, report_type in report_patterns:
            if re.match(pattern, message_lower):
                return Intent(IntentType.SHOW_REPORT, report_type=report_type)

        # Default to general query with knowledge context
        return Intent(IntentType.GENERAL, query=message)

    async def _route_intent(self, intent: Intent, session: ChatSession) -> dict:
        """Route intent to appropriate handler."""
        handlers = {
            IntentType.QUERY_KNOWLEDGE: self._handle_query_knowledge,
            IntentType.TRIGGER_SCOUT: self._handle_trigger_scout,
            IntentType.CREATE_PLAN: self._handle_create_plan,
            IntentType.SHOW_REPORT: self._handle_show_report,
            IntentType.LIST_PLANS: self._handle_list_plans,
            IntentType.SHOW_RULES: self._handle_show_rules,
            IntentType.CHECK_STALENESS: self._handle_check_staleness,
            IntentType.GENERAL: self._handle_general,
        }

        handler = handlers.get(intent.type, self._handle_general)
        return await handler(intent, session)

    async def _handle_query_knowledge(self, intent: Intent, session: ChatSession) -> dict:
        """Handle knowledge queries."""
        knowledge = self.knowledge_store.load()

        if not knowledge:
            return {
                "response": "No knowledge available. Would you like me to run a scan? Just say 'scan' or 'scout'.",
                "action": None,
                "data": None
            }

        query = intent.query

        if query == "tech_stack":
            # Build tech stack response
            languages = [t.name for t in knowledge.technologies.languages]
            frameworks = [t.name for t in knowledge.technologies.frameworks]
            tools = [t.name for t in knowledge.technologies.tools]

            response = f"**Technology Stack for {knowledge.project.name}**\n\n"
            if languages:
                response += f"**Languages:** {', '.join(languages)}\n"
            if frameworks:
                response += f"**Frameworks:** {', '.join(frameworks)}\n"
            if tools:
                response += f"**Tools:** {', '.join(tools)}\n"

            return {
                "response": response,
                "action": "query_knowledge",
                "data": {
                    "languages": languages,
                    "frameworks": frameworks,
                    "tools": tools
                }
            }

        elif query == "domains":
            domains = knowledge.domains
            if not domains:
                return {"response": "No domains identified yet.", "action": None, "data": None}

            response = f"**Domains in {knowledge.project.name}**\n\n"
            for domain in domains:
                response += f"- **{domain.name}**: {', '.join(domain.keywords[:5])}\n"

            return {
                "response": response,
                "action": "query_knowledge",
                "data": {"domains": [d.name for d in domains]}
            }

        elif query == "architecture":
            arch = knowledge.architecture
            response = f"**Architecture: {arch.pattern}**\n\n"

            if arch.modules:
                response += "**Modules:**\n"
                for module in arch.modules[:10]:
                    response += f"- **{module.name}** ({module.path}): {module.purpose}\n"

            if arch.entry_points:
                response += f"\n**Entry Points:** {', '.join(arch.entry_points)}\n"

            return {
                "response": response,
                "action": "query_knowledge",
                "data": {"pattern": arch.pattern, "modules": len(arch.modules)}
            }

        return {
            "response": "I couldn't understand that query. Try asking about 'tech stack', 'domains', or 'architecture'.",
            "action": None,
            "data": None
        }

    async def _handle_trigger_scout(self, intent: Intent, session: ChatSession) -> dict:
        """Handle scout/scan triggers."""
        target = intent.target

        response = "Starting scan"
        if target:
            response += f" for: {target}"
        response += "...\n\n"

        # Run scout asynchronously
        try:
            from workflows.unified_scout import UnifiedScoutWorkflow

            workflow = UnifiedScoutWorkflow(self.project_root)
            target_paths = [target] if target else None
            result = await asyncio.to_thread(
                workflow.run,
                target_paths=target_paths,
                trigger="chat"
            )

            if result.success:
                data = result.data or {}
                response += f"Scan completed!\n"
                response += f"- Mode: {data.get('mode', 'unknown')}\n"
                response += f"- Files scanned: {data.get('files_scanned', 'N/A')}\n"
                response += f"- Domains found: {data.get('domains', 0)}\n"
                response += f"- Coding rules: {data.get('coding_rules', 0)}\n"

                return {
                    "response": response,
                    "action": "trigger_scout",
                    "data": data
                }
            else:
                return {
                    "response": f"Scan failed: {result.error}",
                    "action": "trigger_scout",
                    "data": {"success": False, "error": result.error}
                }
        except Exception as e:
            logger.error(f"Error running scout: {e}")
            return {
                "response": f"Error running scan: {str(e)}",
                "action": "trigger_scout",
                "data": {"success": False, "error": str(e)}
            }

    async def _handle_create_plan(self, intent: Intent, session: ChatSession) -> dict:
        """Handle plan creation requests."""
        description = intent.query

        response = f"I'll create a plan for: **{description}**\n\n"
        response += "Starting planning workflow...\n"

        try:
            from workflows.planning import PlanningWorkflow

            workflow = PlanningWorkflow(self.project_root, auto_scout_on_stale=True)
            result = await asyncio.to_thread(workflow.run, description)

            if result.success:
                plan_id = result.data.get("plan_id") if result.data else "unknown"
                response += f"\nPlan created successfully!\n"
                response += f"- Plan ID: **{plan_id}**\n"
                response += f"\nYou can view and execute this plan from the Plans page."

                return {
                    "response": response,
                    "action": "create_plan",
                    "data": {"plan_id": plan_id, "success": True}
                }
            else:
                return {
                    "response": f"Failed to create plan: {result.error}",
                    "action": "create_plan",
                    "data": {"success": False, "error": result.error}
                }
        except Exception as e:
            logger.error(f"Error creating plan: {e}")
            return {
                "response": f"Error creating plan: {str(e)}",
                "action": "create_plan",
                "data": {"success": False, "error": str(e)}
            }

    async def _handle_show_report(self, intent: Intent, session: ChatSession) -> dict:
        """Handle report display requests."""
        report_type = intent.report_type

        knowledge = self.knowledge_store.load()
        if not knowledge:
            return {
                "response": "No knowledge available. Run a scan first with 'scout' or 'scan'.",
                "action": None,
                "data": None
            }

        if report_type == "summary":
            response = f"**Project Summary: {knowledge.project.name}**\n\n"
            response += f"- **Type:** {knowledge.project.type}\n"
            response += f"- **Primary Language:** {knowledge.project.primary_language}\n"
            response += f"- **Architecture:** {knowledge.architecture.pattern}\n"
            response += f"- **Domains:** {len(knowledge.domains)}\n"
            response += f"- **Modules:** {len(knowledge.architecture.modules)}\n"
            response += f"- **Coding Rules:** {len(knowledge.coding_rules)}\n"
            response += f"- **Last Updated:** {knowledge.last_updated}\n"

            return {
                "response": response,
                "action": "show_report",
                "data": {"type": "summary"}
            }

        return {"response": "Unknown report type.", "action": None, "data": None}

    async def _handle_list_plans(self, intent: Intent, session: ChatSession) -> dict:
        """Handle plan listing requests."""
        plans = self._plan_repo.get_recent_plans(limit=10)

        if not plans:
            return {
                "response": "No plans found. Create one with 'plan [description]'.",
                "action": "list_plans",
                "data": {"plans": []}
            }

        response = "**Recent Plans:**\n\n"
        for plan in plans:
            status = plan.get('status', 'unknown')
            goal = plan.get('goal', 'No description')[:50]
            response += f"- **{plan.get('plan_id')}** [{status}]: {goal}...\n"

        return {
            "response": response,
            "action": "list_plans",
            "data": {"plans": [p.get('plan_id') for p in plans]}
        }

    async def _handle_show_rules(self, intent: Intent, session: ChatSession) -> dict:
        """Handle coding rules display."""
        rules = self._knowledge_repo.get_coding_rules()

        if not rules:
            return {
                "response": "No coding rules found. Run a scan to extract rules from the codebase.",
                "action": "show_rules",
                "data": {"rules": []}
            }

        response = "**Coding Rules:**\n\n"

        # Group by category
        by_category = {}
        for rule in rules:
            cat = rule.get('category', 'general')
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(rule)

        for category, cat_rules in by_category.items():
            response += f"**{category.title()}:**\n"
            for rule in cat_rules[:5]:  # Limit per category
                severity = rule.get('severity', 'info')
                response += f"  - [{severity}] {rule.get('rule', '')}\n"
            response += "\n"

        return {
            "response": response,
            "action": "show_rules",
            "data": {"rules_count": len(rules), "categories": list(by_category.keys())}
        }

    async def _handle_check_staleness(self, intent: Intent, session: ChatSession) -> dict:
        """Handle staleness check requests."""
        summary = get_staleness_summary(self.project_root)

        if not summary.get("has_knowledge"):
            return {
                "response": "No knowledge exists yet. Run 'scout' to create initial knowledge.",
                "action": "check_staleness",
                "data": summary
            }

        is_stale = summary.get("is_stale", True)
        reason = summary.get("reason", "Unknown")

        if is_stale:
            response = f"Knowledge is **stale**: {reason}\n\n"
            response += "Run 'scout' to refresh the knowledge base."
        else:
            response = f"Knowledge is **current**: {reason}\n\n"
            if summary.get("last_scan_time"):
                response += f"Last scanned: {summary.get('last_scan_time')}"

        return {
            "response": response,
            "action": "check_staleness",
            "data": summary
        }

    async def _handle_general(self, intent: Intent, session: ChatSession) -> dict:
        """Handle general queries with knowledge context."""
        message = intent.query

        # Provide helpful response based on what's available
        knowledge = self.knowledge_store.load()

        response = "I can help you with:\n\n"
        response += "- **Scan the codebase**: Say 'scan' or 'scout'\n"
        response += "- **View tech stack**: Say 'what technologies are used?'\n"
        response += "- **See domains**: Say 'show domains'\n"
        response += "- **Create a plan**: Say 'plan [description]' or 'I want to [feature]'\n"
        response += "- **List plans**: Say 'show plans'\n"
        response += "- **Check staleness**: Say 'is knowledge stale?'\n"
        response += "- **View coding rules**: Say 'show rules'\n"

        if knowledge:
            response += f"\n\nCurrent project: **{knowledge.project.name}** ({knowledge.project.type})"

        return {
            "response": response,
            "action": "general",
            "data": None
        }


# Dependency injection
_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """Get or create the chat service singleton."""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service
