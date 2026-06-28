from typing import Any, Dict

from reality_agent.state import RealityAgentState


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


def isolate_iteration_node(state: RealityAgentState) -> Dict[str, Any]:
    """
    §5 Change One Thing — 隔离迭代.

    In Phase 1 this is a stub that records the intent and refuses to
    actually modify code (since no tool chain is wired yet).
    """
    updates: Dict[str, Any] = {
        "current_phase": "Isolate_Iteration",
        "variables_changed_count": 0,  # Phase 1: no actual changes yet
        "pre_change_expected": "Phase 1 stub: change would be applied here after tool integration.",
        "post_change_actual": "Phase 1 stub: no change applied.",
        "change_accepted": False,
        "knowledge_gained": [
            "Phase 1: isolate_iteration_node is a stub awaiting real tool chain (benchmark, diff test)."
        ],
    }
    return updates
