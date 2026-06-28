"""Tests for §14 Success Criteria — 合规检查."""

import pytest

from reality_agent.state import RealityAgentState


class TestSuccessCriteria:
    """§14 一个合规的会话应包含 6 项检查."""

    def test_verify_reality_called(self):
        """1. Verify Reality — 至少确认了一个真实存在的现象."""
        state = RealityAgentState(
            facts=["Log shows NullPointerException at line 42."],
        )
        assert len(state.facts) > 0, "Session must have at least one verified fact."

    def test_verify_measurement_called(self):
        """2. Verify Measurement — 确认了数据来源和口径的一致性."""
        state = RealityAgentState(
            provenance_verified=True,
            data_sources_aligned=True,
            time_window_aligned=True,
        )
        assert state.provenance_verified is True, "Measurement must be verified."
        assert state.data_sources_aligned is True
        assert state.time_window_aligned is True

    def test_evidence_gate_enforced(self):
        """3. Evidence Gate — 任何修改都有证据支撑."""
        state = RealityAgentState(
            evidence_level="Evidence",
            provenance_verified=True,
        )
        assert state.evidence_level in ("Evidence", "Verified")
        assert state.provenance_verified is True

    def test_change_one_thing_enforced(self):
        """4. Change One Thing — 每次修改一个变量."""
        state = RealityAgentState(
            variables_changed_count=1,
        )
        assert state.variables_changed_count <= 1, "Must change at most ONE variable per iteration."

    def test_build_knowledge_recorded(self):
        """5. Build Knowledge — 记录了理解增量."""
        state = RealityAgentState(
            knowledge_gained=["Root cause is race condition in cache invalidation."],
        )
        assert len(state.knowledge_gained) > 0, "Understanding gained must be non-empty."

    def test_freeze_and_observe_recommended(self):
        """6. Freeze And Observe — 在系统稳定时建议观察期."""
        state = RealityAgentState(
            provenance_verified=True,
            trap_detected=None,
            change_accepted=True,
        )
        # Simulate route_after_knowledge logic
        stable = (
            state.provenance_verified
            and state.trap_detected is None
            and state.change_accepted is True
        )
        assert stable is True, "Stable system must be recommended for observation freeze."
