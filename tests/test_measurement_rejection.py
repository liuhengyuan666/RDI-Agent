"""
Tests for Measurement Rejection — §4 Evidence Gate 物理拦截场景.

本测试验证当测量口径不一致（provenance_verified=False）时，
无论证据等级是 Evidence 还是 Verified，Evidence Gate 都必须物理拦截，
禁止进入 isolate_iteration 阶段。
"""

import pytest

from reality_agent.graph import route_after_gate
from reality_agent.state import RealityAgentState


class TestMeasurementRejection:
    """测量口径不一致 → 强制拦截."""

    def test_evidence_without_provenance_is_blocked(self):
        """
        §4 分级拦截：Evidence + provenance_verified=False → build_knowledge (禁止).
        """
        state = RealityAgentState(
            user_request="optimize timeout",
            evidence_level="Evidence",
            provenance_verified=False,
            data_sources_aligned=False,
        )
        result = route_after_gate(state)
        assert result == "build_knowledge", (
            "Evidence without provenance verification MUST be blocked. "
            "This is a core physical guardrail."
        )

    def test_verified_without_provenance_is_blocked(self):
        """
        §4 分级拦截：Verified + provenance_verified=False → build_knowledge (禁止).
        
        v1 严格策略：哪怕是最高信任级 Verified，测量未验证也绝不放行。
        """
        state = RealityAgentState(
            user_request="optimize timeout",
            evidence_level="Verified",
            provenance_verified=False,
            data_sources_aligned=None,
        )
        result = route_after_gate(state)
        assert result == "build_knowledge", (
            "Verified level without provenance verification MUST be blocked. "
            "No exception, no bypass. This is the strictest guardrail."
        )

    def test_observation_always_blocked(self):
        """Observation 等级 — 无论 provenance 状态，一律禁止修改."""
        state = RealityAgentState(
            user_request="fix this",
            evidence_level="Observation",
            provenance_verified=False,
        )
        result = route_after_gate(state)
        assert result == "build_knowledge"

    def test_hypothesis_always_blocked(self):
        """Hypothesis 等级 — 无论 provenance 状态，一律禁止修改."""
        state = RealityAgentState(
            user_request="fix this",
            evidence_level="Hypothesis",
            provenance_verified=True,
        )
        result = route_after_gate(state)
        assert result == "build_knowledge"

    def test_evidence_with_provenance_allowed(self):
        """Evidence + provenance_verified=True → 允许隔离迭代."""
        state = RealityAgentState(
            user_request="fix this",
            evidence_level="Evidence",
            provenance_verified=True,
            data_sources_aligned=True,
            time_window_aligned=True,
            version_aligned=True,
            snapshot_fresh=True,
        )
        result = route_after_gate(state)
        assert result == "isolate_iteration"

    def test_verified_with_provenance_allowed(self):
        """Verified + provenance_verified=True → 允许隔离迭代."""
        state = RealityAgentState(
            user_request="fix this",
            evidence_level="Verified",
            provenance_verified=True,
            data_sources_aligned=True,
            time_window_aligned=True,
            version_aligned=True,
            snapshot_fresh=True,
        )
        result = route_after_gate(state)
        assert result == "isolate_iteration"

    def test_freeze_overrides_evidence_level(self):
        """Freeze 状态存在时，无论证据等级，强制 observe_freeze."""
        state = RealityAgentState(
            user_request="fix this",
            evidence_level="Verified",
            provenance_verified=True,
            freeze_until="2026-12-31T00:00:00Z",
        )
        result = route_after_gate(state)
        assert result == "observe_freeze"
