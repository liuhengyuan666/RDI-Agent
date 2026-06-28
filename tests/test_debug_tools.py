"""
Tests for Debug Tools — Phase 3 tool chain.

Uses unittest.mock to mock subprocess.run for isolated, deterministic testing.
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from reality_agent.state import RealityAgentState
from reality_agent.tools.debug_tools import (
    check_git_consistency,
    check_environment,
    reproduce_issue,
    _find_git_root,
)


class TestReproduceIssue:
    """Tests for reproduce_issue() — §10 Step 1."""

    @patch.dict(os.environ, {"RDI_REPRODUCE_COMMAND": "pytest tests/test_panic.py"})
    @patch("reality_agent.tools.debug_tools.subprocess.run")
    def test_reproduce_success_bug_manifested(self, mock_run):
        """Bug 复现成功：非零退出码视为成功捕获现象."""
        mock_result = MagicMock()
        mock_result.returncode = 1  # Non-zero = bug reproduced
        mock_result.stdout = "AssertionError: expected 5, got 3"
        mock_result.stderr = "Traceback (most recent call last): ..."
        mock_run.return_value = mock_result

        state = RealityAgentState(user_request="fix panic")
        result = reproduce_issue(state)

        assert result["reproduced"] is True
        assert result["exit_code"] == 1
        assert "BUG REPRODUCED" in result["tool_outputs"][0]
        mock_run.assert_called_once()

    @patch.dict(os.environ, {"RDI_REPRODUCE_COMMAND": "pytest tests/test_panic.py"})
    @patch("reality_agent.tools.debug_tools.subprocess.run")
    def test_reproduce_no_bug_in_run(self, mock_run):
        """Bug 未在本次运行中复现：零退出码."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "3 passed in 0.5s"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        state = RealityAgentState(user_request="fix panic")
        result = reproduce_issue(state)

        assert result["reproduced"] is False
        assert result["exit_code"] == 0
        assert "No bug in this run" in result["tool_outputs"][0]

    @patch.dict(os.environ, {}, clear=True)
    def test_reproduce_missing_config(self):
        """缺少 RDI_REPRODUCE_COMMAND 配置时返回安全 fallback."""
        state = RealityAgentState(user_request="fix panic")
        result = reproduce_issue(state)

        assert result["reproduced"] is False
        assert result["exit_code"] == -1
        assert "WARNING" in result["tool_outputs"][0]
        assert "not configured" in result["tool_outputs"][0]

    @patch.dict(os.environ, {"RDI_REPRODUCE_COMMAND": "pytest tests/test_panic.py"})
    @patch("reality_agent.tools.debug_tools.subprocess.run")
    def test_reproduce_timeout(self, mock_run):
        """复现命令超时处理."""
        from subprocess import TimeoutExpired
        mock_run.side_effect = TimeoutExpired("pytest", 300)

        state = RealityAgentState(user_request="fix panic")
        result = reproduce_issue(state)

        assert result["reproduced"] is False
        assert result["exit_code"] == -2
        assert "timed out" in result["tool_outputs"][0]

    @patch.dict(os.environ, {"RDI_REPRODUCE_COMMAND": "pytest tests/test_panic.py"})
    @patch("reality_agent.tools.debug_tools.subprocess.run")
    def test_reproduce_captures_command(self, mock_run):
        """结果中必须包含实际执行的命令."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        state = RealityAgentState(user_request="fix panic")
        result = reproduce_issue(state)

        assert result["command"] == "pytest tests/test_panic.py"


class TestFindGitRoot:
    """Tests for _find_git_root() auto-discovery."""

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.resolve")
    def test_find_git_in_current_dir(self, mock_resolve, mock_exists):
        """当前目录即为 git repo."""
        mock_exists.return_value = True
        mock_resolve.return_value = Path("/project")

        root = _find_git_root("/project")
        assert root == Path("/project")

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.resolve")
    def test_find_git_in_parent(self, mock_resolve, mock_exists):
        """.git 在父目录，向上查找成功."""
        # First call (current) returns False, second (parent) returns True
        call_count = [0]
        def side_effect_exists():
            call_count[0] += 1
            return call_count[0] > 1

        mock_exists.side_effect = side_effect_exists
        mock_resolve.return_value = Path("/project/subdir")

        root = _find_git_root("/project/subdir")
        assert root == Path("/project")

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.resolve")
    def test_no_git_found(self, mock_resolve, mock_exists):
        """向上遍历到根目录也未找到 .git."""
        mock_exists.return_value = False
        mock_resolve.return_value = Path("/some/path")

        root = _find_git_root("/some/path")
        assert root is None


class TestCheckGitConsistency:
    """Tests for check_git_consistency() — §10 Step 2."""

    @patch("reality_agent.tools.debug_tools._find_git_root")
    @patch("reality_agent.tools.debug_tools.subprocess.run")
    def test_git_repo_clean(self, mock_run, mock_find):
        """Git repo 干净一致的状态."""
        mock_find.return_value = Path("/project")

        def mock_run_side_effect(*args, **kwargs):
            cmd = args[0] if args else []
            mock = MagicMock()
            if "rev-parse" in cmd:
                mock.returncode = 0
                mock.stdout = "abc1234\n"
                mock.stderr = ""
            elif "status" in cmd:
                mock.returncode = 0
                mock.stdout = ""  # Clean = empty
                mock.stderr = ""
            elif "describe" in cmd:
                mock.returncode = 0
                mock.stdout = "v1.2.3\n"
                mock.stderr = ""
            return mock

        mock_run.side_effect = mock_run_side_effect

        state = RealityAgentState(user_request="check git")
        result = check_git_consistency(state)

        assert result["git_available"] is True
        assert result["commit_hash"] == "abc1234"
        assert result["working_tree_clean"] is True
        assert result["uncommitted_files"] == []
        assert result["latest_tag"] == "v1.2.3"
        assert result["repo_root"] == str(Path("/project"))

    @patch("reality_agent.tools.debug_tools._find_git_root")
    @patch("reality_agent.tools.debug_tools.subprocess.run")
    def test_git_repo_dirty(self, mock_run, mock_find):
        """Git repo 有未提交更改."""
        mock_find.return_value = Path("/project")

        def mock_run_side_effect(*args, **kwargs):
            cmd = args[0] if args else []
            mock = MagicMock()
            if "rev-parse" in cmd:
                mock.returncode = 0
                mock.stdout = "abc1234\n"
                mock.stderr = ""
            elif "status" in cmd:
                mock.returncode = 0
                mock.stdout = " M src/main.py\n?? new_file.txt\n"
                mock.stderr = ""
            elif "describe" in cmd:
                mock.returncode = 128
                mock.stdout = ""
                mock.stderr = "fatal: No names found"
            return mock

        mock_run.side_effect = mock_run_side_effect

        state = RealityAgentState(user_request="check git")
        result = check_git_consistency(state)

        assert result["working_tree_clean"] is False
        assert len(result["uncommitted_files"]) == 2
        assert "src/main.py" in result["uncommitted_files"][0]
        assert result["latest_tag"] is None

    @patch("reality_agent.tools.debug_tools._find_git_root")
    def test_no_git_repo(self, mock_find):
        """完全找不到 git repo."""
        mock_find.return_value = None

        state = RealityAgentState(user_request="check git")
        result = check_git_consistency(state)

        assert result["git_available"] is False
        assert result["repo_root"] is None
        assert result["commit_hash"] is None

    @patch("reality_agent.tools.debug_tools._find_git_root")
    @patch("reality_agent.tools.debug_tools.subprocess.run")
    def test_git_command_failure(self, mock_run, mock_find):
        """Git 命令执行失败（如 git 未安装）."""
        mock_find.return_value = Path("/project")
        mock_run.side_effect = FileNotFoundError("git not found")

        state = RealityAgentState(user_request="check git")
        result = check_git_consistency(state)

        assert result["git_available"] is False
        assert result["commit_hash"] is None


class TestCheckEnvironment:
    """Tests for check_environment() — §10 Step 2."""

    @patch.dict(os.environ, {
        "RDI_REPRODUCE_COMMAND": "pytest tests/",
        "RDI_BENCHMARK_COMMAND": "cargo bench",
        "LLM_PROVIDER": "openai",
        "LLM_MODEL": "gpt-4o",
    })
    def test_env_vars_reported(self):
        """关键环境变量被正确列出."""
        state = RealityAgentState(user_request="check env")
        result = check_environment(state)

        assert "RDI_REPRODUCE_COMMAND" in result["env_status"]
        assert result["env_status"]["RDI_REPRODUCE_COMMAND"] == "pytest tests/"
        assert result["env_status"]["LLM_PROVIDER"] == "openai"

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_env_vars(self):
        """缺失的环境变量显示 NOT SET."""
        state = RealityAgentState(user_request="check env")
        result = check_environment(state)

        assert result["env_status"]["RDI_REPRODUCE_COMMAND"] == "NOT SET"
