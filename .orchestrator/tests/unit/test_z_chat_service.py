"""
Unit tests for ChatService.

Note: This module must be run AFTER other unit tests to avoid mock pollution.
We rename it with 'z_' prefix to ensure alphabetical ordering puts it last.
"""
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from contextlib import contextmanager

import pytest


# ============================================================================
# Lazy loading - defer mock setup until tests actually run
# ============================================================================

_mocks = None
_chat_module = None
_classes_loaded = False


def _get_mocks():
    """Get or create mocks (lazy initialization)."""
    global _mocks, _chat_module, _classes_loaded

    if _mocks is not None:
        return _mocks

    # Store originals for restoration
    modules_to_mock = [
        'portal.models.base', 'portal.models', 'portal.lifecycle',
        'db', 'core.knowledge_store', 'core.staleness_checker'
    ]

    # Mock the portal.models.base module to prevent database connection
    mock_base = MagicMock()
    mock_base.engine = MagicMock()
    mock_base.async_session_maker = MagicMock()
    mock_base.init_db = MagicMock()
    mock_base.close_db = MagicMock()
    mock_base.Base = MagicMock()
    sys.modules['portal.models.base'] = mock_base
    sys.modules['portal.models'] = MagicMock()

    # Mock lifecycle
    sys.modules['portal.lifecycle'] = MagicMock()

    # Mock db module
    mock_db = MagicMock()
    mock_db.get_knowledge_repository = MagicMock(return_value=MagicMock())
    mock_db.get_plan_repository = MagicMock(return_value=MagicMock())
    sys.modules['db'] = mock_db

    # Mock core modules
    mock_knowledge_store = MagicMock()
    mock_knowledge_store.KnowledgeStore = MagicMock()
    mock_knowledge_store.CodingRule = MagicMock()
    mock_knowledge_store.CodebaseKnowledge = MagicMock()
    sys.modules['core.knowledge_store'] = mock_knowledge_store

    mock_staleness = MagicMock()
    mock_staleness.StalenessChecker = MagicMock()
    mock_staleness.get_staleness_summary = MagicMock(return_value={"has_knowledge": False})
    sys.modules['core.staleness_checker'] = mock_staleness

    _mocks = {
        'db': mock_db,
        'knowledge_store': mock_knowledge_store,
        'staleness': mock_staleness,
    }

    # Load chat_service module
    import importlib.util
    orchestrator_dir = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(orchestrator_dir))

    spec = importlib.util.spec_from_file_location(
        "chat_service",
        orchestrator_dir / "portal" / "services" / "chat_service.py"
    )
    _chat_module = importlib.util.module_from_spec(spec)
    sys.modules['portal.services.chat_service'] = _chat_module
    spec.loader.exec_module(_chat_module)

    _classes_loaded = True

    return _mocks


def _get_classes():
    """Get chat service classes (lazy initialization)."""
    _get_mocks()  # Ensure mocks and module are loaded
    return {
        'IntentType': _chat_module.IntentType,
        'Intent': _chat_module.Intent,
        'ChatSession': _chat_module.ChatSession,
        'ChatService': _chat_module.ChatService,
        'get_chat_service': _chat_module.get_chat_service,
    }


# ============================================================================
# Test Classes
# ============================================================================

class TestIntentType:
    """Tests for IntentType enum."""

    def test_intent_types_exist(self):
        """Test that all expected intent types exist."""
        classes = _get_classes()
        IntentType = classes['IntentType']

        assert IntentType.QUERY_KNOWLEDGE
        assert IntentType.TRIGGER_SCOUT
        assert IntentType.CREATE_PLAN
        assert IntentType.SHOW_REPORT
        assert IntentType.LIST_PLANS
        assert IntentType.SHOW_RULES
        assert IntentType.CHECK_STALENESS
        assert IntentType.GENERAL

    def test_intent_type_values(self):
        """Test intent type enum values."""
        classes = _get_classes()
        IntentType = classes['IntentType']

        assert IntentType.QUERY_KNOWLEDGE.value == "query_knowledge"
        assert IntentType.TRIGGER_SCOUT.value == "trigger_scout"
        assert IntentType.CREATE_PLAN.value == "create_plan"


