"""Tests for §13 Force Patch — cognitive debt tracking."""

import pytest

from reality_agent.state import RealityAgentState
from reality_agent.tools.force_patch import force_patch


class TestForcePatchFallback:
    """§13 降级策略 — 认知债务精确度量."""

    def test_force_patch_adds_cognitive_debt(self):
        """force_patch 必须标记 cognitive_debt_added = True."""
        state = RealityAgentState(user_request="emergency fix")
        result = force_patch(state, "Increased timeout to 500ms")
        assert result["cognitive_debt_added"] is True

    def test_force_patch_records_debt(self):
        """force_patch 必须在 cognitive_debt_records 中记录详情."""
        state = RealityAgentState(user_request="emergency fix")
        result = force_patch(state, "Increased timeout to 500ms")
        assert len(result["cognitive_debt_records"]) == 1
        assert "Increased timeout to 500ms" in result["cognitive_debt_records"][0]

    def test_force_patch_adds_warning(self):
        """force_patch 必须在 knowledge_gained 中添加警告."""
        state = RealityAgentState(user_request="emergency fix")
        result = force_patch(state, "Increased timeout to 500ms")
        assert any("WARNING" in k for k in result["knowledge_gained"])
        assert any("Cognitive Debt" in k for k in result["knowledge_gained"])

    def test_force_patch_leads_to_end(self):
        """force_patch 后不应进入观察期，应直接结束（产生债务）."""
        from reality_agent.graph import route_after_knowledge

        state = RealityAgentState(
            user_request="emergency fix",
            cognitive_debt_added=True,
        )
        result = route_after_knowledge(state)
        assert result == "end"
