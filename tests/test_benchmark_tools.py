"""
Tests for Benchmark Tools — Phase 3 tool chain.

Uses unittest.mock to mock subprocess.run for isolated, deterministic testing.
"""

import os
from unittest.mock import MagicMock, patch

from reality_agent.state import RealityAgentState
from reality_agent.tools.benchmark_tools import (
    run_benchmark,
    generate_flamegraph,
    _extract_simple_metrics,
)


class TestRunBenchmark:
    """Tests for run_benchmark() — §10 performance measurement."""

    @patch.dict(os.environ, {"RDI_BENCHMARK_COMMAND": "cargo bench"})
    @patch("reality_agent.tools.benchmark_tools.subprocess.run")
    def test_benchmark_success(self, mock_run):
        """Benchmark 成功执行并产生数据."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "test bench_fibonacci ... bench: 1,234 ns/iter\n"
            "time: 0.001234 s\n"
            "throughput: 810,000 ops/s"
        )
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        state = RealityAgentState(user_request="optimize function")
        result = run_benchmark(state)

        assert result["benchmark_passed"] is True
        assert result["exit_code"] == 0
        assert result["command"] == "cargo bench"
        assert result["metrics"]["ops_per_sec"] == 810000
        assert "time_seconds" in result["metrics"]

    @patch.dict(os.environ, {"RDI_BENCHMARK_COMMAND": "cargo bench"})
    @patch("reality_agent.tools.benchmark_tools.subprocess.run")
    def test_benchmark_failure(self, mock_run):
        """Benchmark 执行失败（非零退出码）."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "error: bench failed"
        mock_run.return_value = mock_result

        state = RealityAgentState(user_request="optimize function")
        result = run_benchmark(state)

        assert result["benchmark_passed"] is False
        assert result["exit_code"] == 1

    @patch.dict(os.environ, {}, clear=True)
    def test_benchmark_missing_config(self):
        """缺少 RDI_BENCHMARK_COMMAND 配置时返回安全 fallback."""
        state = RealityAgentState(user_request="optimize function")
        result = run_benchmark(state)

        assert result["benchmark_passed"] is False
        assert result["exit_code"] == -1
        assert "WARNING" in result["tool_outputs"][0]
        assert "not configured" in result["tool_outputs"][0]

    @patch.dict(os.environ, {"RDI_BENCHMARK_COMMAND": "wrk -t2 -c100 -d10s http://localhost:8080"})
    @patch("reality_agent.tools.benchmark_tools.subprocess.run")
    def test_benchmark_timeout(self, mock_run):
        """Benchmark 超时处理."""
        from subprocess import TimeoutExpired
        mock_run.side_effect = TimeoutExpired("wrk", 600)

        state = RealityAgentState(user_request="optimize function")
        result = run_benchmark(state)

        assert result["benchmark_passed"] is False
        assert result["exit_code"] == -2
        assert "timed out" in result["tool_outputs"][0]

    @patch.dict(os.environ, {"RDI_BENCHMARK_COMMAND": "pytest --benchmark"})
    @patch("reality_agent.tools.benchmark_tools.subprocess.run")
    def test_benchmark_empty_output(self, mock_run):
        """Benchmark 退出码 0 但无输出视为失败."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""  # Empty output
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        state = RealityAgentState(user_request="optimize function")
        result = run_benchmark(state)

        assert result["benchmark_passed"] is False  # No data = no pass
        assert result["exit_code"] == 0

    @patch.dict(os.environ, {"RDI_BENCHMARK_COMMAND": "pytest --benchmark"})
    @patch("reality_agent.tools.benchmark_tools.subprocess.run")
    def test_benchmark_metric_extraction(self, mock_run):
        """从输出中提取性能指标."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "Benchmark test_1\n"
            "  time: 2.50 s\n"
            "  throughput: 1,500,000 ops/s\n"
            "  latency: 45.2 ms"
        )
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        state = RealityAgentState(user_request="optimize function")
        result = run_benchmark(state)

        assert result["metrics"]["time_seconds"] == 2.50
        assert result["metrics"]["ops_per_sec"] == 1500000
        assert result["metrics"]["latency_ms"] == 45.2


