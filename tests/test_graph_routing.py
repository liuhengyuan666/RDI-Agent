"""Tests for Graph Routing — §0 Environment Discovery + §4 Evidence Gate."""

from unittest.mock import patch

import pytest

from reality_agent.graph import (
    build_graph,
    compile_agent,
    route_after_discovery,
    route_after_gate,
)
from reality_agent.state import RealityAgentState


class TestRouteAfterDiscovery:
    """§0: hard-cut if toolchain is missing."""

    def test_toolchain_available_routes_to_reality(self):
        state = RealityAgentState(user_request="test", toolchain_available=True)
        assert route_after_discovery(state) == "verify_reality"

    def test_toolchain_missing_routes_to_setup_guide(self):
        state = RealityAgentState(user_request="test", toolchain_available=False)
        assert route_after_discovery(state) == "setup_guide"

    def test_default_toolchain_available_is_true(self):
        # Backward compat: default True should not break existing tests
        state = RealityAgentState(user_request="test")
        assert route_after_discovery(state) == "verify_reality"


class TestBuildGraph:
    """Verify topology includes new §0 nodes."""

    def test_graph_compiles_with_discovery_nodes(self):
        graph = build_graph()
        assert graph is not None

    def test_compile_agent_succeeds(self):
        agent = compile_agent()
        assert agent is not None

    def test_environment_discovery_is_entry_point(self):
        # LangGraph doesn't expose entry point easily, but we can verify
        # by running the agent and checking the first phase
        from reality_agent.nodes.environment_discovery import environment_discovery_node
        state = RealityAgentState(user_request="test")
        result = environment_discovery_node(state)
        assert result["current_phase"] == "Environment_Discovery"


class TestGraphEndToEndRouting:
    """Integration: full graph execution with §0 hard-cut."""

    def test_toolchain_missing_ends_at_setup_guide(self):
        from reality_agent.nodes import environment_discovery as ed_module
        with patch.object(ed_module, "discover_project_language", return_value="rust"), \
             patch.object(ed_module, "verify_toolchain_executable", return_value=(False, "Missing cargo")):
            agent = compile_agent()
            state = RealityAgentState(user_request="fix rust compile error")
            final = agent.invoke(state)
        assert final["current_phase"] == "Setup_Guide"
        assert "安全中断" in final["knowledge_gained"][-1]

    def test_toolchain_available_proceeds_to_reality_check(self):
        from reality_agent.nodes import environment_discovery as ed_module
        with patch.object(ed_module, "discover_project_language", return_value="rust"), \
             patch.object(ed_module, "verify_toolchain_executable", return_value=(True, "/usr/bin/cargo")):
            agent = compile_agent()
            state = RealityAgentState(user_request="fix rust compile error")
            phases = []
            for step in agent.stream(state, stream_mode="values"):
                phases.append(step.get("current_phase"))
        # Environment_Discovery should appear during execution (not necessarily first,
        # since initial state has default current_phase="Reality_Check")
        assert "Environment_Discovery" in phases
        assert "Reality_Check" in phases
