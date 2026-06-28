"""
Tests for LLM Structured Output Nodes — Phase 4 Brain Activation.

These tests verify that reality_check_node and measurement_check_node produce
outputs strictly conforming to their Pydantic schemas, even when LLM is disabled
(stub mode) or when falling back from LLM failures.
"""

import os
from unittest.mock import MagicMock, patch

from pydantic import ValidationError
import pytest

from reality_agent.nodes.measurement_check import (
    MeasurementCheckBrainOutput,
    measurement_check_node,
)
from reality_agent.nodes.reality_check import RealityCheckBrainOutput, reality_check_node
from reality_agent.state import RealityAgentState


class TestRealityCheckBrainOutputSchema:
    """验证 RealityCheckBrainOutput Pydantic Schema 的严格性."""

    def test_valid_output(self):
        """合法输出应通过验证."""
        output = RealityCheckBrainOutput(
            is_reproduced=True,
            facts=["NullPointerException at line 42"],
            hypotheses=["Race condition in cache"],
            evidence_level="Evidence",
            trap_detected="Explanation",
            trap_details="User only said 'it feels slow' without metrics",
        )
        assert output.is_reproduced is True
        assert len(output.facts) == 1
        assert output.evidence_level == "Evidence"

    def test_invalid_evidence_level(self):
        """非法 evidence_level 应触发 ValidationError."""
        with pytest.raises(ValidationError):
            RealityCheckBrainOutput(
                is_reproduced=False,
                facts=[],
                hypotheses=[],
                evidence_level="InvalidLevel",  # Not in Literal
            )

    def test_trap_detected_optional(self):
        """trap_detected 为 None 时应通过."""
        output = RealityCheckBrainOutput(
            is_reproduced=False,
            facts=[],
            hypotheses=[],
            evidence_level="Observation",
        )
        assert output.trap_detected is None

    def test_empty_facts_allowed(self):
        """facts 为空列表时（Observation 阶段）应通过."""
        output = RealityCheckBrainOutput(
            is_reproduced=False,
            facts=[],  # Empty is valid for Observation
            hypotheses=["System may have issue"],
            evidence_level="Observation",
        )
        assert len(output.facts) == 0


class TestMeasurementCheckBrainOutputSchema:
    """验证 MeasurementCheckBrainOutput Pydantic Schema 的严格性."""

    def test_all_checks_true(self):
        """所有检查通过时 provenance_verified=True."""
        output = MeasurementCheckBrainOutput(
            provenance_verified=True,
            data_sources_aligned=True,
            time_window_aligned=True,
            version_aligned=True,
            snapshot_fresh=True,
            knowledge_gained=["All sources point to production DB"],
        )
        assert output.provenance_verified is True

    def test_any_check_none_makes_verified_false(self):
        """任一项为 None 时 provenance_verified 可以为 False."""
        output = MeasurementCheckBrainOutput(
            provenance_verified=False,
            data_sources_aligned=None,  # Unknown
            time_window_aligned=True,
            version_aligned=True,
            snapshot_fresh=True,
            audit_reason="data_sources_aligned is unknown",
        )
        assert output.provenance_verified is False

    def test_invalid_provenance_type(self):
        """provenance_verified 非 bool 时应触发 ValidationError."""
        with pytest.raises(ValidationError):
            MeasurementCheckBrainOutput(
                provenance_verified=["invalid"],  # List is not a bool
            )


class TestRealityCheckNodeStubMode:
    """RDI_LLM_MODE=stub 时，节点使用 heuristic fallback."""

    def test_no_logs_returns_observation(self):
        """无日志 → Observation 等级."""
        state = RealityAgentState(user_request="fix panic")
        result = reality_check_node(state)
        assert result["evidence_level"] == "Observation"
        assert result["current_phase"] == "Reality_Check"
        assert any("without attached logs" in f for f in result["facts"])

    def test_with_logs_returns_hypothesis_or_better(self):
        """有日志 → Hypothesis 或更高等级."""
        state = RealityAgentState(
            user_request="fix panic",
            raw_logs=["Traceback (most recent call last): ..."],
        )
        result = reality_check_node(state)
        assert result["evidence_level"] in ("Hypothesis", "Evidence", "Verified")
        assert result["current_phase"] == "Reality_Check"

    def test_reproduced_tool_output_marks_verified(self):
        """reproduce_issue 工具输出 BUG REPRODUCED → Verified."""
        state = RealityAgentState(
            user_request="fix panic",
            tool_outputs=["Exit code: 1 (BUG REPRODUCED)"],
        )
        result = reality_check_node(state)
        assert result["evidence_level"] == "Verified"
        assert any("reproduced" in f.lower() for f in result["facts"])

    def test_fallback_on_llm_failure(self):
        """LLM 调用失败时回退到 heuristic，不崩溃."""
        # 即使 RDI_LLM_MODE=real，如果 LLM 配置错误也应回退
        with patch.dict(os.environ, {"RDI_LLM_MODE": "real", "LLM_PROVIDER": "deepseek"}):
            # 不设置 DEEPSEEK_API_KEY，预期 get_llm() 会失败
            state = RealityAgentState(user_request="fix panic")
            result = reality_check_node(state)
            # Should not raise; falls back to heuristic
            assert "current_phase" in result
            assert any(
                "falling back" in kg.lower() or "heuristic" in kg.lower()
                for kg in result.get("knowledge_gained", [])
            )


