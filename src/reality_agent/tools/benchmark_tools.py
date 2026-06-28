"""Benchmark tools — performance / flamegraph (§10)."""

import os
import subprocess
from typing import Any, Dict, List, Optional

from reality_agent.state import RealityAgentState


# ---------------------------------------------------------------------------
# Configuration: 所有命令通过环境变量读取，禁止硬编码
# ---------------------------------------------------------------------------

DEFAULT_BENCHMARK_COMMAND = "echo 'No RDI_BENCHMARK_COMMAND set. Please configure benchmark.'"
DEFAULT_FLAMEGRAPH_COMMAND = "echo 'No RDI_FLAMEGRAPH_COMMAND set. Please configure flamegraph.'"


# ---------------------------------------------------------------------------
# §10: Run Benchmark
# ---------------------------------------------------------------------------

def run_benchmark(state: RealityAgentState) -> Dict[str, Any]:
    """
    Run performance benchmark. No throughput / flamegraph data = no pass.

    Reads RDI_BENCHMARK_COMMAND from environment variable.
    Examples:
      - Python: "pytest --benchmark"
      - Rust: "cargo bench"
      - HTTP load: "wrk -t2 -c100 -d10s http://127.0.0.1:8080/api/v1/test"
      - Go: "go test -bench=."

    Returns:
        {
            "tool_outputs": [str],
            "benchmark_passed": bool,   # True if command succeeded and produced data
            "exit_code": int,
            "stdout": str,
            "stderr": str,
            "command": str,
            "metrics": Dict[str, Any],  # Parsed metrics (if available)
        }
    """
    cmd = os.getenv("RDI_BENCHMARK_COMMAND", DEFAULT_BENCHMARK_COMMAND)

    if cmd == DEFAULT_BENCHMARK_COMMAND:
        return {
            "tool_outputs": [
                "WARNING: RDI_BENCHMARK_COMMAND not configured. "
                "Set env var to your benchmark command (e.g., 'cargo bench', 'pytest --benchmark')."
            ],
            "benchmark_passed": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": "",
            "command": cmd,
            "metrics": {},
        }

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minutes for long benchmarks
        )
    except subprocess.TimeoutExpired:
        return {
            "tool_outputs": ["ERROR: Benchmark timed out after 600s."],
            "benchmark_passed": False,
            "exit_code": -2,
            "stdout": "",
            "stderr": "Benchmark timed out",
            "command": cmd,
            "metrics": {},
        }
    except Exception as e:
        return {
            "tool_outputs": [f"ERROR: Failed to execute benchmark: {e}"],
            "benchmark_passed": False,
            "exit_code": -3,
            "stdout": "",
            "stderr": str(e),
            "command": cmd,
            "metrics": {},
        }

    # Benchmark passes if command exits 0 and produced stdout
    benchmark_passed = result.returncode == 0 and len(result.stdout) > 0

    # Simple heuristic metric extraction: look for patterns like "time: 1.23s" or "ops: 4567"
    metrics = _extract_simple_metrics(result.stdout)

    output_summary = (
        f"Benchmark: {cmd}\n"
        f"Exit code: {result.returncode}\n"
        f"Passed: {benchmark_passed}\n"
        f"stdout length: {len(result.stdout)} chars\n"
        f"stderr length: {len(result.stderr)} chars\n"
        f"Extracted metrics: {len(metrics)} items"
    )

    return {
        "tool_outputs": [output_summary],
        "benchmark_passed": benchmark_passed,
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "command": cmd,
        "metrics": metrics,
    }


def _extract_simple_metrics(stdout: str) -> Dict[str, Any]:
    """
    Heuristic metric extraction from benchmark stdout.

    Looks for common patterns:
      - "time: X.XXs" or "X.XX s"
      - "throughput: XXXX ops/s"
      - "latency: X.XXms"
    """
    import re
    metrics: Dict[str, Any] = {}

    # Time patterns
    time_match = re.search(r'time[:\s]+([\d.]+)\s*s', stdout, re.IGNORECASE)
    if time_match:
        metrics["time_seconds"] = float(time_match.group(1))

    # Throughput / ops
    ops_match = re.search(r'([\d,]+)\s*ops/s', stdout, re.IGNORECASE)
    if ops_match:
        metrics["ops_per_sec"] = int(ops_match.group(1).replace(",", ""))

    # Latency
    lat_match = re.search(r'latency[:\s]+([\d.]+)\s*ms', stdout, re.IGNORECASE)
    if lat_match:
        metrics["latency_ms"] = float(lat_match.group(1))

    return metrics


# ---------------------------------------------------------------------------
# §5: Differential Test — Change One Thing 验证
# ---------------------------------------------------------------------------

import importlib.util
import sys
from pathlib import Path


