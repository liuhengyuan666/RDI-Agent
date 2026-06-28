"""
RDI Agent ↔ MemGuard MCP Integration Tests

验证 MemGuardMCPAdapter 通过 stdio 发送正确的 JSON-RPC 2.0 消息，
无需启动真实 npx 进程（通过 mock subprocess 隔离外部依赖）。
"""

import json
import os
from io import StringIO
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from reality_agent.adapters.memory_adapter import (
    MemGuardMCPAdapter,
    get_memory_adapter,
)


class FakePipe:
    """模拟 subprocess stdout/stdin 的管道行为。"""

    def __init__(self, responses: list[dict]):
        self._responses = iter(responses)
        self._buffer = StringIO()
        self._closed = False

    def readline(self) -> str:
        try:
            resp = next(self._responses)
            return json.dumps(resp) + "\n"
        except StopIteration:
            return ""

    def write(self, s: str) -> None:
        self._buffer.write(s)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        self._closed = True

    def poll(self) -> None:
        return None


def _make_mock_proc(responses: list[dict]) -> MagicMock:
    """创建模拟 subprocess.Popen 对象。"""
    proc = MagicMock()
    proc.poll.return_value = None
    proc.stdin = FakePipe([])
    proc.stdout = FakePipe(responses)
    proc.stderr = FakePipe([])
    return proc


def _attach_mock(adapter: MemGuardMCPAdapter, mock_proc: MagicMock) -> None:
    """将 mock 进程附加到 adapter，绕过 _ensure_connection 握手。"""
    adapter._connected = True
    adapter._proc = mock_proc


def _get_sent_messages(adapter: MemGuardMCPAdapter) -> list[dict]:
    """从 adapter 的 stdin 读取所有已发送的 JSON-RPC 消息。"""
    proc = adapter._proc
    assert proc is not None
    stdin_pipe = proc.stdin
    assert isinstance(stdin_pipe, FakePipe)
    raw = stdin_pipe._buffer.getvalue().strip()
    if not raw:
        return []
    return [json.loads(line) for line in raw.split("\n")]


class TestMemGuardMCPAdapterHandshake:
    """测试 MCP 握手流程。"""

    def test_initialize_handshake(self):
        """验证 _ensure_connection 发送正确的 initialize / initialized 序列。"""
        init_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "memguard-mcp", "version": "1.0.0"},
                "capabilities": {},
            },
        }
        adapter = MemGuardMCPAdapter()
        mock_proc = _make_mock_proc([init_response])

        # 同时 patch subprocess.Popen 和 time.sleep，完整隔离外部进程
        with patch("subprocess.Popen", return_value=mock_proc), patch("time.sleep"):
            adapter._ensure_connection()

        lines = _get_sent_messages(adapter)
        assert len(lines) == 2
        assert lines[0]["method"] == "initialize"
        assert lines[0]["params"]["clientInfo"]["name"] == "rdi-agent"
        assert lines[1]["method"] == "notifications/initialized"
        assert lines[1].get("id") is None