class TestMeasurementCheckNodeStubMode:
    """RDI_LLM_MODE=stub 时，measurement_check 节点行为."""

    def test_default_unverified(self):
        """默认保守策略：provenance_verified=False."""
        state = RealityAgentState(user_request="optimize timeout")
        result = measurement_check_node(state)
        assert result["provenance_verified"] is False
        assert result["data_sources_aligned"] is None
        assert result["current_phase"] == "Measurement_Check"

    def test_detects_git_dirty(self):
        """Git dirty 工具输出 → version_aligned=False."""
        state = RealityAgentState(
            user_request="optimize",
            tool_outputs=["Working tree clean: False\nUncommitted files: 3"],
        )
        result = measurement_check_node(state)
        assert result["version_aligned"] is False
        assert any("dirty" in kg.lower() for kg in result["knowledge_gained"])

    def test_clean_git_no_change(self):
        """无 git dirty 信号 → 保持默认 None."""
        state = RealityAgentState(
            user_request="optimize",
            tool_outputs=["Working tree clean: True"],
        )
        result = measurement_check_node(state)
        # No dirty signal, stays at default None/False
        assert result["provenance_verified"] is False


class TestStructuredOutputWithLLMMock:
    """模拟 LLM 调用，验证结构化输出注入 state."""

    @patch("reality_agent.nodes.reality_check.get_llm")
    def test_llm_structured_output_injected(self, mock_get_llm):
        """LLM 返回结构化输出时，正确注入 state 字段."""
        # 配置 mock LLM
        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = RealityCheckBrainOutput(
            is_reproduced=True,
            facts=["NPE at line 42"],
            hypotheses=[],
            evidence_level="Evidence",
            trap_detected=None,
        )
        mock_llm.with_structured_output.return_value = mock_structured
        mock_get_llm.return_value = mock_llm

        with patch.dict(os.environ, {"RDI_LLM_MODE": "real"}):
            state = RealityAgentState(user_request="fix npe")
            result = reality_check_node(state)

            assert result["evidence_level"] == "Evidence"
            assert result["facts"] == ["NPE at line 42"]
            assert result["trap_detected"] is None
            mock_llm.with_structured_output.assert_called_once_with(RealityCheckBrainOutput)

    @patch("reality_agent.nodes.measurement_check.get_llm")
    def test_measurement_llm_structured_output(self, mock_get_llm):
        """Measurement 节点 LLM 结构化输出注入."""
        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = MeasurementCheckBrainOutput(
            provenance_verified=True,
            data_sources_aligned=True,
            time_window_aligned=True,
            version_aligned=True,
            snapshot_fresh=True,
            knowledge_gained=["All aligned"],
        )
        mock_llm.with_structured_output.return_value = mock_structured
        mock_get_llm.return_value = mock_llm

        with patch.dict(os.environ, {"RDI_LLM_MODE": "real"}):
            state = RealityAgentState(user_request="optimize")
            result = measurement_check_node(state)

            assert result["provenance_verified"] is True
            assert result["data_sources_aligned"] is True
            mock_llm.with_structured_output.assert_called_once_with(MeasurementCheckBrainOutput)


# ---------------------------------------------------------------------------
# DeepSeek v4-pro 真实 API 端到端黑盒测试桩
# ---------------------------------------------------------------------------

def _has_deepseek_config() -> bool:
    """检查是否具备 DeepSeek API 配置."""
    return bool(
        os.getenv("DEEPSEEK_API_KEY") or os.getenv("LLM_API_KEY")
    )


