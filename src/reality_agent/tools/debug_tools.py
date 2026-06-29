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
DEFAULT_STATIC_COMMAND = "echo 'No RDI_STATIC_COMMAND set. Set to cargo check / go build / python -m compileall . / npm run build etc.'"
DEFAULT_BENCHMARK_COMMAND = "echo 'No RDI_BENCHMARK_COMMAND set. Please configure benchmark.'"


# ---------------------------------------------------------------------------
# §0 Zero-Config: Environment Discovery
# ---------------------------------------------------------------------------

def discover_project_language(search_dirs: Optional[List[str]] = None) -> str:
    """
    Zero-Config: Auto-discover project language by physical feature markers.
    
    Scans the provided directories (or os.getcwd() if none) for well-known 
    manifest files (Cargo.toml, go.mod, pyproject.toml, package.json). 
    Returns the detected language or 'unknown'.
    
    For monorepos with multiple markers, returns 'polyglot' (leaves to LLM 
    or human for secondary intent classification).
    
    Args:
        search_dirs: List of directories to scan. If None, scans cwd only.
    """
    import os
    from pathlib import Path
    
    if search_dirs is None:
        search_dirs = [os.getcwd()]
    
    markers = {
        "rust": ["Cargo.toml", "Cargo.lock"],
        "go": ["go.mod", "go.sum"],
        "python": ["pyproject.toml", "requirements.txt", "setup.py", "Pipfile"],
        "node": ["package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"],
    }
    
    found = []
    for dir_path in search_dirs:
        cwd = Path(dir_path)
        if not cwd.exists():
            continue
        for lang, files in markers.items():
            if any((cwd / f).exists() for f in files):
                if lang not in found:
                    found.append(lang)
        # Return immediately if we found exactly one language in this directory
        # This prioritizes earlier directories (target dir over cwd fallback)
        if len(found) == 1:
            return found[0]
    
    if not found:
        return "unknown"
    if len(found) == 1:
        return found[0]
    return "polyglot"


def verify_toolchain_executable(lang: str) -> tuple[bool, str]:
    """
    Verify toolchain executable exists in system PATH via shutil.which.
    
    Returns:
        (available: bool, path_or_reason: str)
    """
    import shutil
    
    executables = {
        "rust": "cargo",
        "go": "go",
        "python": "python",
        "node": "node",
    }
    
    exe = executables.get(lang)
    if not exe:
        # Unknown or generic language: default to available (user must specify command manually)
        return True, ""
    
    path = shutil.which(exe)
    if path:
        return True, path
    return False, f"Missing {exe} in system PATH."


# ---------------------------------------------------------------------------
# §0.5 Step 0: Static Check Probe (before LLM / runtime)
# ---------------------------------------------------------------------------

def run_static_check(detected_language: Optional[str] = None) -> dict[str, Any]:
    """
    First-order probe: compile / static check command.
    
    Priority:
    1. RDI_STATIC_COMMAND env var (explicit user override)
    2. Auto-inferred from detected_language (Zero-Config)
    
    Timeout: RDI_STATIC_TIMEOUT (default 60s) for heavy compilation.
    
    If exit code != 0: compiler error is iron-clad evidence — evidence_level
    should be forced to 'Evidence' and runtime probe should be skipped.
    """
    import os
    import subprocess
    
    # Priority 1: explicit user override
    explicit_cmd = os.getenv("RDI_STATIC_COMMAND")
    
    # Priority 2: auto-infer from detected language
    lang = detected_language or "unknown"
    auto_cmds = {
        "rust": "cargo check --message-format=json",
        "go": "go build ./...",
        "python": "python -m compileall .",  # Corrected: compileall recursively compiles .py files
        "node": "npm run build",
        "polyglot": None,
        "unknown": None,
    }
    auto_cmd = auto_cmds.get(lang)
    
    if explicit_cmd:
        cmd = explicit_cmd
    elif auto_cmd:
        cmd = auto_cmd
    else:
        return {
            "tool_outputs": ["Static check: no explicit RDI_STATIC_COMMAND and language not recognized. Skipping."],
            "static_check_passed": None,
            "static_stdout": "",
            "static_stderr": "",
            "exit_code": 0,
        }
    
    timeout = int(os.getenv("RDI_STATIC_TIMEOUT", "60"))
    
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            "tool_outputs": [f"ERROR: Static check timed out after {timeout}s."],
            "static_check_passed": False,
            "static_stdout": "",
            "static_stderr": f"Command timed out after {timeout}s",
            "exit_code": -2,
        }
    except Exception as e:
        return {
            "tool_outputs": [f"ERROR: Static check execution failed: {e}"],
            "static_check_passed": False,
            "static_stdout": "",
            "static_stderr": str(e),
            "exit_code": -3,
        }
    
    passed = result.returncode == 0
    summary = (
        f"Static check: {'PASS' if passed else 'FAIL'} (exit {result.returncode})\n"
        f"Command: {cmd}\n"
        f"stdout length: {len(result.stdout)} chars\n"
        f"stderr length: {len(result.stderr)} chars"
    )
    
    return {
        "tool_outputs": [summary],
        "static_check_passed": passed,
        "static_stdout": result.stdout,
        "static_stderr": result.stderr,
        "exit_code": result.returncode,
    }


