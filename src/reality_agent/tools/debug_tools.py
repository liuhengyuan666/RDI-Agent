"""Debug tools — Debug Pyramid (§10)."""

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from reality_agent.state import RealityAgentState


# ---------------------------------------------------------------------------
# Configuration: 所有命令通过环境变量读取，禁止硬编码
# ---------------------------------------------------------------------------

DEFAULT_REPRODUCE_COMMAND = "echo 'No RDI_REPRODUCE_COMMAND set. Please configure reproduce script.'"
DEFAULT_BENCHMARK_COMMAND = "echo 'No RDI_BENCHMARK_COMMAND set. Please configure benchmark.'"


# ---------------------------------------------------------------------------
# §10 Step 1: Reproduce Issue
# ---------------------------------------------------------------------------

def reproduce_issue(state: RealityAgentState) -> Dict[str, Any]:
    """
    §10 Step 1: Attempt to reproduce the reported issue.

    Reads RDI_REPRODUCE_COMMAND from environment variable.
    Executes the command via subprocess, capturing stdout and stderr.

    Design philosophy: A non-zero exit code means the bug was successfully
    reproduced (Verify Reality succeeded). A zero exit code means the bug did
    NOT manifest in this run (needs more data).

    Returns:
        {
            "tool_outputs": [str],
            "reproduced": bool,        # True if exit code != 0 (bug manifested)
            "exit_code": int,
            "stdout": str,
            "stderr": str,
            "command": str,
        }
    """
    cmd = os.getenv("RDI_REPRODUCE_COMMAND", DEFAULT_REPRODUCE_COMMAND)

    if cmd == DEFAULT_REPRODUCE_COMMAND:
        return {
            "tool_outputs": [
                "WARNING: RDI_REPRODUCE_COMMAND not configured. "
                "Set env var to your reproduce script (e.g., 'pytest tests/test_panic.py')."
            ],
            "reproduced": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": "",
            "command": cmd,
        }

    try:
        result = subprocess.run(
            cmd,
            shell=True,  # Allows complex commands like "cargo test -- --nocapture"
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout to prevent hanging
        )
    except subprocess.TimeoutExpired:
        return {
            "tool_outputs": ["ERROR: Reproduce command timed out after 300s."],
            "reproduced": False,
            "exit_code": -2,
            "stdout": "",
            "stderr": "Command timed out",
            "command": cmd,
        }
    except Exception as e:
        return {
            "tool_outputs": [f"ERROR: Failed to execute reproduce command: {e}"],
            "reproduced": False,
            "exit_code": -3,
            "stdout": "",
            "stderr": str(e),
            "command": cmd,
        }

    # Non-zero exit = bug manifested (reproduced)
    # Zero exit = bug did NOT manifest this time
    reproduced = result.returncode != 0

    output_summary = (
        f"Command: {cmd}\n"
        f"Exit code: {result.returncode} ({'BUG REPRODUCED' if reproduced else 'No bug in this run'})\n"
        f"stdout length: {len(result.stdout)} chars\n"
        f"stderr length: {len(result.stderr)} chars"
    )

    return {
        "tool_outputs": [output_summary],
        "reproduced": reproduced,
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "command": cmd,
    }


# ---------------------------------------------------------------------------
# §10 Step 2: Git Consistency Check (Auto-discovery)
# ---------------------------------------------------------------------------

def _find_git_root(start_path: Optional[str] = None) -> Optional[Path]:
    """
    Auto-discover .git directory by walking upward from start_path.

    Returns the Path to the repository root (parent of .git), or None.
    """
    if start_path is None:
        start_path = os.getcwd()

    current = Path(start_path).resolve()

    # Walk upward until we find .git or hit the filesystem root
    for parent in [current, *current.parents]:
        git_dir = parent / ".git"
        if git_dir.exists():
            return parent

    return None