class TestIntent:
    """Tests for Intent class."""

    def test_intent_creation(self):
        """Test creating an intent."""
        classes = _get_classes()
        Intent = classes['Intent']
        IntentType = classes['IntentType']

        intent = Intent(
            intent_type=IntentType.QUERY_KNOWLEDGE,
            query="tech_stack"
        )

        assert intent.type == IntentType.QUERY_KNOWLEDGE
        assert intent.query == "tech_stack"
        assert intent.target == ""

    def test_intent_with_target(self):
        """Test intent with target."""
        classes = _get_classes()
        Intent = classes['Intent']
        IntentType = classes['IntentType']

        intent = Intent(
            intent_type=IntentType.TRIGGER_SCOUT,
            target="src/components"
        )

        assert intent.type == IntentType.TRIGGER_SCOUT
        assert intent.target == "src/components"

    def test_intent_with_report_type(self):
        """Test intent with report type."""
        classes = _get_classes()
        Intent = classes['Intent']
        IntentType = classes['IntentType']

        intent = Intent(
            intent_type=IntentType.SHOW_REPORT,
            report_type="summary"
        )

        assert intent.type == IntentType.SHOW_REPORT
        assert intent.report_type == "summary"


class TestChatSession:
    """Tests for ChatSession class."""

    def test_session_creation(self):
        """Test creating a chat session."""
        classes = _get_classes()
        ChatSession = classes['ChatSession']

        session = ChatSession("test-session-123", context="test context")

        assert session.session_id == "test-session-123"
        assert session.context == "test context"
        assert session.history == []
        assert session.created_at is not None

    def test_session_default_context(self):
        """Test session with no context."""
        classes = _get_classes()
        ChatSession = classes['ChatSession']

        session = ChatSession("test-id")

        assert session.session_id == "test-id"
        assert session.context is None

    def test_add_message(self):
        """Test adding messages to session."""
        classes = _get_classes()
        ChatSession = classes['ChatSession']

        session = ChatSession("test-session")
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi there!")

        assert len(session.history) == 2
        assert session.history[0]["role"] == "user"
        assert session.history[0]["content"] == "Hello"
        assert session.history[1]["role"] == "assistant"
        assert "timestamp" in session.history[0]

    def test_get_recent_history(self):
        """Test getting recent history with limit."""
        classes = _get_classes()
        ChatSession = classes['ChatSession']

        session = ChatSession("test-session")
        for i in range(15):
            session.add_message("user", f"Message {i}")

        recent = session.get_recent_history(max_messages=5)

        assert len(recent) == 5
        assert recent[0]["content"] == "Message 10"
        assert recent[4]["content"] == "Message 14"

    def test_get_recent_history_default_limit(self):
        """Test get_recent_history with default limit."""
        classes = _get_classes()
        ChatSession = classes['ChatSession']

        session = ChatSession("test-session")
        for i in range(20):
            session.add_message("user", f"Message {i}")

        recent = session.get_recent_history()  # Default is 10

        assert len(recent) == 10
        assert recent[0]["content"] == "Message 10"