@pytest.mark.skipif(not _has_deepseek_config(), reason="DeepSeek API key not configured")
class TestDeepSeekRealAPI:
    """
    DeepSeek v4-pro 真实 API 端到端测试.

    运行条件:
      - 环境变量 DEEPSEEK_API_KEY 或 LLM_API_KEY 已设置
      - 网络可达 https://api.deepseek.com/v1

    警告: 这些测试调用真实 API，可能产生费用。仅在 CI 环境变量控制下运行。
    """

    @patch.dict(os.environ, {
        "RDI_LLM_MODE": "real",
        "LLM_PROVIDER": "deepseek",
        "LLM_MODEL": "deepseek-v4-pro",
        "LLM_BASE_URL": "https://api.deepseek.com/v1",
    }, clear=False)
    def test_reality_check_structured_output_with_deepseek(self):
        """
        端到端: DeepSeek v4-pro 对 reality_check 节点输出结构化 JSON.

        验证点:
        1. get_llm() 成功实例化 ChatOpenAI (deepseek-compatible)
        2. with_structured_output(RealityCheckBrainOutput) 不抛异常
        3. 返回结果符合 Pydantic Schema（facts, hypotheses, evidence_level 分离）
        4. evidence_level 不为非法值
        """
        from reality_agent.llm import get_llm
        from reality_agent.nodes.reality_check import RealityCheckBrainOutput, reality_check_node

        state = RealityAgentState(
            user_request="We observed a 500 Internal Server Error on /api/v1/orders endpoint around 14:00 UTC. Logs show NullPointerException at OrderService.java:147.",
            raw_logs=[
                "2024-01-15 14:00:03 ERROR OrderService - NullPointerException at line 147",
                "2024-01-15 14:00:04 ERROR OrderController - 500 Internal Server Error",
            ],
        )

        result = reality_check_node(state)

        # 验证输出符合预期范围
        assert "evidence_level" in result
        assert result["evidence_level"] in ("Observation", "Hypothesis", "Evidence", "Verified")
        assert "facts" in result
        assert isinstance(result["facts"], list)
        assert len(result["facts"]) >= 1  # DeepSeek 应至少提取一条事实
        assert "hypotheses" in result
        assert isinstance(result["hypotheses"], list)
        # 如果证据充足，evidence_level 至少应为 Hypothesis
        if result["evidence_level"] in ("Evidence", "Verified"):
            assert len(result["facts"]) >= 1

    @patch.dict(os.environ, {
        "RDI_LLM_MODE": "real",
        "LLM_PROVIDER": "deepseek",
        "LLM_MODEL": "deepseek-v4-pro",
        "LLM_BASE_URL": "https://api.deepseek.com/v1",
    }, clear=False)
    def test_measurement_check_structured_output_with_deepseek(self):
        """
        端到端: DeepSeek v4-pro 对 measurement_check 节点输出结构化 JSON.

        验证点:
        1. provenance_verified 为 bool 类型
        2. data_sources_aligned / time_window_aligned / version_aligned / snapshot_fresh 为 bool 或 None
        3. audit_reason 在 provenance_verified=False 时非空
        """
        from reality_agent.nodes.measurement_check import MeasurementCheckBrainOutput, measurement_check_node

        state = RealityAgentState(
            user_request="optimize database query latency",
            evidence_level="Hypothesis",
            facts=["Dashboard shows avg latency 450ms", "Backtest shows 120ms"],
            tool_outputs=[
                "check_git_consistency: commit=abc1234, working_tree_clean=True",
                "check_environment: RDI_BENCHMARK_COMMAND=pytest --benchmark",
            ],
        )

        result = measurement_check_node(state)

        assert "provenance_verified" in result
        assert isinstance(result["provenance_verified"], bool)
        assert result["data_sources_aligned"] in (True, False, None)
        assert result["time_window_aligned"] in (True, False, None)
        assert result["version_aligned"] in (True, False, None)
        assert result["snapshot_fresh"] in (True, False, None)

        if result["provenance_verified"] is False:
            assert result.get("knowledge_gained")  # 应有审计原因

    @patch.dict(os.environ, {
        "RDI_LLM_MODE": "real",
        "LLM_PROVIDER": "deepseek",
        "LLM_MODEL": "deepseek-v4-pro",
        "LLM_BASE_URL": "https://api.deepseek.com/v1",
    }, clear=False)
    def test_deepseek_llm_factory(self):
        """
        验证 DeepSeek 工厂函数正确实例化 LLM.

        确保 get_llm() 返回的实例支持 with_structured_output() 方法。
        """
        import os
        import importlib
        import reality_agent.llm

        # 在测试运行时动态设置 API key，绕过 patch.dict 的导入时计算问题
        api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("LLM_API_KEY")
        if not api_key:
            pytest.skip("DEEPSEEK_API_KEY or LLM_API_KEY not set in environment")
        os.environ["LLM_API_KEY"] = api_key

        # 必须 reload 模块：LLM_PROVIDER 等是模块级常量，
        # patch.dict 只影响 os.environ 但不影响已导入的模块常量
        importlib.reload(reality_agent.llm)
        from reality_agent.llm import get_llm

        llm = get_llm()
        assert llm is not None
        # 关键验证：支持结构化输出绑定
        structured = llm.with_structured_output(RealityCheckBrainOutput)
        assert structured is not None
