"""Force patch fallback — §13 Cognitive Debt."""

from typing import Any, Dict

from reality_agent.state import RealityAgentState


def force_patch(state: RealityAgentState, patch_description: str) -> Dict[str, Any]:
    """
    §13 Fallback: Emergency override of the Evidence-First audit.

    This is the ONLY way to bypass the guardrail. It MUST:
    1. Mark `cognitive_debt_added` = True
    2. Record the exact patch in `cognitive_debt_records`
    3. Add a warning comment to the knowledge log

    WARNING: Unverified optimization. Cognitive Debt Added.
    """
    return {
        "cognitive_debt_added": True,
        "cognitive_debt_records": [
            f"FORCE_PATCH: {patch_description}. Bypassed Evidence Gate."
        ],
        "knowledge_gained": [
            "WARNING: Unverified optimization. Cognitive Debt Added. "
            "Evidence Gate audit must be completed in a subsequent session."
        ],
    }
