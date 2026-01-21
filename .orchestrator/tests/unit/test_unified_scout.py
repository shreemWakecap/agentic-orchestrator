"""
Unit tests for UnifiedScoutWorkflow.
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


class TestUnifiedScoutWorkflowInit:
    """Tests for UnifiedScoutWorkflow initialization."""

    @pytest.fixture
    def mock_deps(self):
        """Create mocked dependencies."""
        with patch('workflows.unified_scout.get_agent_config') as mock_config:
            with patch('workflows.unified_scout.KnowledgeStore') as mock_ks:
                with patch('workflows.unified_scout.get_knowledge_repository') as mock_kr:
                    with patch('workflows.unified_scout.Agent') as mock_agent:
                        mock_config.return_value = {}
                        mock_ks.return_value = Mock()
                        mock_kr.return_value = Mock()
                        mock_agent.load.return_value = Mock()
                        yield {
                            'config': mock_config,
                            'knowledge_store': mock_ks,
                            'knowledge_repo': mock_kr,
                            'agent': mock_agent,
                        }

    def test_workflow_initialization(self, mock_deps, tmp_path):
        """Test workflow initializes with correct attributes."""
        from workflows.unified_scout import UnifiedScoutWorkflow

        workflow = UnifiedScoutWorkflow(tmp_path)

        assert workflow.project_root == tmp_path
        assert workflow.name == "Unified Scout Workflow"
        mock_deps['agent'].load.assert_called_once_with("scout", tmp_path)


class TestGitState:
    """Tests for git state retrieval."""

    @pytest.fixture
    def workflow(self, tmp_path):
        """Create a workflow with mocked dependencies."""
        with patch('workflows.unified_scout.get_agent_config', return_value={}):
            with patch('workflows.unified_scout.KnowledgeStore'):
                with patch('workflows.unified_scout.get_knowledge_repository'):
                    with patch('workflows.unified_scout.Agent'):
                        from workflows.unified_scout import UnifiedScoutWorkflow
                        return UnifiedScoutWorkflow(tmp_path)

    @patch('subprocess.run')
    def test_get_git_state_success(self, mock_subprocess, workflow):
        """Test successful git state retrieval."""
        def mock_run(cmd, **kwargs):
            result = Mock()
            result.returncode = 0
            if "rev-parse" in cmd and "HEAD" in cmd and "--abbrev-ref" not in cmd:
                result.stdout = "abc123def456"
            elif "--abbrev-ref" in cmd:
                result.stdout = "main"
            return result

        mock_subprocess.side_effect = mock_run

        state = workflow._get_git_state()

        assert state["commit_hash"] == "abc123def456"
        assert state["branch"] == "main"

    @patch('subprocess.run')
    def test_get_git_state_failure(self, mock_subprocess, workflow):
        """Test git state retrieval when git fails."""
        mock_subprocess.return_value = Mock(returncode=1, stdout="")

        state = workflow._get_git_state()

        assert state["commit_hash"] is None
        assert state["branch"] is None

    @patch('subprocess.run')
    def test_get_git_state_exception(self, mock_subprocess, workflow):
        """Test git state retrieval handles exceptions."""
        mock_subprocess.side_effect = Exception("Git not found")

        state = workflow._get_git_state()

        assert state["commit_hash"] is None
        assert state["branch"] is None


class TestChangedFiles:
    """Tests for changed files detection."""

    @pytest.fixture
    def workflow(self, tmp_path):
        """Create a workflow with mocked dependencies."""
        with patch('workflows.unified_scout.get_agent_config', return_value={}):
            with patch('workflows.unified_scout.KnowledgeStore'):
                with patch('workflows.unified_scout.get_knowledge_repository'):
                    with patch('workflows.unified_scout.Agent'):
                        from workflows.unified_scout import UnifiedScoutWorkflow
                        return UnifiedScoutWorkflow(tmp_path)

    @patch('subprocess.run')
    def test_get_changed_files_success(self, mock_subprocess, workflow):
        """Test successful changed files retrieval."""
        def mock_run(cmd, **kwargs):
            result = Mock()
            result.returncode = 0
            if "diff" in cmd:
                result.stdout = "src/main.py\nsrc/utils.py"
            elif "ls-files" in cmd:
                result.stdout = "src/new_file.py"
            return result

        mock_subprocess.side_effect = mock_run

        files = workflow._get_changed_files_since_commit("abc123")

        assert "src/main.py" in files
        assert "src/utils.py" in files
        assert "src/new_file.py" in files

    @patch('subprocess.run')
    def test_get_changed_files_deduplicates(self, mock_subprocess, workflow):
        """Test that duplicate files are removed."""
        def mock_run(cmd, **kwargs):
            result = Mock()
            result.returncode = 0
            if "diff" in cmd:
                result.stdout = "src/file.py\nsrc/file.py"  # Duplicate
            else:
                result.stdout = "src/file.py"  # Also duplicate
            return result

        mock_subprocess.side_effect = mock_run

        files = workflow._get_changed_files_since_commit("abc123")

        assert files.count("src/file.py") == 1

    @patch('subprocess.run')
    def test_count_commits_since_success(self, mock_subprocess, workflow):
        """Test counting commits since a hash."""
        mock_subprocess.return_value = Mock(returncode=0, stdout="15")

        count = workflow._count_commits_since("abc123")

        assert count == 15

    @patch('subprocess.run')
    def test_count_commits_since_failure(self, mock_subprocess, workflow):
        """Test counting commits handles failure."""
        mock_subprocess.return_value = Mock(returncode=1)

        count = workflow._count_commits_since("abc123")

        assert count == 0


class TestShouldDoFullScan:
    """Tests for scan mode determination."""

    @pytest.fixture
    def mock_knowledge_repo(self):
        """Create a mock knowledge repository."""
        return Mock()

    @pytest.fixture
    def mock_knowledge_store(self):
        """Create a mock knowledge store."""
        return Mock()

    @pytest.fixture
    def workflow(self, tmp_path, mock_knowledge_repo, mock_knowledge_store):
        """Create a workflow with mocked dependencies."""
        with patch('workflows.unified_scout.get_agent_config', return_value={}):
            with patch('workflows.unified_scout.KnowledgeStore', return_value=mock_knowledge_store):
                with patch('workflows.unified_scout.get_knowledge_repository', return_value=mock_knowledge_repo):
                    with patch('workflows.unified_scout.Agent'):
                        from workflows.unified_scout import UnifiedScoutWorkflow
                        return UnifiedScoutWorkflow(tmp_path)

    def test_force_full_returns_true(self, workflow):
        """Test that force_full always triggers full scan."""
        should_full, reason = workflow._should_do_full_scan(force_full=True)

        assert should_full is True
        assert "Full scan requested" in reason

    def test_target_paths_returns_incremental(self, workflow):
        """Test that target_paths triggers incremental scan."""
        should_full, reason = workflow._should_do_full_scan(
            force_full=False,
            target_paths=["src/main.py", "src/utils.py"]
        )

        assert should_full is False
        assert "Targeted scan" in reason

    def test_no_knowledge_returns_full(self, workflow, mock_knowledge_store):
        """Test that missing knowledge triggers full scan."""
        mock_knowledge_store.exists.return_value = False

        should_full, reason = workflow._should_do_full_scan()

        assert should_full is True
        assert "No existing knowledge" in reason

    def test_no_scan_metadata_returns_full(self, workflow, mock_knowledge_store, mock_knowledge_repo):
        """Test that missing scan metadata triggers full scan."""
        mock_knowledge_store.exists.return_value = True
        mock_knowledge_repo.get_scan_metadata.return_value = None

        should_full, reason = workflow._should_do_full_scan()

        assert should_full is True
        assert "No previous scan metadata" in reason

    def test_no_commit_hash_returns_full(self, workflow, mock_knowledge_store, mock_knowledge_repo):
        """Test that missing commit hash triggers full scan."""
        mock_knowledge_store.exists.return_value = True
        mock_knowledge_repo.get_scan_metadata.return_value = {
            "scan_time": "2024-01-15T10:00:00",
            "git_commit_hash": None,
        }

        should_full, reason = workflow._should_do_full_scan()

        assert should_full is True
        assert "No git commit hash" in reason

    @patch('subprocess.run')
    def test_same_commit_returns_incremental(
        self, mock_subprocess, workflow, mock_knowledge_store, mock_knowledge_repo
    ):
        """Test that same commit returns no changes."""
        mock_knowledge_store.exists.return_value = True
        mock_knowledge_repo.get_scan_metadata.return_value = {
            "git_commit_hash": "abc123"
        }

        mock_subprocess.return_value = Mock(returncode=0, stdout="abc123")

        should_full, reason = workflow._should_do_full_scan()

        assert should_full is False
        assert "No changes" in reason

    @patch('subprocess.run')
    def test_many_commits_returns_full(
        self, mock_subprocess, workflow, mock_knowledge_store, mock_knowledge_repo
    ):
        """Test that many commits behind triggers full scan."""
        mock_knowledge_store.exists.return_value = True
        mock_knowledge_repo.get_scan_metadata.return_value = {
            "git_commit_hash": "old123"
        }

        def mock_run(cmd, **kwargs):
            result = Mock()
            result.returncode = 0
            if "rev-parse" in cmd:
                result.stdout = "new456"  # Different commit
            elif "rev-list" in cmd and "--count" in cmd:
                result.stdout = "55"  # Over threshold
            return result

        mock_subprocess.side_effect = mock_run

        should_full, reason = workflow._should_do_full_scan()

        assert should_full is True
        assert "commits since last scan" in reason

    @patch('subprocess.run')
    def test_many_files_changed_returns_full(
        self, mock_subprocess, workflow, mock_knowledge_store, mock_knowledge_repo
    ):
        """Test that many files changed triggers full scan."""
        mock_knowledge_store.exists.return_value = True
        mock_knowledge_repo.get_scan_metadata.return_value = {
            "git_commit_hash": "old123"
        }

        def mock_run(cmd, **kwargs):
            result = Mock()
            result.returncode = 0
            if "rev-parse" in cmd:
                result.stdout = "new456"
            elif "rev-list" in cmd:
                result.stdout = "10"  # Under commit threshold
            elif "diff" in cmd:
                # Return 150 files
                files = [f"src/file{i}.py" for i in range(150)]
                result.stdout = "\n".join(files)
            else:
                result.stdout = ""
            return result

        mock_subprocess.side_effect = mock_run

        should_full, reason = workflow._should_do_full_scan()

        assert should_full is True
        assert "files changed" in reason

    @patch('subprocess.run')
    def test_few_changes_returns_incremental(
        self, mock_subprocess, workflow, mock_knowledge_store, mock_knowledge_repo
    ):
        """Test that few changes triggers incremental scan."""
        mock_knowledge_store.exists.return_value = True
        mock_knowledge_repo.get_scan_metadata.return_value = {
            "git_commit_hash": "old123"
        }

        def mock_run(cmd, **kwargs):
            result = Mock()
            result.returncode = 0
            if "rev-parse" in cmd:
                result.stdout = "new456"
            elif "rev-list" in cmd:
                result.stdout = "5"
            elif "diff" in cmd:
                result.stdout = "src/main.py\nsrc/utils.py"
            else:
                result.stdout = ""
            return result

        mock_subprocess.side_effect = mock_run

        should_full, reason = workflow._should_do_full_scan()

        assert should_full is False
        assert "Incremental scan" in reason
        assert "2 files changed" in reason


class TestFilterSourcePaths:
    """Tests for path filtering."""

    @pytest.fixture
    def workflow(self, tmp_path):
        """Create a workflow with mocked dependencies."""
        with patch('workflows.unified_scout.get_agent_config', return_value={}):
            with patch('workflows.unified_scout.KnowledgeStore'):
                with patch('workflows.unified_scout.get_knowledge_repository'):
                    with patch('workflows.unified_scout.Agent'):
                        from workflows.unified_scout import UnifiedScoutWorkflow
                        return UnifiedScoutWorkflow(tmp_path)

    def test_filter_excludes_node_modules(self, workflow):
        """Test that node_modules are filtered."""
        paths = [
            "src/main.py",
            "node_modules/pkg/index.js",
            "node_modules/other/file.js"
        ]

        filtered = workflow._filter_source_paths(paths)

        assert "src/main.py" in filtered
        assert len(filtered) == 1

    def test_filter_excludes_venv(self, workflow):
        """Test that venv directories are filtered."""
        paths = [
            "src/main.py",
            ".venv/lib/python/site-packages/pkg.py",
            "venv/bin/python"
        ]

        filtered = workflow._filter_source_paths(paths)

        assert "src/main.py" in filtered
        assert len(filtered) == 1

    def test_filter_excludes_pycache(self, workflow):
        """Test that __pycache__ is filtered."""
        paths = [
            "src/main.py",
            "src/__pycache__/main.cpython-311.pyc"
        ]

        filtered = workflow._filter_source_paths(paths)

        assert "src/main.py" in filtered
        assert len(filtered) == 1

    def test_filter_excludes_orchestrator(self, workflow):
        """Test that .orchestrator directory is filtered."""
        paths = [
            "src/main.py",
            ".orchestrator/db/data.db",
            ".orchestrator/agents/scout.md"
        ]

        filtered = workflow._filter_source_paths(paths)

        assert "src/main.py" in filtered
        assert len(filtered) == 1

    def test_filter_excludes_build_dirs(self, workflow):
        """Test that build/dist directories are filtered."""
        paths = [
            "src/main.py",
            "dist/bundle.js",
            "build/output.js"
        ]

        filtered = workflow._filter_source_paths(paths)

        assert "src/main.py" in filtered
        assert len(filtered) == 1

    def test_filter_keeps_source_files(self, workflow):
        """Test that source files are kept."""
        paths = [
            "src/main.py",
            "src/utils/helpers.py",
            "tests/test_main.py",
            "api/routes/users.py"
        ]

        filtered = workflow._filter_source_paths(paths)

        assert len(filtered) == 4
        assert all(p in filtered for p in paths)


class TestPromptBuilding:
    """Tests for prompt building."""

    @pytest.fixture
    def workflow(self, tmp_path):
        """Create a workflow with mocked dependencies."""
        with patch('workflows.unified_scout.get_agent_config', return_value={}):
            with patch('workflows.unified_scout.KnowledgeStore'):
                with patch('workflows.unified_scout.get_knowledge_repository'):
                    with patch('workflows.unified_scout.Agent'):
                        from workflows.unified_scout import UnifiedScoutWorkflow
                        return UnifiedScoutWorkflow(tmp_path)

    def test_build_full_scan_prompt(self, workflow):
        """Test full scan prompt is built correctly."""
        prompt = workflow._build_full_scan_prompt()

        assert "FULL analysis" in prompt
        assert "Project structure" in prompt
        assert "Technologies" in prompt
        assert "Architecture" in prompt
        assert "domains" in prompt.lower()

    def test_build_incremental_scan_prompt(self, workflow):
        """Test incremental scan prompt includes paths."""
        paths = ["src/main.py", "src/utils.py"]

        prompt = workflow._build_incremental_scan_prompt(paths)

        assert "INCREMENTAL" in prompt or "incremental" in prompt
        assert "src/main.py" in prompt
        assert "src/utils.py" in prompt

    def test_build_incremental_scan_prompt_no_paths(self, workflow):
        """Test incremental scan with no paths."""
        prompt = workflow._build_incremental_scan_prompt([])

        # Should still build a valid prompt
        assert len(prompt) > 0


class TestParseScoutOutput:
    """Tests for parsing scout agent output."""

    @pytest.fixture
    def workflow(self, tmp_path):
        """Create a workflow with mocked dependencies."""
        with patch('workflows.unified_scout.get_agent_config', return_value={}):
            with patch('workflows.unified_scout.KnowledgeStore'):
                with patch('workflows.unified_scout.get_knowledge_repository'):
                    with patch('workflows.unified_scout.Agent'):
                        from workflows.unified_scout import UnifiedScoutWorkflow
                        return UnifiedScoutWorkflow(tmp_path)

    def test_parse_valid_json(self, workflow):
        """Test parsing valid JSON output."""
        output = """
        Some text before

        ```json
        {
            "project": {
                "name": "test-project",
                "type": "web-application",
                "primary_language": "Python"
            },
            "technologies": {
                "languages": [{"name": "Python", "version": "3.11", "confidence": 0.9}],
                "frameworks": [],
                "tools": []
            },
            "coding_rules": [
                {"id": "rule-1", "category": "naming", "rule": "Use snake_case", "severity": "warning"}
            ]
        }
        ```

        Some text after
        """

        result = workflow._parse_scout_output(output)

        assert result is not None
        assert result["project"]["name"] == "test-project"
        assert len(result["coding_rules"]) == 1

    def test_parse_invalid_json_returns_none(self, workflow):
        """Test that invalid JSON returns None."""
        output = "This is not valid JSON output"

        result = workflow._parse_scout_output(output)

        assert result is None

    def test_parse_handles_no_json_block(self, workflow):
        """Test parsing when there's no JSON code block."""
        output = """
        {"project": {"name": "test"}, "technologies": {"languages": [], "frameworks": [], "tools": []}}
        """

        # Might parse bare JSON or return None depending on implementation
        result = workflow._parse_scout_output(output)
        # Either parse successfully or return None gracefully
        assert result is None or isinstance(result, dict)
