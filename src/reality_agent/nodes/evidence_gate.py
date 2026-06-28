"""Evidence gate node — §4 Evidence Gate (纯逻辑网关)."""

from typing import Any, Dict

from reality_agent.state import RealityAgentState


def evidence_gate_node(state: RealityAgentState) -> Dict[str, Any]:
    """
    §4 Evidence Gate — 核心拦截层.

    This node is a **pure logic gateway** (no LLM call).
    It enforces the tiered interception policy:

    ┌─────────────────────────────────────────────────────────────┐
    │  evidence_level  │  provenance  │  Action                  │
    ├─────────────────────────────────────────────────────────────┤
    │  Observation     │  any         │  → build_knowledge (禁止) │
    │  Hypothesis      │  any         │  → build_knowledge (禁止) │
    │  Evidence        │  False       │  → build_knowledge (禁止) │
    │  Evidence        │  True        │  → isolate_iteration (放行)│
    │  Verified        │  True        │  → isolate_iteration (放行)│
    └─────────────────────────────────────────────────────────────┘

    The routing decision is made by `route_after_gate` in graph.py.
    This node only updates the phase label and appends an audit trail.
    """
    updates: Dict[str, Any] = {"current_phase": "Evidence_Gate"}

    # Audit trail entry
    gate_record = (
        f"EvidenceGate: level={state.evidence_level}, "
        f"provenance={state.provenance_verified}, "
        f"facts={len(state.facts)}, hypotheses={len(state.hypotheses)}"
    )
    updates["knowledge_gained"] = [gate_record]

    return updates