class TestExtractSimpleMetrics:
    """Tests for _extract_simple_metrics() heuristic parser."""

    def test_extract_time(self):
        """提取时间指标."""
        stdout = "Benchmark result: time: 1.23 s\n"
        metrics = _extract_simple_metrics(stdout)
        assert metrics["time_seconds"] == 1.23

    def test_extract_ops(self):
        """提取吞吐量指标."""
        stdout = "Throughput: 999,999 ops/s\n"
        metrics = _extract_simple_metrics(stdout)
        assert metrics["ops_per_sec"] == 999999

    def test_extract_latency(self):
        """提取延迟指标."""
        stdout = "Average latency: 12.5 ms\n"
        metrics = _extract_simple_metrics(stdout)
        assert metrics["latency_ms"] == 12.5

    def test_extract_all_metrics(self):
        """同时提取所有指标."""
        stdout = (
            "time: 3.14 s\n"
            "throughput: 2,500,000 ops/s\n"
            "latency: 99.9 ms"
        )
        metrics = _extract_simple_metrics(stdout)
        assert len(metrics) == 3
        assert metrics["time_seconds"] == 3.14
        assert metrics["ops_per_sec"] == 2500000
        assert metrics["latency_ms"] == 99.9

    def test_no_metrics(self):
        """无匹配指标时返回空字典."""
        stdout = "Some random output without numbers"
        metrics = _extract_simple_metrics(stdout)
        assert metrics == {}


class TestGenerateFlamegraph:
    """Tests for generate_flamegraph() — stub Phase 3."""

    @patch.dict(os.environ, {"RDI_FLAMEGRAPH_COMMAND": "perf record -g ./target"})
    def test_flamegraph_stub_with_config(self):
        """配置了命令但仍为 stub（Phase 3）."""
        state = RealityAgentState(user_request="profile cpu")
        result = generate_flamegraph(state)

        assert result["flamegraph_generated"] is False
        assert "Phase 3" in result["tool_outputs"][0]
        assert "perf record" in result["command"]

    @patch.dict(os.environ, {}, clear=True)
    def test_flamegraph_stub_default(self):
        """无配置时使用默认 fallback."""
        state = RealityAgentState(user_request="profile cpu")
        result = generate_flamegraph(state)

        assert result["flamegraph_generated"] is False
        assert "not configured" in result["tool_outputs"][0].lower() or "Phase 3" in result["tool_outputs"][0]


