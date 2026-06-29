"""Measurement check node — Verify Measurement (§3)."""

import os
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from reality_agent.llm import get_llm
from reality_agent.state import RealityAgentState
from reality_agent.tools.debug_tools import check_git_consistency


# ---------------------------------------------------------------------------
# Prompt Loader: 运行时动态读取外部 .txt 资源
# ---------------------------------------------------------------------------

def _load_prompt(name: str) -> str:
    """
    Load a prompt template from the prompts/ directory.

    Resolution order:
    1. src/reality_agent/prompts/{name}.txt (dev mode)
    2. reality_agent/prompts/{name}.txt (installed package)
    3. Fallback to hardcoded inline prompt (last resort, emits warning)
    """
    import importlib.resources

    try:
        text = importlib.resources.read_text("reality_agent.prompts", f"{name}.txt")
        return text
    except (ImportError, FileNotFoundError, OSError):
        pass

    script_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(script_dir, "..", "prompts", f"{name}.txt")
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    return f"# WARNING: Prompt '{name}' not found at runtime. Using fallback.\n"


# ---------------------------------------------------------------------------
# Structured Output Schema — Pydantic 强控 LLM 输出格式
# ---------------------------------------------------------------------------

class MeasurementCheckBrainOutput(BaseModel):
    """
    §3 Verify Measurement — 结构化大脑输出.

    大模型必须通过 with_structured_output 生成此 Schema，
    确保 provenance 四项检查全部回答，不遗漏。
    """
    provenance_verified: bool = Field(
        description="所有数据来源、时间窗口、版本、快照是否全部验证一致"
    )
    data_sources_aligned: Optional[bool] = Field(
        default=None,
        description="Dashboard / Backtest / Report / DB 数字是否指向同一数据源"
    )
    time_window_aligned: Optional[bool] = Field(
        default=None,
        description="不同系统的观测时间是否对齐"
    )
    version_aligned: Optional[bool] = Field(
        default=None,
        description="代码版本、数据版本、配置版本是否一致"
    )
    snapshot_fresh: Optional[bool] = Field(
        default=None,
        description="缓存/快照是否已过期"
    )
    knowledge_gained: List[str] = Field(
        default_factory=list,
        description="关于测量口径一致性的新理解"
    )
    audit_reason: Optional[str] = Field(
        default=None,
        description="如果 provenance_verified=False，说明哪一项不一致及原因"
    )


SYSTEM_PROMPT = _load_prompt("measurement_check")


# ---------------------------------------------------------------------------
# Heuristic fallback — 当 LLM 不可用时使用
# ---------------------------------------------------------------------------

def _heuristic_measurement_check(state: RealityAgentState) -> Dict[str, Any]:
    """Phase 2 heuristic stub when LLM is unavailable."""
    updates: Dict[str, Any] = {"current_phase": "Measurement_Check"}

    # Default conservative: unverified until tools provide real data
    updates["data_sources_aligned"] = None
    updates["time_window_aligned"] = None
    updates["version_aligned"] = None
    updates["snapshot_fresh"] = None
    updates["provenance_verified"] = False

    # Check if git consistency tool found dirty working tree
    git_dirty = any(
        "working tree clean: False" in str(o) or "Uncommitted files" in str(o)
        for o in state.tool_outputs
    )
    if git_dirty:
        updates["version_aligned"] = False
        updates["knowledge_gained"] = [
            "Git working tree is dirty. Code version may not match production."
        ]
    else:
        updates["knowledge_gained"] = [
            "Phase 2 heuristic: measurement tools not yet integrated. Defaulting to conservative unverified state."
        ]

    return updates


# ---------------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------------

def measurement_check_node(state: RealityAgentState) -> Dict[str, Any]:
    """
    §3 Verify Measurement — 确认测量可信.

    Phase 4: If LLM is configured (RDI_LLM_MODE=real), uses structured output
    to force the model to answer all four provenance checks.
    Otherwise falls back to heuristic stub.
    """
    if os.getenv("RDI_LLM_MODE", "stub").lower() != "real":
        return _heuristic_measurement_check(state)

    try:
        # Execute git consistency check before LLM analysis
        # This provides physical evidence about version alignment
        updates: Dict[str, Any] = {}
        git_result = check_git_consistency(state)
        
        # Append git check results to tool outputs for audit trail
        git_tool_output = git_result.get("tool_outputs", [])
        if git_tool_output:
            updates["tool_outputs"] = git_tool_output
        
        llm = get_llm()
        structured_llm = llm.with_structured_output(MeasurementCheckBrainOutput)

        context = f"""Evidence level: {state.evidence_level}
Verified facts:
{chr(10).join(f"- {f}" for f in state.facts) if state.facts else "(none)"}

Tool outputs:
{chr(10).join(f"- {o}" for o in state.tool_outputs) if state.tool_outputs else "(none)"}

Git consistency:
{chr(10).join(f"- {o}" for o in git_tool_output) if git_tool_output else "(not checked)"}
"""

        result: MeasurementCheckBrainOutput = structured_llm.invoke(
            [
                ("system", SYSTEM_PROMPT),
                ("human", context),
            ]
        )

        # Merge LLM result with updates (which may contain tool_outputs from git check)
        llm_updates = {
            "current_phase": "Measurement_Check",
            "provenance_verified": result.provenance_verified,
            "data_sources_aligned": result.data_sources_aligned,
            "time_window_aligned": result.time_window_aligned,
            "version_aligned": result.version_aligned,
            "snapshot_fresh": result.snapshot_fresh,
            "knowledge_gained": result.knowledge_gained + [
                f"LLM audit: provenance_verified={result.provenance_verified}. "
                f"Reason: {result.audit_reason or 'all checks passed'}"
            ],
        }
        updates.update(llm_updates)
        return updates
    except Exception as e:
        fallback = _heuristic_measurement_check(state)
        fallback["knowledge_gained"] = [
            f"LLM call failed ({e}), falling back to heuristic. "
            "Consider checking LLM_PROVIDER / LLM_API_KEY configuration."
        ]
        return fallback
