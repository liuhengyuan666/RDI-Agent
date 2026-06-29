"""Tests for Environment Discovery — §0 Zero-Config."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from reality_agent.nodes.environment_discovery import (
    _build_setup_guide,
    environment_discovery_node,
)
from reality_agent.state import RealityAgentState
from reality_agent.tools.debug_tools import discover_project_language, verify_toolchain_executable


class TestDiscoverProjectLanguage:
    """Zero-Config language detection by physical markers."""

    def test_detect_rust(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "Cargo.toml").write_text("[package]\nname = 'test'\n")
            assert discover_project_language(search_dirs=[tmpdir]) == "rust"

    def test_detect_go(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "go.mod").write_text("module test\n")
            assert discover_project_language(search_dirs=[tmpdir]) == "go"

    def test_detect_python(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "pyproject.toml").write_text("[project]\nname = 'test'\n")
            assert discover_project_language(search_dirs=[tmpdir]) == "python"

    def test_detect_node(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "package.json").write_text('{"name": "test"}')
            assert discover_project_language(search_dirs=[tmpdir]) == "node"

    def test_detect_polyglot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "Cargo.toml").write_text("")
            Path(tmpdir, "go.mod").write_text("")
            assert discover_project_language(search_dirs=[tmpdir]) == "polyglot"

    def test_detect_unknown(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            assert discover_project_language(search_dirs=[tmpdir]) == "unknown"

    def test_fallback_to_cwd(self):
        """When search_dirs is None, should fall back to os.getcwd()."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "pyproject.toml").write_text("[project]\nname = 'test'\n")
            with patch("os.getcwd", return_value=tmpdir):
                assert discover_project_language() == "python"

    def test_detect_from_reproduce_target_dir(self):
        """Simulate scanning a target directory from --reproduce command."""
        with tempfile.TemporaryDirectory() as rust_dir:
            Path(rust_dir, "Cargo.toml").write_text("[package]\nname = 'test'\n")
            # cwd is some other Python project
            with tempfile.TemporaryDirectory() as py_dir:
                Path(py_dir, "pyproject.toml").write_text("[project]\nname = 'agent'\n")
                with patch("os.getcwd", return_value=py_dir):
                    # Without target dir: detects Python (cwd)
                    assert discover_project_language() == "python"
                    # With target dir: detects Rust (reproduce target)
                    assert discover_project_language(search_dirs=[rust_dir, py_dir]) == "rust"
                    # With target dir only: detects Rust
                    assert discover_project_language(search_dirs=[rust_dir]) == "rust"


class TestVerifyToolchainExecutable:
    """shutil.which based toolchain verification."""

    def test_rust_toolchain_available(self):
        with patch("shutil.which", return_value="/usr/bin/cargo"):
            available, path = verify_toolchain_executable("rust")
        assert available is True
        assert "/usr/bin/cargo" in path

    def test_rust_toolchain_missing(self):
        with patch("shutil.which", return_value=None):
            available, reason = verify_toolchain_executable("rust")
        assert available is False
        assert "Missing cargo" in reason

    def test_unknown_language_defaults_available(self):
        # Unknown language should not block (user must specify manually)
        available, reason = verify_toolchain_executable("fortran")
        assert available is True
        assert reason == ""


class TestEnvironmentDiscoveryNode:
    """Integration: node scans environment and writes state updates."""

    def test_toolchain_available(self):
        state = RealityAgentState(user_request="test")
        with patch("os.getcwd", return_value="/tmp"), \
             patch("reality_agent.nodes.environment_discovery.discover_project_language", return_value="python"), \
             patch("reality_agent.nodes.environment_discovery.verify_toolchain_executable", return_value=(True, "/usr/bin/python")):
            result = environment_discovery_node(state)
        assert result["detected_language"] == "python"
        assert result["toolchain_available"] is True
        assert "toolchain available" in result["knowledge_gained"][0].lower()

    def test_toolchain_missing(self):
        state = RealityAgentState(user_request="test")
        with patch("os.getcwd", return_value="/tmp"), \
             patch("reality_agent.nodes.environment_discovery.discover_project_language", return_value="rust"), \
             patch("reality_agent.nodes.environment_discovery.verify_toolchain_executable", return_value=(False, "Missing cargo")):
            result = environment_discovery_node(state)
        assert result["detected_language"] == "rust"
        assert result["toolchain_available"] is False
        assert result["setup_plan"] is not None
        assert "RDI Environment Alert" in result["setup_plan"]
        assert "Missing cargo" in result["knowledge_gained"][0]


class TestBuildSetupGuide:
    """Platform-aware setup guide generation with fallback."""

    def test_rust_windows_guide(self):
        with patch("platform.system", return_value="Windows"):
            guide = _build_setup_guide("rust", "Missing cargo")
        assert "RDI Environment Alert" in guide
        assert "scoop install rustup" in guide
        assert "choco install rustup" in guide
        assert "安全中断" in guide

    def test_rust_macos_guide(self):
        with patch("platform.system", return_value="Darwin"):
            guide = _build_setup_guide("rust", "Missing cargo")
        assert "brew install rustup" in guide
        assert "安全中断" in guide

    def test_rust_linux_guide(self):
        with patch("platform.system", return_value="Linux"):
            guide = _build_setup_guide("rust", "Missing cargo")
        assert "apt install rustc" in guide
        assert "dnf install rust" in guide
        assert "pacman -S rust" in guide
        assert "安全中断" in guide

    def test_rust_unknown_os_fallback(self):
        with patch("platform.system", return_value="FreeBSD"):
            guide = _build_setup_guide("rust", "Missing cargo")
        assert "官方安装指南" in guide
        assert "rustup.rs" in guide
        assert "安全中断" in guide

    def test_python_guide(self):
        with patch("platform.system", return_value="Linux"):
            guide = _build_setup_guide("python", "Missing python")
        assert "python3" in guide
        assert "安全中断" in guide

    def test_unknown_language_generic(self):
        with patch("platform.system", return_value="Linux"):
            guide = _build_setup_guide("elixir", "Missing mix")
        assert "未知项目类型" in guide
        assert "安全中断" in guide
