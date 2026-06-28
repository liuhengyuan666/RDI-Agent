"""Reality check node — Verify Reality (§2)."""

import os
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from reality_agent.llm import get_llm
from reality_agent.state import RealityAgentState


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

class RealityCheckBrainOutput(BaseModel):
    """
    §2 Verify Reality — 结构化大脑输出.

    大模型必须通过 with_structured_output 生成此 Schema，
    确保 facts / hypotheses / evidence_level 的严格分离。
    """
    is_reproduced: bool = Field(
        description="通过分析工具链输出，确认现象是否真实复现"
    )
    facts: List[str] = Field(
        description="从日志中提取的、不容置疑的客观事实（如具体报错行、错误码）"
    )
    hypotheses: List[str] = Field(
        description="人类或大模型推测的可能原因，尚未被证实的假设"
    )
    evidence_level: Literal["Observation", "Hypothesis", "Evidence", "Verified"] = Field(
        description="当前证据等级"
    )
    trap_detected: Optional[str] = Field(
        default=None,
        description="检测到的陷阱类型: Explanation|MetricWorship|Narrative|Recency|Confirmation|PrematureTuning"
    )
    trap_details: Optional[str] = Field(
        default=None,
        description="陷阱的具体描述与拦截理由"
    )


SYSTEM_PROMPT = _load_prompt("reality_check")


# ---------------------------------------------------------------------------
# Heuristic fallback — 当 LLM 不可用时使用
# ---------------------------------------------------------------------------

def _heuristic_reality_check(state: RealityAgentState) -> Dict[str, Any]:
    """Phase 2 heuristic stub when LLM is unavailable."""
    updates: Dict[str, Any] = {"current_phase": "Reality_Check"}

    if not state.raw_logs and not state.tool_outputs:
        updates["facts"] = ["User reported an issue without attached logs or traces."]
        updates["hypotheses"] = ["The issue exists in the described environment."]
        updates["evidence_level"] = "Observation"
        updates["trap_detected"] = "Explanation"
        updates["trap_details"] = "No logs provided. Request is explanation-driven."
    else:
        # Check if reproduce_issue tool succeeded
        reproduced = any("BUG REPRODUCED" in str(o) for o in state.tool_outputs)
        if reproduced:
            updates["facts"] = ["Bug was successfully reproduced by automated tool."]
            updates["evidence_level"] = "Verified"
        else:
            updates["facts"] = ["Logs have been provided and are available for inspection."]
            updates["evidence_level"] = "Hypothesis"
        updates["hypotheses"] = ["The root cause is in the module described by the user."]

    return updates


# ---------------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------------

def reality_check_node(state: RealityAgentState) -> Dict[str, Any]:
    """
    §2 Verify Reality — 确认现象真实存在.

    Phase 4: If LLM is configured (RDI_LLM_MODE=real), uses structured output
    to force the model to produce facts/hypotheses separation.
    Otherwise falls back to heuristic stub.
    """
    # Check if LLM mode is enabled
    if os.getenv("RDI_LLM_MODE", "stub").lower() != "real":
        return _heuristic_reality_check(state)

    try:
        llm = get_llm()
        structured_llm = llm.with_structured_output(RealityCheckBrainOutput)

        # Build context from state
        context = f"""User request: {state.user_request}

Available logs:
{chr(10).join(f"- {log}" for log in state.raw_logs) if state.raw_logs else "(none)"}

Tool outputs:
{chr(10).join(f"- {out}" for out in state.tool_outputs) if state.tool_outputs else "(none)"}
"""

        result: RealityCheckBrainOutput = structured_llm.invoke(
            [
                ("system", SYSTEM_PROMPT),
                ("human", context),
            ]
        )

        return {
            "current_phase": "Reality_Check",
            "facts": result.facts,
            "hypotheses": result.hypotheses,
            "evidence_level": result.evidence_level,
            "trap_detected": result.trap_detected,
            "trap_details": result.trap_details,
            "knowledge_gained": [
                f"LLM structured output: is_reproduced={result.is_reproduced}, "
                f"evidence_level={result.evidence_level}, facts={len(result.facts)}"
            ],
        }
    except Exception as e:
        # Fail-safe: if LLM call fails, fall back to heuristic
        fallback = _heuristic_reality_check(state)
        fallback["knowledge_gained"] = [
            f"LLM call failed ({e}), falling back to heuristic. "
            "Consider checking LLM_PROVIDER / LLM_API_KEY configuration."
        ]
        return fallback
