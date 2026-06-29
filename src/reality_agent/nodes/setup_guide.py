"""Setup Guide Node — Infrastructure Missing (§0).

When toolchain is unavailable, generates a human-readable setup guide.
This node is terminal: it never leads to code modification."""

from typing import Any, Dict

from reality_agent.state import RealityAgentState


def setup_guide_node(state: RealityAgentState) -> Dict[str, Any]:
    """
    §0 Setup Guide — Terminal node for missing infrastructure.

    This node is reached when environment_discovery detects a missing toolchain.
    It simply echoes the setup_plan into knowledge_gained and ends.

    Design principle: No sys.exit inside LangGraph nodes. Exit code 4 is
    triggered by cli.py final state inspection.
    """
    plan = state.setup_plan or (
        "[RDI Environment Alert] Toolchain unavailable. "
        "No setup guide was generated. Please check your environment."
    )

    return {
        "current_phase": "Setup_Guide",
        "knowledge_gained": [plan],
    }
