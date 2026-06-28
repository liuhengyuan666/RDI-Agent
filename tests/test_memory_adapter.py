"""Tests for Memory Adapter — Hexagonal Architecture Port/Adapter."""

import json
import os
import tempfile

from reality_agent.adapters.memory_adapter import StubMemoryAdapter, get_memory_adapter, NoopMemoryAdapter


class TestStubMemoryAdapter:
    """v1: 本地 JSON ledger，零外部依赖测试."""

    def test_adapter_initializes_ledger(self):
        """ledger 文件不存在时自动初始化."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "ledger.json")
            adapter = StubMemoryAdapter(ledger_path=path)
            assert os.path.exists(path)
            data = adapter.get_ledger("default")
            assert "debts" in data
            assert "checkpoints" in data
            assert "freezes" in data

    def test_log_cognitive_debt(self):
        """§13: 记录降级产生的认知债务."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "ledger.json")
            adapter = StubMemoryAdapter(ledger_path=path)
            result = adapter.log_cognitive_debt({
                "project_id": "test_proj",
                "reason": "Emergency timeout increase",
                "patch_description": "Changed timeout to 500ms",
            })
            assert result is True
            ledger = adapter.get_ledger("test_proj")
            assert len(ledger["debts"]) == 1
            assert "WARNING" in ledger["debts"][0]["warning"]
            assert "Cognitive Debt" in ledger["debts"][0]["warning"]

    def test_log_freeze(self):
        """§7: 记录观察期冻结."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "ledger.json")
            adapter = StubMemoryAdapter(ledger_path=path)
            adapter.log_freeze("test_proj", "2026-12-31", "Stable after bugfix")
            frozen, reason = adapter.is_project_frozen("test_proj")
            assert frozen is True
            assert "Stable after bugfix" in (reason or "")

    def test_is_project_not_frozen(self):
        """没有 freeze 记录时返回 False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "ledger.json")
            adapter = StubMemoryAdapter(ledger_path=path)
            frozen, reason = adapter.is_project_frozen("new_proj")
            assert frozen is False
            assert reason is None

    def test_log_iteration_checkpoint(self):
        """§11: 记录结构化观测日志."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "ledger.json")
            adapter = StubMemoryAdapter(ledger_path=path)
            summary = {
                "project_id": "test_proj",
                "timestamp": "2026-06-27T00:00:00Z",
                "evidence_level": "Evidence",
                "trap_detected": None,
                "knowledge_gained": ["Root cause identified as race condition."],
            }
            adapter.log_iteration_checkpoint(summary)
            ledger = adapter.get_ledger("test_proj")
            assert len(ledger["checkpoints"]) == 1
            assert ledger["checkpoints"][0]["evidence_level"] == "Evidence"

    def test_projects_isolated(self):
        """不同项目之间的 ledger 互不干扰."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "ledger.json")
            adapter = StubMemoryAdapter(ledger_path=path)
            adapter.log_freeze("proj_a", "2026-12-31", "Frozen")
            frozen_a, _ = adapter.is_project_frozen("proj_a")
            frozen_b, _ = adapter.is_project_frozen("proj_b")
            assert frozen_a is True
            assert frozen_b is False


class TestMemoryAdapterFactory:
    """工厂函数根据环境变量返回正确的适配器."""

    def test_default_returns_noop(self):
        """默认环境返回 NoopMemoryAdapter (Phase 6 人类审计主权)."""
        adapter = get_memory_adapter()
        assert isinstance(adapter, NoopMemoryAdapter)
