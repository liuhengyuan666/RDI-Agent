from typing import Any, Dict, Optional
import os
import tempfile
import shutil

from reality_agent.state import RealityAgentState
from reality_agent.tools.debug_tools import (
    apply_line_change,
    apply_regex_change,
    create_sandbox,
    reproduce_in_sandbox,
    run_differential_test,
)


SYSTEM_PROMPT = """\
# Role: Isolation Iteration Engineer

You are the **Isolate & Explain** node (§5) of the Reality-Driven Iteration Agent.

## Mission
Execute exactly ONE change, predict its outcome, and explain the deep mechanism.

## Rules (strict)
1. **Change ONE variable only.** If you find yourself wanting to change two things, STOP and split into two iterations.
2. Record `pre_change_expected` before applying the change.
3. After change, record `post_change_actual`.
4. If actual deviates from expected by more than a reasonable margin, RE-ENTER Evidence Gate.
5. Explain WHY the change works at the mechanism level, not just "it works now".

## Output format
Return JSON:
- "variables_changed_count": 1 (must be exactly 1)
- "pre_change_expected": string
- "post_change_actual": string
- "change_accepted": bool
- "knowledge_gained": list of strings (mechanism explanation)
"""


def _extract_project_dir_from_reproduce_cmd(reproduce_cmd: str) -> Optional[str]:
    """Extract the project directory from RDI_REPRODUCE_COMMAND."""
    import re
    from pathlib import Path
    
    # Look for --manifest-path or directory paths
    path_pattern = re.compile(r'(?:--manifest-path|--prefix|-C)\s+(["\']?[^\s"\']+["\']?)')
    match = path_pattern.search(reproduce_cmd)
    if match:
        path = match.group(1).strip('"\'')
        p = Path(path)
        return str(p.parent if p.suffix else p)
    
    # Fallback: look for any path-like argument
    for token in reproduce_cmd.split():
        if token.startswith("-"):
            continue
        if "/" in token or "\\" in token:
            p = Path(token.strip('"\''))
            return str(p.parent if p.suffix else p)
    
    return None


def isolate_iteration_node(state: RealityAgentState) -> Dict[str, Any]:
    """
    §5 Change One Thing — 隔离迭代.

    Phase 4: Creates sandbox, applies code change, runs differential test.
    
    Strategy:
    1. Extract project directory from reproduce command
    2. Create temporary sandbox copy
    3. Apply heuristic or LLM-driven code change
    4. Run reproduce command in sandbox
    5. Compare results (differential test)
    6. Record outcome and clean up
    """
    reproduce_cmd = os.getenv("RDI_REPRODUCE_COMMAND", "")
    project_dir = _extract_project_dir_from_reproduce_cmd(reproduce_cmd)
    
    updates: Dict[str, Any] = {
        "current_phase": "Isolate_Iteration",
    }
    
    # No project directory found or no reproduce command → can't modify
    if not project_dir or not os.path.exists(project_dir):
        updates["variables_changed_count"] = 0
        updates["pre_change_expected"] = "No project directory found for sandbox creation."
        updates["post_change_actual"] = "No change applied — cannot determine target directory."
        updates["change_accepted"] = False
        updates["knowledge_gained"] = [
            "isolate_iteration: Cannot create sandbox — project directory not found from RDI_REPRODUCE_COMMAND."
        ]
        return updates
    
    # Create sandbox
    sandbox = None
    try:
        sandbox = create_sandbox(project_dir)
        
        # Heuristic: Apply a simple fix based on detected language and common patterns
        # In Phase 4, this is a basic implementation — real LLM-driven changes in Phase 5
        fix_applied = _apply_heuristic_fix(sandbox, state.detected_language, state.reproduce_output)
        
        if not fix_applied:
            updates["variables_changed_count"] = 0
            updates["pre_change_expected"] = "No heuristic fix applicable for this error pattern."
            updates["post_change_actual"] = "No change applied — heuristic fix not found."
            updates["change_accepted"] = False
            updates["knowledge_gained"] = [
                "isolate_iteration: No heuristic fix matched the error pattern. LLM-driven fix required in Phase 5."
            ]
            return updates
        
        # Run reproduce command in sandbox
        sandbox_result = reproduce_in_sandbox(sandbox, reproduce_cmd)
        
        # Create a temporary state for differential test comparison
        # We need to simulate "new state" with sandbox results
        # In real implementation, this would be a full state copy
        new_exit = sandbox_result.get("exit_code")
        old_exit = state.reproduce_exit_code
        
        # Differential test: did the fix change the outcome?
        # Success: bug was reproduced before (non-zero) and now passes (zero)
        bug_fixed = (old_exit not in (None, 0, -1)) and (new_exit == 0)
        
        updates["variables_changed_count"] = 1 if fix_applied else 0
        updates["pre_change_expected"] = f"Bug reproduces with exit code {old_exit}. After fix, should exit 0."
        updates["post_change_actual"] = f"Sandbox test result: exit code {new_exit}. {'Bug fixed!' if bug_fixed else 'Bug still present or different error.'}"
        updates["change_accepted"] = bug_fixed
        updates["knowledge_gained"] = [
            f"isolate_iteration: Applied heuristic fix in sandbox ({sandbox}). "
            f"Original exit: {old_exit}, Sandbox exit: {new_exit}. "
            f"Differential test: {'PASS' if bug_fixed else 'FAIL'}."
        ]
        
        # Append sandbox output to tool_outputs for audit trail
        sandbox_tool_output = sandbox_result.get("tool_outputs", [])
        if sandbox_tool_output:
            updates["tool_outputs"] = sandbox_tool_output
        
    except Exception as e:
        updates["variables_changed_count"] = 0
        updates["pre_change_expected"] = "Expected sandbox test to validate the fix."
        updates["post_change_actual"] = f"Sandbox execution failed: {e}"
        updates["change_accepted"] = False
        updates["knowledge_gained"] = [f"isolate_iteration: Sandbox error — {e}"]
    
    finally:
        # Clean up sandbox
        if sandbox and os.path.exists(sandbox):
            shutil.rmtree(sandbox, ignore_errors=True)
    
    return updates