# ---------------------------------------------------------------------------
# §10 Step 1: Reproduce Issue (Runtime Execution Probe)
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
# §10 Step 3: Differential Test (Phase 4 — real implementation)
# ---------------------------------------------------------------------------

def run_differential_test(old_state: RealityAgentState, new_state: RealityAgentState) -> bool:
    """
    §10 Step 3: Execute differential test after Change One Thing.
    
    Compares reproduce command outputs before and after the isolated change.
    If the new output differs from the old output in a way that suggests
    the bug is fixed (exit code changed from non-zero to zero), returns True.
    
    Phase 4: Real diff using reproduce_exit_code comparison.
    """
    # Compare reproduce exit codes: old (non-zero = bug) vs new (zero = fixed)
    old_exit = old_state.reproduce_exit_code
    new_exit = new_state.reproduce_exit_code
    
    # Bug was reproduced before (non-zero) and now passes (zero) → success
    if old_exit not in (None, 0, -1) and new_exit == 0:
        return True
    
    # If no reproduce data available, fall back to checking if any tool output changed
    old_outputs = "\n".join(old_state.tool_outputs)
    new_outputs = "\n".join(new_state.tool_outputs)
    if old_outputs != new_outputs:
        # Output changed — could be fix or could be different error
        # Conservative: return False (requires human review)
        return False
    
    # No change detected — modification had no effect
    return False


# ---------------------------------------------------------------------------
# §5 Change One Thing: Code Modification Tools (Phase 4)
# ---------------------------------------------------------------------------

import shutil
import tempfile


def create_sandbox(project_dir: str) -> str:
    """
    Create a temporary sandbox copy of the project directory.
    
    Returns:
        Path to the sandbox directory (caller is responsible for cleanup).
    """
    sandbox = tempfile.mkdtemp(prefix="rdi-sandbox-")
    # Copy project contents to sandbox
    for item in os.listdir(project_dir):
        src = os.path.join(project_dir, item)
        dst = os.path.join(sandbox, item)
        if os.path.isdir(src):
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns('.git', 'target', '__pycache__', 'node_modules'))
        else:
            shutil.copy2(src, dst)
    return sandbox


def apply_line_change(file_path: str, line_num: int, new_content: str) -> bool:
    """
    Replace a specific line in a file (1-indexed).
    
    Returns:
        True if change was applied, False if line number out of range.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        if line_num < 1 or line_num > len(lines):
            return False
        
        # Ensure newline
        if not new_content.endswith("\n"):
            new_content += "\n"
        lines[line_num - 1] = new_content
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        return True
    except Exception:
        return False


def apply_regex_change(file_path: str, pattern: str, replacement: str) -> bool:
    """
    Apply regex replacement to file content.
    
    Returns:
        True if at least one match was replaced, False otherwise.
    """
    import re
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        new_content, count = re.subn(pattern, replacement, content)
        if count == 0:
            return False
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return True
    except Exception:
        return False


def reproduce_in_sandbox(sandbox_dir: str, reproduce_cmd: str) -> Dict[str, Any]:
    """
    Run the reproduce command inside the sandbox directory.
    
    The reproduce command is expected to be a relative path or use the sandbox
    directory as working directory.
    
    Returns dict compatible with reproduce_issue output format.
    """
    import subprocess
    
    try:
        result = subprocess.run(
            reproduce_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=sandbox_dir,
        )
    except subprocess.TimeoutExpired:
        return {
            "tool_outputs": ["ERROR: Reproduce command timed out after 300s in sandbox."],
            "reproduced": False,
            "exit_code": -2,
            "stdout": "",
            "stderr": "Command timed out",
            "command": reproduce_cmd,
        }
    except Exception as e:
        return {
            "tool_outputs": [f"ERROR: Failed to execute reproduce command in sandbox: {e}"],
            "reproduced": False,
            "exit_code": -3,
            "stdout": "",
            "stderr": str(e),
            "command": reproduce_cmd,
        }
    
    reproduced = result.returncode != 0
    output_summary = (
        f"Sandbox command: {reproduce_cmd}\n"
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
        "command": reproduce_cmd,
    }
