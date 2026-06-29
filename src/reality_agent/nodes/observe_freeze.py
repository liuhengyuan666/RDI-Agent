from typing import Any, Dict

from reality_agent.state import RealityAgentState
from reality_agent.adapters.memory_adapter import get_memory_adapter


def observe_freeze_node(state: RealityAgentState) -> Dict[str, Any]:
    """
    §7 Freeze And Observe — 观察期.

    When the system is stable and all critical issues are resolved,
    enter the observation freeze. No parameter tuning, no core logic changes.

    Phase 4: Persists freeze state to MemoryAdapter (if not noop) and
    uses the actual project_id from state (not hardcoded).
    """
    project_id = state.frozen_project_id or "default"
    
    updates: Dict[str, Any] = {
        "current_phase": "Observe_Freeze",
        "freeze_reason": "System reached stable state after Evidence-First audit.",
        "frozen_project_id": project_id,
    }

    updates["knowledge_gained"] = [
        "Entering observation freeze. Monitoring, logging, and observability improvements are allowed. "
        "Parameter tuning, threshold adjustment, and core logic changes are PROHIBITED."
    ]
    
    # Persist freeze to MemoryAdapter if not noop
    adapter = get_memory_adapter()
    if adapter.__class__.__name__ != 'NoopMemoryAdapter':
        adapter.log_freeze(
            project_id=project_id,
            freeze_until=state.freeze_until or "",
            reason=state.freeze_reason or "System reached stable state after Evidence-First audit.",
        )

    return updates
