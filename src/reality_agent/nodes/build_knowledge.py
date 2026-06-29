from typing import Any, Dict

from reality_agent.state import RealityAgentState
from reality_agent.adapters.memory_adapter import get_memory_adapter
from reality_agent.tools.force_patch import force_patch


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
    
    Phase 4: Persists knowledge to MemoryAdapter if --commit is enabled.
    Also checks for force_patch override request in user prompt.
    """
    updates: Dict[str, Any] = {"current_phase": "Build_Knowledge"}

    # Check for force_patch override (user explicitly requests bypass)
    # This is the ONLY way to bypass the Evidence Gate — by adding cognitive debt
    if "force" in state.user_request.lower() or "bypass" in state.user_request.lower():
        patch_desc = f"User requested bypass of Evidence Gate with request: {state.user_request[:100]}"
        force_updates = force_patch(state, patch_desc)
        updates.update(force_updates)
        updates["knowledge_gained"] = [
            f"WARNING: Force patch triggered. {patch_desc}. "
            "Cognitive debt added — Evidence Gate audit must be completed in next session."
        ]
        # Early return with force patch results
        return updates

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
        "code_changes": f"+{state.variables_changed_count} -0 lines" if state.variables_changed_count else "+0 -0 lines (no changes applied)",
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
        f"Phase 4 synthesis complete. Evidence level: {state.evidence_level}. "
        f"Machine probes: static_check={state.static_check_passed}, reproduced={state.reproduced}."
    ]
    
    # Persist knowledge to MemoryAdapter if commit mode is enabled
    adapter = get_memory_adapter()
    if adapter.__class__.__name__ != 'NoopMemoryAdapter':
        adapter.log_iteration_checkpoint({
            "project_id": state.frozen_project_id or "default",
            "knowledge_items": all_knowledge,
            "facts": all_facts,
            "hypotheses": all_hypotheses,
            "evidence_level": state.evidence_level,
            "trap_detected": state.trap_detected,
        })

    return updates
