"""Tests for §4 Evidence Gate — the core interception layer."""

import pytest

from reality_agent.graph import route_after_gate
from reality_agent.state import RealityAgentState


class TestEvidenceGateRouting:
    """§4 分级拦截策略 — 纯逻辑路由测试."""

    def test_observation_level_blocked(self):
        """仅有 Observation → 禁止修改，返回 build_knowledge."""
        state = RealityAgentState(
            user_request="fix this",
            evidence_level="Observation",
            provenance_verified=False,
        )
        result = route_after_gate(state)
        assert result == "build_knowledge"

    def test_hypothesis_level_blocked(self):
        """仅有 Hypothesis → 禁止修改，返回 build_knowledge."""
        state = RealityAgentState(
            user_request="fix this",
            evidence_level="Hypothesis",
            provenance_verified=False,
        )
        result = route_after_gate(state)
        assert result == "build_knowledge"

    def test_evidence_without_provenance_blocked(self):
        """Evidence 但 provenance 未验证 → 禁止修改."""
        state = RealityAgentState(
            user_request="fix this",
            evidence_level="Evidence",
            provenance_verified=False,
        )
        result = route_after_gate(state)
        assert result == "build_knowledge"

    def test_evidence_with_provenance_allowed(self):
        """Evidence + provenance_verified → 允许 isolate_iteration."""
        state = RealityAgentState(
            user_request="fix this",
            evidence_level="Evidence",
            provenance_verified=True,
        )
        result = route_after_gate(state)
        assert result == "isolate_iteration"

    def test_verified_with_provenance_allowed(self):
        """Verified + provenance_verified → 允许 isolate_iteration."""
        state = RealityAgentState(
            user_request="fix this",
            evidence_level="Verified",
            provenance_verified=True,
        )
        result = route_after_gate(state)
        assert result == "isolate_iteration"

    def test_freeze_state_priority(self):
        """Freeze 记录存在时，无论证据等级，优先 observe_freeze."""
        state = RealityAgentState(
            user_request="fix this",
            evidence_level="Evidence",
            provenance_verified=True,
            freeze_until="2026-12-31T00:00:00Z",
        )
        result = route_after_gate(state)
        assert result == "observe_freeze"