class TestChatServiceIntentParsing:
    """Tests for ChatService intent parsing."""

    @pytest.fixture
    def chat_service(self, tmp_path):
        """Create a ChatService instance with mocked dependencies."""
        mocks = _get_mocks()
        classes = _get_classes()
        ChatService = classes['ChatService']

        mocks['knowledge_store'].KnowledgeStore.return_value = Mock()
        mocks['db'].get_knowledge_repository.return_value = Mock()
        mocks['db'].get_plan_repository.return_value = Mock()

        return ChatService(tmp_path)

    # Scout/Scan intent tests
    @pytest.mark.parametrize("message,expected_target", [
        ("scan", ""),
        ("scout", ""),
        ("scan src/components", "src/components"),
        ("run scout", ""),
        ("run scout api/routes", "api/routes"),
        ("analyze", ""),
        ("analyze src/", "src/"),
        ("refresh knowledge", ""),
    ])
    def test_parse_intent_scout(self, chat_service, message, expected_target):
        """Test parsing scout/scan intents."""
        classes = _get_classes()
        IntentType = classes['IntentType']

        intent = chat_service.parse_intent(message)

        assert intent.type == IntentType.TRIGGER_SCOUT
        assert intent.target == expected_target

    # Plan creation intent tests
    @pytest.mark.parametrize("message,expected_query_contains", [
        ("create a plan for user auth", "user auth"),
        ("make plan for adding tests", "adding tests"),
        ("generate plan for refactoring", "refactoring"),
        ("plan add dark mode", "add dark mode"),
        ("i want to implement caching", "implement caching"),
        ("implement user profiles", "user profiles"),
        ("add logging system", "logging system"),
    ])
    def test_parse_intent_plan_creation(self, chat_service, message, expected_query_contains):
        """Test parsing plan creation intents."""
        classes = _get_classes()
        IntentType = classes['IntentType']

        intent = chat_service.parse_intent(message)

        assert intent.type == IntentType.CREATE_PLAN
        assert expected_query_contains in intent.query.lower()

    # Knowledge query intent tests
    @pytest.mark.parametrize("message", [
        "what technologies are used",
        "what tech is used",
        "show tech stack",
        "list frameworks",
        "get tools",
        "display languages",
        "tech stack",
        "stack info",
    ])
    def test_parse_intent_knowledge_tech(self, chat_service, message):
        """Test parsing tech stack query intents."""
        classes = _get_classes()
        IntentType = classes['IntentType']

        intent = chat_service.parse_intent(message)

        assert intent.type == IntentType.QUERY_KNOWLEDGE
        assert intent.query == "tech_stack"

    def test_parse_intent_knowledge_domains(self, chat_service):
        """Test parsing domains query intent."""
        classes = _get_classes()
        IntentType = classes['IntentType']

        for message in ["what are the domains", "show domains", "list domains"]:
            intent = chat_service.parse_intent(message)
            assert intent.type == IntentType.QUERY_KNOWLEDGE
            assert intent.query == "domains"

    def test_parse_intent_knowledge_architecture(self, chat_service):
        """Test parsing architecture query intent."""
        classes = _get_classes()
        IntentType = classes['IntentType']

        for message in ["what is the architecture", "show architecture", "describe architecture"]:
            intent = chat_service.parse_intent(message)
            assert intent.type == IntentType.QUERY_KNOWLEDGE
            assert intent.query == "architecture"

    # Coding rules intent tests
    @pytest.mark.parametrize("message", [
        "show rules",
        "list coding rules",
        "what are the rules",
    ])
    def test_parse_intent_show_rules(self, chat_service, message):
        """Test parsing show rules intent."""
        classes = _get_classes()
        IntentType = classes['IntentType']

        intent = chat_service.parse_intent(message)
        assert intent.type == IntentType.SHOW_RULES

    # Staleness check intent tests
    @pytest.mark.parametrize("message", [
        "is knowledge stale",
        "is knowledge current",
        "is stale",
        "is up to date",
        "check staleness",
        "check freshness",
        "last scan",
        "when was last scan",
    ])
    def test_parse_intent_staleness(self, chat_service, message):
        """Test parsing staleness check intent."""
        classes = _get_classes()
        IntentType = classes['IntentType']

        intent = chat_service.parse_intent(message)
        assert intent.type == IntentType.CHECK_STALENESS

    def test_parse_intent_staleness_edge_cases(self, chat_service):
        """Test messages that don't match staleness patterns fall through."""
        classes = _get_classes()
        IntentType = classes['IntentType']

        # "is it up to date" doesn't match pattern
        intent = chat_service.parse_intent("is it up to date")
        assert intent.type == IntentType.GENERAL

    # List plans intent tests
    @pytest.mark.parametrize("message", [
        "show plans",
        "list plans",
        "get my plans",
    ])
    def test_parse_intent_list_plans(self, chat_service, message):
        """Test parsing list plans intent."""
        classes = _get_classes()
        IntentType = classes['IntentType']

        intent = chat_service.parse_intent(message)
        assert intent.type == IntentType.LIST_PLANS

    # Report intent tests
    @pytest.mark.parametrize("message,expected_type", [
        ("show report", "knowledge"),
        ("get knowledge report", "knowledge"),
        ("show summary", "summary"),
        ("overview", "summary"),
    ])
    def test_parse_intent_report(self, chat_service, message, expected_type):
        """Test parsing report intent."""
        classes = _get_classes()
        IntentType = classes['IntentType']

        intent = chat_service.parse_intent(message)
        assert intent.type == IntentType.SHOW_REPORT
        assert intent.report_type == expected_type

    # General intent tests
    def test_parse_intent_general(self, chat_service):
        """Test that unrecognized messages default to general."""
        classes = _get_classes()
        IntentType = classes['IntentType']

        intent = chat_service.parse_intent("hello there")
        assert intent.type == IntentType.GENERAL

        intent = chat_service.parse_intent("random question about something")
        assert intent.type == IntentType.GENERAL