class TestDifferentialTest:
    """Tests for run_differential_test() — §5 Change One Thing."""

    def test_identical_modules_pass(self, tmp_path):
        """两个完全相同的模块 → diff_passed=True, identical=True."""
        original = tmp_path / "original.py"
        variant = tmp_path / "variant.py"
        original.write_text("def solve(x):\n    return x * 2\n")
        variant.write_text("def solve(x):\n    return x * 2\n")

        from reality_agent.tools.benchmark_tools import run_differential_test
        result = run_differential_test(
            str(original), str(variant), inputs=[1, 2, 3, 5, 10]
        )

        assert result["diff_passed"] is True
        assert result["identical"] is True
        assert len(result["differences"]) == 0
        assert result["error"] is None

    def test_different_modules_fail(self, tmp_path):
        """两个不同的模块 → diff_passed=False, identical=False."""
        original = tmp_path / "original.py"
        variant = tmp_path / "variant.py"
        original.write_text("def solve(x):\n    return x * 2\n")
        variant.write_text("def solve(x):\n    return x * 3\n")

        from reality_agent.tools.benchmark_tools import run_differential_test
        result = run_differential_test(
            str(original), str(variant), inputs=[2, 3]
        )

        assert result["diff_passed"] is False
        assert result["identical"] is False
        assert len(result["differences"]) == 2
        assert result["differences"][0]["type"] == "value_mismatch"
        assert result["differences"][0]["original"] == 4
        assert result["differences"][0]["variant"] == 6

    def test_dict_input_support(self, tmp_path):
        """支持 dict 类型输入（关键字参数）."""
        original = tmp_path / "calc.py"
        variant = tmp_path / "calc_v2.py"
        original.write_text("def compute(a, b):\n    return a + b\n")
        variant.write_text("def compute(a, b):\n    return a + b\n")

        from reality_agent.tools.benchmark_tools import run_differential_test
        result = run_differential_test(
            str(original), str(variant), inputs=[{"a": 1, "b": 2}, {"a": 10, "b": 20}]
        )

        assert result["diff_passed"] is True
        assert result["original_results"] == [3, 30]

    def test_execution_error_captured(self, tmp_path):
        """变体模块抛出异常 → 差异记录为 execution_error."""
        original = tmp_path / "safe.py"
        variant = tmp_path / "buggy.py"
        original.write_text("def process(x):\n    return x / 2\n")
        variant.write_text("def process(x):\n    return x / 0\n")

        from reality_agent.tools.benchmark_tools import run_differential_test
        result = run_differential_test(
            str(original), str(variant), inputs=[4, 8]
        )

        assert result["diff_passed"] is False
        assert result["identical"] is False
        assert len(result["differences"]) == 2
        assert result["differences"][0]["type"] == "execution_error"
        assert "division by zero" in result["differences"][0]["error"].lower() or "ZeroDivisionError" in result["differences"][0]["error"]

    def test_tolerance_float_mismatch(self, tmp_path):
        """Tolerance 参数允许微小浮点差异通过."""
        original = tmp_path / "calc.py"
        variant = tmp_path / "calc_v2.py"
        original.write_text("def compute(x):\n    return x * 1.0\n")
        variant.write_text("def compute(x):\n    return x * 1.00001\n")

        from reality_agent.tools.benchmark_tools import run_differential_test
        # Strict mode (tolerance=0) should fail
        strict = run_differential_test(
            str(original), str(variant), inputs=[1.0, 2.0, 3.0], tolerance=0.0
        )
        assert strict["diff_passed"] is False

        # Tolerance mode (tolerance=0.001) should pass
        loose = run_differential_test(
            str(original), str(variant), inputs=[1.0, 2.0, 3.0], tolerance=0.001
        )
        assert loose["diff_passed"] is True
        assert loose["identical"] is False  # Still not strictly identical
        assert loose["tolerance"] == 0.001

    def test_tolerance_large_diff_still_fails(self, tmp_path):
        """Tolerance 不掩盖显著差异."""
        original = tmp_path / "big.py"
        variant = tmp_path / "big_v2.py"
        original.write_text("def big(x):\n    return x * 10.0\n")
        variant.write_text("def big(x):\n    return x * 15.0\n")

        from reality_agent.tools.benchmark_tools import run_differential_test
        result = run_differential_test(
            str(original), str(variant), inputs=[1.0, 2.0], tolerance=0.1
        )
        assert result["diff_passed"] is False
        assert result["differences"][0]["original"] == 10.0
        assert result["differences"][0]["variant"] == 15.0

    def test_tolerance_non_numeric_ignored(self, tmp_path):
        """Tolerance 仅对数值类型生效，字符串/列表仍严格比对."""
        original = tmp_path / "text.py"
        variant = tmp_path / "text_v2.py"
        original.write_text("def greet(name):\n    return f'Hello {name}'\n")
        variant.write_text("def greet(name):\n    return f'Hi {name}'\n")

        from reality_agent.tools.benchmark_tools import run_differential_test
        result = run_differential_test(
            str(original), str(variant), inputs=["Alice"], tolerance=0.5
        )
        assert result["diff_passed"] is False
        assert result["differences"][0]["type"] == "value_mismatch"

