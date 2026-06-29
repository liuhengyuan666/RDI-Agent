"""Tests for Setup Guide Node — §0 Infrastructure Missing Terminal."""

from reality_agent.nodes.setup_guide import setup_guide_node
from reality_agent.state import RealityAgentState


class TestSetupGuideNode:
    """Terminal node: echoes setup_plan, never calls sys.exit."""

    def test_setup_guide_with_plan(self):
        state = RealityAgentState(
            user_request="test",
            setup_plan="[RDI Environment Alert] Install Rust.",
            toolchain_available=False,
        )
        result = setup_guide_node(state)
        assert result["current_phase"] == "Setup_Guide"
        assert "[RDI Environment Alert] Install Rust." in result["knowledge_gained"][0]

    def test_setup_guide_without_plan(self):
        state = RealityAgentState(
            user_request="test",
            setup_plan=None,
            toolchain_available=False,
        )
        result = setup_guide_node(state)
        assert result["current_phase"] == "Setup_Guide"
        assert "No setup guide was generated" in result["knowledge_gained"][0]

    def test_setup_guide_does_not_modify_other_state(self):
        state = RealityAgentState(
            user_request="test",
            setup_plan="Plan here",
            detected_language="rust",
        )
        result = setup_guide_node(state)
        # Should only touch current_phase and knowledge_gained
        assert "detected_language" not in result
        assert "toolchain_available" not in result