class TestChatServiceSessionManagement:
    """Tests for ChatService session management."""

    @pytest.fixture
    def chat_service(self, tmp_path):
        """Create a ChatService instance."""
        mocks = _get_mocks()
        classes = _get_classes()
        ChatService = classes['ChatService']

        mocks['knowledge_store'].KnowledgeStore.return_value = Mock()
        mocks['db'].get_knowledge_repository.return_value = Mock()
        mocks['db'].get_plan_repository.return_value = Mock()

        return ChatService(tmp_path)

    def test_create_session(self, chat_service):
        """Test creating a new session."""
        session = chat_service.create_session("session-123", context="test")

        assert chat_service.has_session("session-123")
        assert session.session_id == "session-123"
        assert session.context == "test"

    def test_has_session(self, chat_service):
        """Test checking if session exists."""
        assert chat_service.has_session("nonexistent") is False

        chat_service.create_session("exists")
        assert chat_service.has_session("exists") is True

    def test_end_session(self, chat_service):
        """Test ending a session."""
        chat_service.create_session("to-end")
        assert chat_service.has_session("to-end") is True

        chat_service.end_session("to-end")
        assert chat_service.has_session("to-end") is False

    def test_end_nonexistent_session(self, chat_service):
        """Test ending a session that doesn't exist."""
        chat_service.end_session("nonexistent")


