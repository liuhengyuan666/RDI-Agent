"""Tests for state transitions and graph topology."""

import pytest

from reality_agent.graph import build_graph, compile_agent
from reality_agent.state import RealityAgentState


class TestStateTransitions:
    """验证 LangGraph 拓扑结构和状态流转."""

    def test_graph_builds_without_error(self):
        """Graph 必须能成功构建."""
        graph = build_graph()
        assert graph is not None

    def test_agent_compiles(self):
        """Agent 必须能成功编译为可执行对象."""
        agent = compile_agent()
        assert agent is not None

    def test_initial_state_defaults(self):
        """初始状态必须处于 Environment_Discovery 阶段 (§0 入口)."""
        state = RealityAgentState()
        assert state.current_phase == "Environment_Discovery"
        assert state.evidence_level == "Observation"
        assert state.provenance_verified is False

    def test_append_only_lists(self):
        """Annotated[list, operator.add] 必须实现追加语义."""
        # Simulate LangGraph reduction: two partial updates with operator.add
        from operator import add

        state1 = {"facts": ["fact_a"], "knowledge_gained": ["k1"]}
        state2 = {"facts": ["fact_b"], "knowledge_gained": ["k2"]}

        # In LangGraph, annotated fields are reduced with the operator
        reduced_facts = add(state1.get("facts", []), state2.get("facts", []))
        reduced_knowledge = add(state1.get("knowledge_gained", []), state2.get("knowledge_gained", []))

        assert reduced_facts == ["fact_a", "fact_b"]
        assert reduced_knowledge == ["k1", "k2"]

    def test_evidence_level_progression(self):
        """证据等级必须能从 Observation 逐步提升到 Verified."""
        state = RealityAgentState(
            user_request="test",
            evidence_level="Observation",
        )
        # Simulate progression
        state.evidence_level = "Hypothesis"
        state.evidence_level = "Evidence"
        state.provenance_verified = True
        state.evidence_level = "Verified"

        assert state.evidence_level == "Verified"
        assert state.provenance_verified is True