def run_differential_test(
    module_path: str,
    variant_path: str,
    inputs: List[Any],
    tolerance: float = 0.0,
) -> Dict[str, Any]:
    """
    §5 Change One Thing — 差分测试引擎.

    接收原始模块路径和修改后的变体模块路径，以及一组输入矩阵。
    在隔离环境中加载并运行两者，比对输出结果。

    Args:
        module_path: 原始模块文件路径（如 "src/solver.py"）
        variant_path: 修改后的模块文件路径（如 "src/solver_v2.py"）
        inputs: 输入矩阵（List of dicts or args tuples）

    Returns:
        {
            "tool_outputs": [str],
            "diff_passed": bool,           # True if all outputs match
            "identical": bool,              # True if outputs exactly equal
            "differences": List[Dict],      # 详细差异记录
            "original_results": List[Any],
            "variant_results": List[Any],
            "error": str | None,           # 执行异常信息
        }
    """
    def _load_module(path: str) -> Any:
        """动态加载指定路径的 Python 模块."""
        spec = importlib.util.spec_from_file_location("_diff_module", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module from {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules["_diff_module"] = module
        spec.loader.exec_module(module)
        return module

    def _find_callable(module: Any) -> Any:
        """自动查找模块中的主要可调用对象（假设有一个非 dunder 的 callable）."""
        candidates = [
            getattr(module, name)
            for name in dir(module)
            if callable(getattr(module, name)) and not name.startswith("_")
        ]
        if not candidates:
            raise ValueError(f"No callable found in {module}")
        return candidates[0]

    try:
        original_module = _load_module(module_path)
        variant_module = _load_module(variant_path)

        original_fn = _find_callable(original_module)
        variant_fn = _find_callable(variant_module)
    except Exception as e:
        return {
            "tool_outputs": [f"Module loading failed: {e}"],
            "diff_passed": False,
            "identical": False,
            "differences": [],
            "original_results": [],
            "variant_results": [],
            "error": str(e),
        }

    original_results: List[Any] = []
    variant_results: List[Any] = []
    differences: List[Dict[str, Any]] = []
    strict_mismatches: List[Dict[str, Any]] = []  # 不受 tolerance 影响的严格比对记录

    for idx, inp in enumerate(inputs):
        try:
            if isinstance(inp, dict):
                orig_out = original_fn(**inp)
                var_out = variant_fn(**inp)
            elif isinstance(inp, (list, tuple)):
                orig_out = original_fn(*inp)
                var_out = variant_fn(*inp)
            else:
                orig_out = original_fn(inp)
                var_out = variant_fn(inp)
        except Exception as e:
            differences.append({
                "index": idx,
                "input": inp,
                "error": str(e),
                "type": "execution_error",
            })
            strict_mismatches.append(differences[-1])
            original_results.append(None)
            variant_results.append(None)
            continue

        original_results.append(orig_out)
        variant_results.append(var_out)

        # 严格相等记录（用于 identical 判定）
        if orig_out != var_out:
            strict_mismatches.append({
                "index": idx,
                "input": inp,
                "original": orig_out,
                "variant": var_out,
                "type": "strict_mismatch",
            })

        # Tolerance 比对（用于 diff_passed 判定）
        if not _outputs_equal(orig_out, var_out, tolerance):
            differences.append({
                "index": idx,
                "input": inp,
                "original": orig_out,
                "variant": var_out,
                "type": "value_mismatch",
            })

    identical = len(strict_mismatches) == 0
    diff_passed = len(differences) == 0

    summary = (
        f"Differential test: {len(inputs)} inputs. "
        f"Tolerance: {tolerance}. "
        f"Identical: {identical}. Differences: {len(differences)}."
    )

    return {
        "tool_outputs": [summary],
        "diff_passed": diff_passed,
        "identical": identical,
        "differences": differences,
        "original_results": original_results,
        "variant_results": variant_results,
        "error": None,
        "tolerance": tolerance,
    }


def _outputs_equal(a: Any, b: Any, tolerance: float) -> bool:
    """
    Compare two outputs with optional numeric tolerance.

    - If tolerance == 0 (default): strict equality (==)
    - If tolerance > 0 and both are numbers: abs(a - b) <= tolerance
    - Otherwise: strict equality
    """
    if tolerance <= 0.0:
        return a == b
    try:
        diff = abs(a - b)  # type: ignore
        return diff <= tolerance
    except (TypeError, ValueError):
        return a == b


# ---------------------------------------------------------------------------
# §10: Generate Flamegraph (stub — Phase 4)
# ---------------------------------------------------------------------------


def generate_flamegraph(state: RealityAgentState) -> Dict[str, Any]:
    """
    Generate CPU flamegraph. Requires `perf` or equivalent on target environment.

    Reads RDI_FLAMEGRAPH_COMMAND from environment variable.
    Phase 3: returns stub. Phase 4: actual flamegraph generation.
    """
    cmd = os.getenv("RDI_FLAMEGRAPH_COMMAND", DEFAULT_FLAMEGRAPH_COMMAND)

    return {
        "tool_outputs": [
            f"Phase 3: Flamegraph generation stub. "
            f"Configure RDI_FLAMEGRAPH_COMMAND to enable (e.g., 'perf record -g ./target'). "
            f"Current: {cmd}"
        ],
        "flamegraph_generated": False,
        "command": cmd,
    }
