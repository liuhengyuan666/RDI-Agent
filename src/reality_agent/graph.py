"""Reality-Driven Agent — LangGraph topology and conditional routing."""

import os
from typing import Any, Dict, Literal, Optional

from langgraph.graph import END, StateGraph

from reality_agent.adapters.memory_adapter import get_memory_adapter
from reality_agent.llm import get_llm
from reality_agent.nodes.environment_discovery import environment_discovery_node
from reality_agent.nodes.setup_guide import setup_guide_node
from reality_agent.nodes.build_knowledge import build_knowledge_node
from reality_agent.nodes.evidence_gate import evidence_gate_node
from reality_agent.nodes.isolate_iteration import isolate_iteration_node
from reality_agent.nodes.measurement_check import measurement_check_node
from reality_agent.nodes.observe_freeze import observe_freeze_node
from reality_agent.nodes.reality_check import reality_check_node
from reality_agent.state import RealityAgentState



def build_graph() -> StateGraph:
    """Construct the 7-step Reality-Driven Iteration graph (with §0 Environment Discovery)."""
    workflow = StateGraph(RealityAgentState)

    # Register all nodes
    workflow.add_node("environment_discovery", environment_discovery_node)
    workflow.add_node("setup_guide", setup_guide_node)
    workflow.add_node("verify_reality", reality_check_node)
    workflow.add_node("verify_measurement", measurement_check_node)
    workflow.add_node("evidence_gate", evidence_gate_node)
    workflow.add_node("isolate_iteration", isolate_iteration_node)
    workflow.add_node("build_knowledge", build_knowledge_node)
    workflow.add_node("observe_freeze", observe_freeze_node)

    # Fixed entry point (§0)
    workflow.set_entry_point("environment_discovery")

    # Conditional routing after discovery (§0 Zero-Config)
    workflow.add_conditional_edges(
        "environment_discovery",
        route_after_discovery,
        {
            "verify_reality": "verify_reality",
            "setup_guide": "setup_guide",
        },
    )

    # Setup guide is terminal
    workflow.add_edge("setup_guide", END)

    # Sequential edges (§2 → §3 → §4)
    workflow.add_edge("verify_reality", "verify_measurement")
    workflow.add_edge("verify_measurement", "evidence_gate")

    # Conditional routing after Evidence Gate (§4 分级拦截策略)
    workflow.add_conditional_edges(
        "evidence_gate",
        route_after_gate,
        {
            "isolate_iteration": "isolate_iteration",
            "build_knowledge": "build_knowledge",
            "observe_freeze": "observe_freeze",
        },
    )

    # After isolation, always build knowledge (§5 → §6)
    workflow.add_edge("isolate_iteration", "build_knowledge")

    # After build_knowledge, decide next phase (§6 → §7 or END)
    workflow.add_conditional_edges(
        "build_knowledge",
        route_after_knowledge,
        {
            "observe_freeze": "observe_freeze",
            "end": END,
        },
    )

    # Observe freeze can end or loop back (future: reopen with evidence)
    workflow.add_edge("observe_freeze", END)

    return workflow


def compile_agent() -> Any:
    """Compile and return the runnable agent."""
    graph = build_graph()
    return graph.compile()


# ---------------------------------------------------------------------------
# Routing logic — hard-coded guardrails (§0, §4)
# ---------------------------------------------------------------------------

def route_after_discovery(state: RealityAgentState) -> Literal["verify_reality", "setup_guide"]:
    """
    §0 Environment Discovery — hard-cut if toolchain is missing.

    If toolchain_available is False: route to setup_guide (terminal node).
    If True: proceed to verify_reality (normal flow).
    """
    if not state.toolchain_available:
        return "setup_guide"
    return "verify_reality"


def route_after_gate(state: RealityAgentState) -> Literal["isolate_iteration", "build_knowledge", "observe_freeze"]:
    """
    §4 Evidence Gate — 分级拦截策略.

    Strict routing logic (no LLM involved here).
    v1 严格拦截：哪怕 Evidence_Level == "Verified"，也必须 provenance_verified=True。
    """
    # 最高优先级：检查运行时 freeze 状态（当前会话）或持久化 ledger（跨会话）
    if state.freeze_until is not None:
        return "observe_freeze"

    adapter = get_memory_adapter()
    frozen, freeze_reason = adapter.is_project_frozen(state.frozen_project_id or "default")
    if frozen:
        return "observe_freeze"

    # 核心防线：没有 provenance_verified，一切免谈
    if not state.provenance_verified:
        return "build_knowledge"

    # 测量已验证，按证据等级分流
    if state.evidence_level in ("Evidence", "Verified"):
        return "isolate_iteration"

    # 保守兜底：Observation / Hypothesis → 禁止修改
    return "build_knowledge"


def route_after_knowledge(state: RealityAgentState) -> Literal["observe_freeze", "end"]:
    """
    §6 Build Knowledge → §7 Freeze And Observe 或 §12 Exit Rule.
    """
    adapter = get_memory_adapter()

    # 如果触发了 force_patch 降级，不进入观察期，直接结束（产生认知债务）
    if state.cognitive_debt_added:
        adapter.log_cognitive_debt({
            "project_id": state.frozen_project_id or "default",
            "reason": "Force patch bypassed Evidence Gate",
            "patch_description": state.cognitive_debt_records[-1] if state.cognitive_debt_records else "unknown",
        })
        return "end"

    # 判断是否满足观察期条件
    stable = (
        state.provenance_verified
        and state.trap_detected is None
        and state.change_accepted is True
    )

    if stable:
        adapter.log_freeze(
            project_id=state.frozen_project_id or "default",
            freeze_until=state.freeze_until or "",
            reason=state.freeze_reason or "System reached stable state after Evidence-First audit.",
        )
        return "observe_freeze"

    # 否则直接结束本轮
    return "end"