@pytest.mark.asyncio
class TestChatServiceHandlers:
    """Tests for ChatService message handling."""

    @pytest.fixture
    def mock_knowledge_store(self):
        """Create a mock knowledge store."""
        store = Mock()
        store.load.return_value = None
        return store

    @pytest.fixture
    def mock_knowledge_repo(self):
        """Create a mock knowledge repository."""
        repo = Mock()
        repo.get_coding_rules.return_value = []
        return repo

    @pytest.fixture
    def mock_plan_repo(self):
        """Create a mock plan repository."""
        repo = Mock()
        repo.get_recent_plans.return_value = []
        return repo

    @pytest.fixture
    def chat_service(self, mock_knowledge_store, mock_knowledge_repo, mock_plan_repo, tmp_path):
        """Create a ChatService with mocked dependencies."""
        mocks = _get_mocks()
        classes = _get_classes()
        ChatService = classes['ChatService']

        mocks['knowledge_store'].KnowledgeStore.return_value = mock_knowledge_store
        mocks['db'].get_knowledge_repository.return_value = mock_knowledge_repo
        mocks['db'].get_plan_repository.return_value = mock_plan_repo

        return ChatService(tmp_path)

    async def test_handle_message_creates_session(self, chat_service):
        """Test that handle_message creates session if needed."""
        assert chat_service.has_session("new-session") is False
        await chat_service.handle_message("hello", "new-session")
        assert chat_service.has_session("new-session") is True

    async def test_handle_message_adds_to_history(self, chat_service):
        """Test that handle_message adds messages to history."""
        session = chat_service.create_session("test-session")
        await chat_service.handle_message("hello", "test-session")

        assert len(session.history) == 2
        assert session.history[0]["role"] == "user"
        assert session.history[0]["content"] == "hello"

    async def test_handle_query_knowledge_no_knowledge(self, chat_service, mock_knowledge_store):
        """Test knowledge query when no knowledge exists."""
        mock_knowledge_store.load.return_value = None
        result = await chat_service.handle_message("what tech is used", "test")
        assert "No knowledge available" in result["response"]

    async def test_handle_show_rules_no_rules(self, chat_service, mock_knowledge_repo):
        """Test show rules when no rules exist."""
        mock_knowledge_repo.get_coding_rules.return_value = []
        result = await chat_service.handle_message("show rules", "test")
        assert "No coding rules found" in result["response"]

    async def test_handle_list_plans_no_plans(self, chat_service, mock_plan_repo):
        """Test list plans when no plans exist."""
        mock_plan_repo.get_recent_plans.return_value = []
        result = await chat_service.handle_message("show plans", "test")
        assert "No plans found" in result["response"]

    async def test_handle_general_intent(self, chat_service):
        """Test handling general/unknown intent."""
        result = await chat_service.handle_message("random message", "test")
        assert "I can help you with" in result["response"]
        assert result["action"] == "general"

    async def test_handle_check_staleness_no_knowledge(self, chat_service):
        """Test staleness check when no knowledge exists."""
        mocks = _get_mocks()
        mocks['staleness'].get_staleness_summary.return_value = {"has_knowledge": False}

        result = await chat_service.handle_message("is knowledge stale", "test")
        assert "No knowledge exists" in result["response"]
        assert result["action"] == "check_staleness"

    async def test_handle_check_staleness_stale(self, chat_service):
        """Test staleness check when knowledge is stale."""
        mocks = _get_mocks()
        mocks['staleness'].get_staleness_summary.return_value = {
            "has_knowledge": True,
            "is_stale": True,
            "reason": "5 commits behind"
        }

        result = await chat_service.handle_message("check staleness", "test")
        assert "stale" in result["response"].lower()
        assert "5 commits behind" in result["response"]

    async def test_handle_check_staleness_current(self, chat_service):
        """Test staleness check when knowledge is current."""
        mocks = _get_mocks()
        mocks['staleness'].get_staleness_summary.return_value = {
            "has_knowledge": True,
            "is_stale": False,
            "reason": "Knowledge is current",
            "last_scan_time": "2024-01-15T10:30:00"
        }

        result = await chat_service.handle_message("is knowledge current", "test")
        assert "current" in result["response"].lower()


class TestGetChatService:
    """Tests for get_chat_service singleton."""

    def test_get_chat_service_returns_instance(self):
        """Test that get_chat_service returns an instance."""
        global _chat_module
        mocks = _get_mocks()
        classes = _get_classes()
        ChatService = classes['ChatService']
        get_chat_service = classes['get_chat_service']

        _chat_module._chat_service = None
        mocks['knowledge_store'].KnowledgeStore.return_value = Mock()
        mocks['db'].get_knowledge_repository.return_value = Mock()
        mocks['db'].get_plan_repository.return_value = Mock()

        service = get_chat_service()
        assert service is not None
        assert isinstance(service, ChatService)

    def test_get_chat_service_returns_singleton(self):
        """Test that get_chat_service returns the same instance."""
        global _chat_module
        mocks = _get_mocks()
        classes = _get_classes()
        get_chat_service = classes['get_chat_service']

        _chat_module._chat_service = None
        mocks['knowledge_store'].KnowledgeStore.return_value = Mock()
        mocks['db'].get_knowledge_repository.return_value = Mock()
        mocks['db'].get_plan_repository.return_value = Mock()

        service1 = get_chat_service()
        service2 = get_chat_service()
        assert service1 is service2