class TestMemGuardMCPAdapterToolCalls:
    """测试各 Port 方法映射为正确的 MCP 工具调用。"""

    def test_is_project_frozen_calls_bootstrap(self):
        """is_project_frozen → runtime_bootstrap，解析 Observe 为冻结。"""
        bootstrap_result = {
            "jsonrpc": "2.0",
            "id": 2,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({
                            "current_phase": "Observe",
                            "constraints": ["freeze_until=2025-12-31"],
                            "memory_health": {"status": "ok"},
                        }),
                    }
                ]
            },
        }
        adapter = MemGuardMCPAdapter()
        _attach_mock(adapter, _make_mock_proc([bootstrap_result]))

        frozen, reason = adapter.is_project_frozen("test-project")
        assert frozen is True
        assert reason is not None
        assert "Observe" in reason
        assert "freeze_until=2025-12-31" in reason

        lines = _get_sent_messages(adapter)
        tool_call = [ln for ln in lines if ln.get("method") == "tools/call"][0]
        assert tool_call["params"]["name"] == "runtime_bootstrap"
        assert tool_call["params"]["arguments"]["project_root"] == os.getcwd()

    def test_is_project_frozen_not_frozen(self):
        """current_phase 为 Explore 时返回未冻结。"""
        bootstrap_result = {
            "jsonrpc": "2.0",
            "id": 2,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({
                            "current_phase": "Explore",
                            "constraints": [],
                            "memory_health": {"status": "ok"},
                        }),
                    }
                ]
            },
        }
        adapter = MemGuardMCPAdapter()
        _attach_mock(adapter, _make_mock_proc([bootstrap_result]))

        frozen, reason = adapter.is_project_frozen("test-project")
        assert frozen is False
        assert reason is None

    def test_log_cognitive_debt_sends_trap_recorded(self):
        """log_cognitive_debt → runtime_commit_event(TrapRecorded)。"""
        commit_result = {
            "jsonrpc": "2.0",
            "id": 2,
            "result": {
                "content": [
                    {"type": "text", "text": "successfully committed TrapRecorded"}
                ]
            },
        }
        adapter = MemGuardMCPAdapter()
        _attach_mock(adapter, _make_mock_proc([commit_result]))

        ok = adapter.log_cognitive_debt({
            "project_id": "test-project",
            "reason": "Unverified optimization",
            "patch_description": "Add async caching",
        })
        assert ok is True

        lines = _get_sent_messages(adapter)
        tool_call = [ln for ln in lines if ln.get("method") == "tools/call"][0]
        assert tool_call["params"]["name"] == "runtime_commit_event"
        assert tool_call["params"]["arguments"]["event_type"] == "TrapRecorded"
        payload = tool_call["params"]["arguments"]["payload"]
        assert payload["error_signature"] == "cognitive_debt"
        assert "Add async caching" in payload["solution"]
        assert "WARNING: Cognitive Debt" in payload["solution"]

    def test_log_freeze_sends_phase_changed(self):
        """log_freeze → runtime_commit_event(PhaseChanged)。"""
        commit_result = {
            "jsonrpc": "2.0",
            "id": 2,
            "result": {
                "content": [
                    {"type": "text", "text": "successfully committed PhaseChanged"}
                ]
            },
        }
        adapter = MemGuardMCPAdapter()
        _attach_mock(adapter, _make_mock_proc([commit_result]))

        ok = adapter.log_freeze("test-project", "2025-12-31", "High defect rate detected")
        assert ok is True

        lines = _get_sent_messages(adapter)
        tool_call = [ln for ln in lines if ln.get("method") == "tools/call"][0]
        assert tool_call["params"]["name"] == "runtime_commit_event"
        assert tool_call["params"]["arguments"]["event_type"] == "PhaseChanged"
        payload = tool_call["params"]["arguments"]["payload"]
        assert payload["new_phase"] == "Observe_Freeze"
        assert payload["reason"] == "High defect rate detected"
        assert payload["freeze_until"] == "2025-12-31"

    def test_log_iteration_checkpoint_sends_insight(self):
        """log_iteration_checkpoint → TrapRecorded，error_signature="insight"。"""
        commit_result = {
            "jsonrpc": "2.0",
            "id": 2,
            "result": {
                "content": [{"type": "text", "text": "successfully committed"}]
            },
        }
        adapter = MemGuardMCPAdapter()
        _attach_mock(adapter, _make_mock_proc([commit_result]))

        ok = adapter.log_iteration_checkpoint({
            "project_id": "test-project",
            "evidence_level": "Verified",
            "knowledge_gained": ["Cache invalidation is hard"],
            "trap_detected": False,
        })
        assert ok is True

        lines = _get_sent_messages(adapter)
        tool_call = [ln for ln in lines if ln.get("method") == "tools/call"][0]
        assert tool_call["params"]["name"] == "runtime_commit_event"
        assert tool_call["params"]["arguments"]["event_type"] == "TrapRecorded"
        payload = tool_call["params"]["arguments"]["payload"]
        assert payload["error_signature"] == "insight"
        assert "Cache invalidation is hard" in payload["solution"]

    def test_adapter_handles_tool_error_gracefully(self):
        """工具返回 error 时保守返回，不抛异常。"""
        error_response = {
            "jsonrpc": "2.0",
            "id": 2,
            "error": {"code": -32602, "message": "Invalid params"},
        }
        adapter = MemGuardMCPAdapter()
        _attach_mock(adapter, _make_mock_proc([error_response]))

        frozen, reason = adapter.is_project_frozen("test-project")
        assert frozen is False
        assert reason is not None
        assert "MemGuard bootstrap failed" in reason

    def test_get_ledger_calls_query_memory(self):
        """get_ledger → runtime_query_memory。"""
        query_result = {
            "jsonrpc": "2.0",
            "id": 2,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"records": [{"id": "1", "type": "TrapRecorded"}]}),
                    }
                ]
            },
        }
        adapter = MemGuardMCPAdapter()
        _attach_mock(adapter, _make_mock_proc([query_result]))

        ledger = adapter.get_ledger("test-project")
        assert ledger["records"][0]["type"] == "TrapRecorded"

        lines = _get_sent_messages(adapter)
        tool_call = [ln for ln in lines if ln.get("method") == "tools/call"][0]
        assert tool_call["params"]["name"] == "runtime_query_memory"
        assert "test-project" in tool_call["params"]["arguments"]["query_intent"]


class TestMemGuardMCPAdapterFactory:
    """验证工厂函数。"""

    @patch.dict(os.environ, {"RDI_MEMORY_ADAPTER": "memguard"}, clear=False)
    def test_factory_returns_memguard_adapter(self):
        adapter = get_memory_adapter()
        assert isinstance(adapter, MemGuardMCPAdapter)

    def test_factory_default_is_noop(self):
        adapter = get_memory_adapter()
        from reality_agent.adapters.memory_adapter import NoopMemoryAdapter
        assert isinstance(adapter, NoopMemoryAdapter)


class TestMemGuardMCPAdapterRealProbe:
    """
    真实 MemGuard MCP 进程探测测试（可选，需本地安装 npx 和 @henry_lhy/memguard-mcp）。
    标记为 slow/integration，CI 中默认跳过。
    """

    @pytest.mark.slow
    @pytest.mark.skipif(
        os.environ.get("MEMGUARD_MCP_PROBE") != "1",
        reason="Set MEMGUARD_MCP_PROBE=1 to run real MCP integration test",
    )
    def test_real_probe_bootstrap(self):
        adapter = MemGuardMCPAdapter()
        try:
            frozen, reason = adapter.is_project_frozen(os.getcwd())
            assert isinstance(frozen, bool)
            assert isinstance(reason, (str, type(None)))
        finally:
            adapter._close_proc()

    @pytest.mark.slow
    @pytest.mark.skipif(
        os.environ.get("MEMGUARD_MCP_PROBE") != "1",
        reason="Set MEMGUARD_MCP_PROBE=1 to run real MCP integration test",
    )
    def test_real_probe_commit_event(self):
        adapter = MemGuardMCPAdapter()
        try:
            ok = adapter.log_cognitive_debt({
                "project_id": "test-probe",
                "reason": "Integration test probe",
                "patch_description": "No-op patch",
            })
            assert isinstance(ok, bool)
        finally:
            adapter._close_proc()
