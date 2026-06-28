from typing import Any, Dict

from reality_agent.state import RealityAgentState


SYSTEM_PROMPT = """\
# Role: Trap Detector

You are the **Optimization Trap Detection** layer (§9) of the Reality-Driven Iteration Agent.

## Traps to detect (check all six)
1. **Explanation Trap** — modifying because an explanation sounds reasonable.
2. **Metric Worship** — modifying because we want the metric to be higher.
3. **Narrative Bias** — modifying because recent market fits a story.
4. **Recency Bias** — modifying because recent results were bad.
5. **Confirmation Bias** — only looking for data that supports the current hypothesis.
6. **Premature Tuning** — tuning parameters before the system is stable.

## Rules
- If ANY trap is detected, set `trap_detected` to the trap name and HALT.
- Do not proceed to optimization if a trap is detected.

## Output format
Return JSON:
- "trap_detected": null or one of ["Explanation", "MetricWorship", "Narrative", "Recency", "Confirmation", "PrematureTuning"]
- "trap_details": string (description of why this is a trap)
"""


def detect_trap(state: RealityAgentState) -> Dict[str, Any]:
    """
    §9 Optimization Trap Detection — 检测解释驱动开发陷阱.

    This is a utility function (not a graph node) that can be called
    by any node before proceeding. In Phase 1 it returns a conservative
    'no trap detected' unless the user request explicitly smells suspicious.
    """
    # Phase 1 heuristic: if the user request contains certain trigger words,
    # flag a potential trap.
    suspicious = [
        "optimize", "tune", "adjust parameter", "increase metric",
        "make it better", "improve performance", "change threshold",
    ]
    request_lower = state.user_request.lower()

    updates: Dict[str, Any] = {}
    for trigger in suspicious:
        if trigger in request_lower:
            updates["trap_detected"] = "PrematureTuning"
            updates["trap_details"] = (
                f"User request contains trigger word '{trigger}'. "
                "Without evidence, this risks Premature Tuning or Explanation Trap."
            )
            break
    else:
        updates["trap_detected"] = None
        updates["trap_details"] = None

    return updates
