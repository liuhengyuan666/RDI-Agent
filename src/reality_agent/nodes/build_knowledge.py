from typing import Any, Dict

from reality_agent.state import RealityAgentState


SYSTEM_PROMPT = """\
# Role: Knowledge Architect

You are the **Build Knowledge** node (§6) of the Reality-Driven Iteration Agent.

## Mission
Turn every iteration into a permanent asset of understanding.

## Mandatory Questions (must answer all)
1. What did we discover? — New objective facts about the system.
2. What did we rule out? — Falsified hypotheses that should never be tried again.
3. Which assumption was disproven? — Explicit record to prevent future repeated mistakes.
4. Which knowledge can be permanently沉淀? — Reusable system understanding.

## Output format
Return JSON:
- "knowledge_gained": list of strings (each must be a reusable insight)
- "falsified_hypotheses": list of strings
- "iteration_summary": {
    "code_changes": "+X -Y lines",
    "understanding_gained": "string (must be non-empty)",
    "evidence_level": "Observation|Hypothesis|Evidence|Verified",
    "trap_detected": "None|Explanation|MetricWorship|...",
    "phase_recommendation": "Continue|Observe|Stop"
  }
"""


def build_knowledge_node(state: RealityAgentState) -> Dict[str, Any]:
    """
    §6 Build Knowledge — 记录理解增量.

    This node synthesizes everything learned so far and emits the
    structured observability log required by §11.
    """
    updates: Dict[str, Any] = {"current_phase": "Build_Knowledge"}

    # Aggregate knowledge from previous nodes (since lists are append-only)
    all_facts = state.facts
    all_hypotheses = state.hypotheses
    all_knowledge = state.knowledge_gained

    # Determine recommendation based on evidence level
    if state.evidence_level == "Observation":
        recommendation = "Stop"
    elif state.evidence_level == "Hypothesis":
        recommendation = "Stop"
    elif state.evidence_level == "Evidence" and not state.provenance_verified:
        recommendation = "Stop"
    elif state.evidence_level in ("Evidence", "Verified") and state.provenance_verified:
        recommendation = "Observe"
    else:
        recommendation = "Continue"

    # Build the §11 structured log
    iteration_summary = {
        "code_changes": "+0 -0 lines (Phase 1 stub)",
        "understanding_gained": (
            f"Accumulated {len(all_facts)} facts, {len(all_hypotheses)} hypotheses, "
            f"{len(all_knowledge)} knowledge items."
        ),
        "evidence_level": state.evidence_level,
        "trap_detected": state.trap_detected or "无",
        "phase_recommendation": recommendation,
    }

    updates["iteration_summary"] = iteration_summary
    updates["knowledge_gained"] = [
        f"Phase 1 synthesis complete. Evidence level: {state.evidence_level}."
    ]

    return updates