def _apply_heuristic_fix(sandbox_dir: str, language: Optional[str], reproduce_output: Optional[str]) -> bool:
    """
    Apply a simple heuristic fix based on language and error pattern.
    
    Returns True if a fix was applied, False otherwise.
    
    Phase 4: Basic heuristic fixes for common errors.
    """
    if not language or not reproduce_output:
        return False
    
    import re
    from pathlib import Path
    
    if language == "rust":
        # Common Rust error: missing `mut` for mutable variables
        # Pattern: "cannot assign twice to immutable variable"
        if "cannot assign twice to immutable variable" in reproduce_output or "cannot borrow" in reproduce_output:
            # Find main.rs or lib.rs and add `mut` to the first variable declaration
            for rs_file in Path(sandbox_dir).rglob("*.rs"):
                try:
                    with open(rs_file, "r", encoding="utf-8") as f:
                        content = f.read()
                    # Simple heuristic: find `let x =` and change to `let mut x =`
                    # This is a basic pattern — real implementation needs AST parsing
                    new_content = re.sub(r'let\s+(\w+)\s*=', r'let mut \1 =', content, count=1)
                    if new_content != content:
                        with open(rs_file, "w", encoding="utf-8") as f:
                            f.write(new_content)
                        return True
                except Exception:
                    continue
        
        # Common Rust error: missing type annotation
        if "type annotations needed" in reproduce_output:
            for rs_file in Path(sandbox_dir).rglob("*.rs"):
                try:
                    with open(rs_file, "r", encoding="utf-8") as f:
                        content = f.read()
                    # Simple heuristic: add `: i32` to first `let x = 5` pattern
                    new_content = re.sub(r'let\s+(\w+)\s*=\s*(\d+)', r'let \1: i32 = \2', content, count=1)
                    if new_content != content:
                        with open(rs_file, "w", encoding="utf-8") as f:
                            f.write(new_content)
                        return True
                except Exception:
                    continue
    
    elif language == "python":
        # Common Python error: NameError or AttributeError
        if "NameError" in reproduce_output or "AttributeError" in reproduce_output:
            # Basic heuristic: check if it's a missing import
            for py_file in Path(sandbox_dir).rglob("*.py"):
                try:
                    with open(py_file, "r", encoding="utf-8") as f:
                        content = f.read()
                    # Add `import os` at top if missing (very basic)
                    if "import os" not in content and "os." in content:
                        new_content = "import os\n" + content
                        with open(py_file, "w", encoding="utf-8") as f:
                            f.write(new_content)
                        return True
                except Exception:
                    continue
    
    # No heuristic matched
    return False