def check_git_consistency(state: RealityAgentState) -> Dict[str, Any]:
    """
    §10 Step 2: Check Git commit consistency between environments.

    Auto-discovers .git by walking upward from current working directory.
    No hardcoded paths. Works in any repo (memguard, memguard-mcp, RDIAgent, etc.).

    Checks:
    1. Current commit hash (git rev-parse --short HEAD)
    2. Working tree status (git status --porcelain) — must be clean for consistency
    3. Latest tag (if any) for version reference

    Returns:
        {
            "tool_outputs": [str],
            "repo_root": str | None,
            "commit_hash": str | None,
            "working_tree_clean": bool,
            "uncommitted_files": List[str],
            "latest_tag": str | None,
            "git_available": bool,
        }
    """
    repo_root = _find_git_root()

    if repo_root is None:
        return {
            "tool_outputs": ["No .git repository found. Walking upward from cwd failed."],
            "repo_root": None,
            "commit_hash": None,
            "working_tree_clean": False,
            "uncommitted_files": [],
            "latest_tag": None,
            "git_available": False,
        }

    def run_git(args: List[str]) -> Tuple[int, str, str]:
        """Helper to run git commands in discovered repo."""
        try:
            result = subprocess.run(
                ["git", "-C", str(repo_root)] + args,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.returncode, result.stdout.strip(), result.stderr.strip()
        except Exception as e:
            return -1, "", str(e)

    # 1. Get commit hash
    code, commit_hash, err = run_git(["rev-parse", "--short", "HEAD"])
    git_available = code == 0

    if not git_available:
        return {
            "tool_outputs": [f"Git command failed: {err}"],
            "repo_root": str(repo_root),
            "commit_hash": None,
            "working_tree_clean": False,
            "uncommitted_files": [],
            "latest_tag": None,
            "git_available": False,
        }

    # 2. Check working tree status
    code, status_out, _ = run_git(["status", "--porcelain"])
    uncommitted = [line.strip() for line in status_out.splitlines() if line.strip()]
    working_tree_clean = len(uncommitted) == 0

    # 3. Get latest tag (if any)
    code, tag_out, _ = run_git(["describe", "--tags", "--abbrev=0"])
    latest_tag = tag_out if code == 0 else None

    summary = (
        f"Git repository: {repo_root}\n"
        f"Commit: {commit_hash}\n"
        f"Working tree clean: {working_tree_clean}\n"
        f"Uncommitted files: {len(uncommitted)}\n"
        f"Latest tag: {latest_tag or 'none'}"
    )

    return {
        "tool_outputs": [summary],
        "repo_root": str(repo_root),
        "commit_hash": commit_hash,
        "working_tree_clean": working_tree_clean,
        "uncommitted_files": uncommitted,
        "latest_tag": latest_tag,
        "git_available": True,
    }


# ---------------------------------------------------------------------------
# §10 Step 2: Environment Check (stub — Phase 4)
# ---------------------------------------------------------------------------

def check_environment(state: RealityAgentState) -> Dict[str, Any]:
    """
    §10 Step 2: Check environment configuration consistency.

    Phase 3: Compares critical env vars. Phase 4: Full config file diff.
    """
    critical_vars = ["RDI_REPRODUCE_COMMAND", "RDI_BENCHMARK_COMMAND", "LLM_PROVIDER", "LLM_MODEL"]
    env_status = {var: os.getenv(var, "NOT SET") for var in critical_vars}

    summary = "Environment variables:\n" + "\n".join(
        f"  {k}: {v}" for k, v in env_status.items()
    )

    return {
        "tool_outputs": [summary],
        "env_status": env_status,
    }


# ---------------------------------------------------------------------------
# §10 Step 3: Differential Test (stub — Phase 4)
# ---------------------------------------------------------------------------

def run_differential_test(old_state: RealityAgentState, new_state: RealityAgentState) -> bool:
    """
    §10 Step 3: Execute differential test after Change One Thing.

    Compares outputs before and after the isolated change.
    Phase 3: returns False (no change applied). Phase 4: real diff.
    """
    # Phase 3: fail-safe — no changes yet
    return False
