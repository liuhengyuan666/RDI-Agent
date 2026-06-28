"""
Cognitive Guard Memory Adapter — Port & Adapter Pattern (Hexagonal Architecture)

RDI Agent ↔ Memory Storage Boundary
====================================

v1: 零协议耦合 — 使用本地 JSON ledger，不依赖 MemGuard MCP 或 KnowledgeGuard。
v2: 无缝映射 — 新增 MemGuardMCPAdapter 实现同一 Protocol，将本地数据映射为
    MemGuard 事件 (TrapRecorded, PhaseChanged, TaskUpdated)。

TODO: v2-memguard-mapping
-----------------------
本地 Ledger 字段 → MemGuard 事件映射表:

| Ledger Key              | MemGuard Event           | Payload 字段                     |
|-------------------------|--------------------------|-----------------------------------|
| cognitive_debt[]        | TrapRecorded             | error_signature, solution          |
| knowledge_gained[]      | TrapRecorded (沉淀)       | error_signature="insight", solution  |
| freeze_until            | PhaseChanged             | new_phase="Observe", reason         |
| iteration_summary{}     | TaskUpdated (上下文)     | task_id, context_update             |

注意：MemGuard 有严格的 Payload Schema（-32602 验证），v2 实现必须加载
      references/trap-rules.md 和 references/phase-changed.md 后再实现。

TODO: v2-memguard-impl
----------------------
class MemGuardMCPAdapter(RealityMemoryPort):
    def __init__(self):
        self._mcp = MemGuardMCPClient()  # 需通过 MCP server 连接

    def is_project_frozen(self, project_id: str) -> tuple[bool, Optional[str]]:
        # 调用 memguard_runtime_bootstrap() → 解析 constraints
        # 若 current_phase == "Observe" 且 freeze_until 未过期 → 返回 (True, reason)
        ...

    def log_iteration_checkpoint(self, summary: Dict[str, Any]) -> bool:
        # 将 summary 组装为 TrapRecorded payload
        # 调用 memguard_runtime_commit_event(event_type="TrapRecorded", payload=...)
        ...

    def log_cognitive_debt(self, record: Dict[str, Any]) -> bool:
        # 映射为 TrapRecorded，solution 字段带 // WARNING: Cognitive Debt
        ...

    def log_freeze(self, project_id: str, freeze_until: str, reason: str) -> bool:
        # 映射为 PhaseChanged，new_phase="Observe_Freeze"
        ...
"""

import json
import os
from typing import Any, Dict, List, Optional, Protocol, Tuple

from reality_agent.state import RealityAgentState


# ---------------------------------------------------------------------------
# Port: 抽象协议（上层 LangGraph 节点只依赖此接口）
# ---------------------------------------------------------------------------

class RealityMemoryPort(Protocol):
    """
    RDI 认知防线专属记忆接口（Port）
    完全解耦底层实现，上层 LangGraph 节点只认这个接口。
    """

    def is_project_frozen(self, project_id: str) -> Tuple[bool, Optional[str]]:
        """
        §7: 检查项目是否处于 Freeze And Observe 观察期。

        Returns:
            (is_frozen, reason_or_none)
        """
        ...

    def log_iteration_checkpoint(self, summary: Dict[str, Any]) -> bool:
        """
        持久化 §11 的结构化输出 (Observability Log)。
        包括：knowledge_gained, trap_detected, cognitive_debt。
        """
        ...

    def log_cognitive_debt(self, record: Dict[str, Any]) -> bool:
        """
        §13: 记录因 force_patch 降级产生的认知债务。
        """
        ...

    def log_freeze(self, project_id: str, freeze_until: str, reason: str) -> bool:
        """
        §7: 记录项目进入观察期冻结。
        """
        ...

    def get_ledger(self, project_id: str) -> Dict[str, Any]:
        """
        读取指定项目的完整 ledger（调试用）。
        """
        ...


# ---------------------------------------------------------------------------
# Adapter v1: StubMemoryAdapter — 本地 JSON，零外部依赖
# ---------------------------------------------------------------------------

DEFAULT_LEDGER_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    ".reality_ledger.json",
)


class StubMemoryAdapter:
    """
    v1 本地轻量化实现。

    不依赖任何 MCP server、不读写 memory/*.md、不调用外部 API。
    所有数据持久化到本地 JSON 文件（默认：项目根目录 .reality_ledger.json）。
    """

    def __init__(self, ledger_path: Optional[str] = None) -> None:
        self._ledger_path = ledger_path or DEFAULT_LEDGER_PATH
        self._ensure_ledger()

    def _ensure_ledger(self) -> None:
        """如果 ledger 文件不存在，初始化空结构。"""
        if not os.path.exists(self._ledger_path):
            with open(self._ledger_path, "w", encoding="utf-8") as f:
                json.dump({"version": "v1", "projects": {}}, f, indent=2, ensure_ascii=False)

    def _load(self) -> Dict[str, Any]:
        with open(self._ledger_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, data: Dict[str, Any]) -> None:
        with open(self._ledger_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _get_project(self, ledger: Dict[str, Any], project_id: str) -> Dict[str, Any]:
        """获取或创建项目命名空间。"""
        if project_id not in ledger["projects"]:
            ledger["projects"][project_id] = {
                "debts": [],
                "checkpoints": [],
                "freezes": [],
                "knowledge": [],
            }
        return ledger["projects"][project_id]

    # -- Port Implementation --

    def is_project_frozen(self, project_id: str) -> Tuple[bool, Optional[str]]:
        ledger = self._load()
        proj = self._get_project(ledger, project_id)

        # 检查最新一条 freeze 记录
        for freeze in reversed(proj.get("freezes", [])):
            # v1 简化：只要存在 freeze 记录，就认为处于冻结
            # v2 应比较 freeze_until 与当前时间
            return True, freeze.get("reason")

        return False, None

    def log_iteration_checkpoint(self, summary: Dict[str, Any]) -> bool:
        ledger = self._load()
        project_id = summary.get("project_id", "default")
        proj = self._get_project(ledger, project_id)

        entry = {
            "timestamp": summary.get("timestamp", ""),
            "evidence_level": summary.get("evidence_level", ""),
            "trap_detected": summary.get("trap_detected", None),
            "knowledge_gained": summary.get("knowledge_gained", []),
        }
        proj["checkpoints"].append(entry)
        self._save(ledger)
        return True

    def log_cognitive_debt(self, record: Dict[str, Any]) -> bool:
        ledger = self._load()
        project_id = record.get("project_id", "default")
        proj = self._get_project(ledger, project_id)

        debt = {
            "timestamp": record.get("timestamp", ""),
            "reason": record.get("reason", ""),
            "patch_description": record.get("patch_description", ""),
            "warning": "WARNING: Unverified optimization. Cognitive Debt Added.",
        }
        proj["debts"].append(debt)
        self._save(ledger)
        return True

    def log_freeze(self, project_id: str, freeze_until: str, reason: str) -> bool:
        ledger = self._load()
        proj = self._get_project(ledger, project_id)

        freeze = {
            "freeze_until": freeze_until,
            "reason": reason,
        }
        proj["freezes"].append(freeze)
        self._save(ledger)
        return True

    def get_ledger(self, project_id: str) -> Dict[str, Any]:
        ledger = self._load()
        return self._get_project(ledger, project_id)


# ---------------------------------------------------------------------------
# Adapter v0.5: NoopMemoryAdapter — 默认不写入任何外部存储
# ---------------------------------------------------------------------------

class NoopMemoryAdapter:
    """
    Phase 6 默认适配器：人类审计主权模式。

    不写入任何文件、不连接任何 MCP server、不产生任何副作用。
    所有读取返回空值，所有写入返回 True（静默丢弃）。

    这是 rdi run 的默认行为。只有 --commit 时才切换到 Stub/MemGuard。
    """

    def is_project_frozen(self, project_id: str) -> Tuple[bool, Optional[str]]:
        return False, None

    def log_iteration_checkpoint(self, summary: Dict[str, Any]) -> bool:
        return True

    def log_cognitive_debt(self, record: Dict[str, Any]) -> bool:
        return True

    def log_freeze(self, project_id: str, freeze_until: str, reason: str) -> bool:
        return True

    def get_ledger(self, project_id: str) -> Dict[str, Any]:
        return {}


# ---------------------------------------------------------------------------
# Adapter v2: MemGuardMCPAdapter — stdio JSON-RPC 2.0 MCP 通信
# ---------------------------------------------------------------------------

import subprocess
import threading
import uuid


class MemGuardMCPAdapter:
    """
    Phase 6 完整实现：通过 stdio 与 @henry_lhy/memguard-mcp 进行 JSON-RPC 2.0 通信。

    协议确认（2025-06-27 探测）：
    - 启动: npx -y @henry_lhy/memguard-mcp (shell=True on Windows)
    - 握手: initialize → 响应 → notifications/initialized
    - 工具调用: method="tools/call", params={"name": "runtime_*", "arguments": {...}}
    - 响应格式: {"result": {"content": [{"type": "text", "text": "..."}]}}
    - 工具名（不带 memguard_ 前缀）: runtime_bootstrap, runtime_commit_event, runtime_query_memory, runtime_task_lookup

    事件映射:
    - is_project_frozen()    → runtime_bootstrap() → 解析 current_phase
    - log_cognitive_debt()   → runtime_commit_event("TrapRecorded", payload)
    - log_iteration_checkpoint() → runtime_commit_event("TrapRecorded", payload)
    - log_freeze()           → runtime_commit_event("PhaseChanged", payload)
    """

    _MCP_COMMAND = "npx -y @henry_lhy/memguard-mcp"
    _BOOTSTRAP_TOOL = "runtime_bootstrap"
    _COMMIT_TOOL = "runtime_commit_event"
    _QUERY_TOOL = "runtime_query_memory"
    _TIMEOUT_SECONDS = 15

    def __init__(self, project_root: Optional[str] = None) -> None:
        self._project_root = project_root or os.getcwd()
        self._proc: Optional[subprocess.Popen] = None
        self._connected = False
        self._lock = threading.Lock()
        self._req_id = 0

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def _ensure_connection(self) -> None:
        """惰性连接：启动 npx 进程，完成 MCP 握手."""
        if self._connected and self._proc is not None and self._proc.poll() is None:
            return

        with self._lock:
            if self._connected and self._proc is not None and self._proc.poll() is None:
                return

            # 关闭旧进程（如果有）
            self._close_proc()

            # 启动新进程
            try:
                self._proc = subprocess.Popen(
                    self._MCP_COMMAND,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    shell=True,
                    cwd=self._project_root,
                )
            except Exception as e:
                raise RuntimeError(f"Failed to start memguard-mcp: {e}")

            # 等待进程启动
            import time
            time.sleep(1.0)

            # 1. 发送 initialize 请求
            init_request = {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "rdi-agent", "version": "0.6.0"},
                },
            }
            self._send_raw(init_request)
            init_response = self._recv_raw(timeout=self._TIMEOUT_SECONDS)
            if init_response is None:
                raise RuntimeError("MCP initialize timeout: no response from memguard-mcp")
            if "error" in init_response:
                raise RuntimeError(f"MCP initialize error: {init_response.get('error')}")

            # 2. 发送 initialized 通知
            self._send_raw({"jsonrpc": "2.0", "method": "notifications/initialized"})

            self._connected = True

    def _send_raw(self, msg: Dict[str, Any]) -> None:
        """发送一条 JSON-RPC 消息（自动追加换行）."""
        if self._proc is None or self._proc.stdin is None:
            raise RuntimeError("MCP process not running")
        line = json.dumps(msg) + "\n"
        self._proc.stdin.write(line)
        self._proc.stdin.flush()

    def _recv_raw(self, timeout: int = 10) -> Optional[Dict[str, Any]]:
        """读取一条 JSON-RPC 响应（阻塞直到超时）."""
        if self._proc is None or self._proc.stdout is None:
            return None

        import select
        # Windows 不支持 select  on pipes, 使用轮询
        import time
        end_time = time.time() + timeout
        while time.time() < end_time:
            line = self._proc.stdout.readline()
            if line:
                try:
                    return json.loads(line.strip())
                except json.JSONDecodeError:
                    continue
            time.sleep(0.1)
        return None

    def _call_tool(self, name: str, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """调用 MCP 工具并返回 result 对象."""
        self._ensure_connection()
        request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        self._send_raw(request)
        response = self._recv_raw(timeout=self._TIMEOUT_SECONDS)
        if response is None:
            raise RuntimeError(f"MCP tool call timeout: {name}")
        if "error" in response:
            raise RuntimeError(f"MCP tool error ({name}): {response.get('error')}")
        return response.get("result")

    def _parse_tool_text(self, result: Optional[Dict[str, Any]]) -> str:
        """从 tools/call result 中提取 text content."""
        if not result:
            return ""
        content = result.get("content", [])
        if content and isinstance(content, list) and len(content) > 0:
            return content[0].get("text", "")
        return ""

    def _close_proc(self) -> None:
        """安全关闭 MCP 进程."""
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                pass
            finally:
                self._proc = None
                self._connected = False

    def __del__(self) -> None:
        self._close_proc()

    # -- Port Implementation --

    def is_project_frozen(self, project_id: str) -> Tuple[bool, Optional[str]]:
        """
        §7: 检查项目是否处于观察期冻结.

        调用 runtime_bootstrap → 解析 current_phase.
        若 current_phase 包含 "Observe" 或 "Freeze" → 返回 (True, reason).
        """
        try:
            result = self._call_tool(self._BOOTSTRAP_TOOL, {"project_root": self._project_root})
            text = self._parse_tool_text(result)
            if not text:
                return False, None

            data = json.loads(text)
            current_phase = data.get("current_phase", "")
            constraints = data.get("constraints", [])
            memory_health = data.get("memory_health", {})

            # 判断是否在观察期
            frozen = any(kw in current_phase.lower() for kw in ("observe", "freeze", "frozen"))
            reason = f"current_phase={current_phase}"
            if constraints:
                reason += f", constraints={constraints}"

            return frozen, reason if frozen else None

        except Exception as e:
            # 连接失败时保守返回：不冻结，但记录警告
            return False, f"MemGuard bootstrap failed: {e}"

    def log_iteration_checkpoint(self, summary: Dict[str, Any]) -> bool:
        """
        持久化 §11 的结构化输出.

        映射为 TrapRecorded 事件:
        payload: {"error_signature": "insight", "solution": <json summary>}
        """
        try:
            payload = {
                "error_signature": "insight",
                "solution": json.dumps(summary, ensure_ascii=False, default=str),
            }
            result = self._call_tool(self._COMMIT_TOOL, {
                "event_type": "TrapRecorded",
                "payload": payload,
            })
            text = self._parse_tool_text(result)
            return "successfully committed" in text.lower() or "committed" in text.lower()
        except Exception as e:
            return False

    def log_cognitive_debt(self, record: Dict[str, Any]) -> bool:
        """
        §13: 记录因 force_patch 降级产生的认知债务.

        映射为 TrapRecorded 事件:
        payload: {
            "error_signature": "cognitive_debt",
            "solution": record["patch_description"] + " // WARNING: Cognitive Debt"
        }
        """
        try:
            patch_desc = record.get("patch_description", "unknown")
            payload = {
                "error_signature": "cognitive_debt",
                "solution": f"{patch_desc} // WARNING: Cognitive Debt",
            }
            result = self._call_tool(self._COMMIT_TOOL, {
                "event_type": "TrapRecorded",
                "payload": payload,
            })
            text = self._parse_tool_text(result)
            return "successfully committed" in text.lower() or "committed" in text.lower()
        except Exception as e:
            return False

    def log_freeze(self, project_id: str, freeze_until: str, reason: str) -> bool:
        """
        §7: 记录项目进入观察期冻结.

        映射为 PhaseChanged 事件:
        payload: {"new_phase": "Observe_Freeze", "reason": reason, "freeze_until": freeze_until}
        """
        try:
            payload = {
                "new_phase": "Observe_Freeze",
                "reason": reason,
                "freeze_until": freeze_until,
            }
            result = self._call_tool(self._COMMIT_TOOL, {
                "event_type": "PhaseChanged",
                "payload": payload,
            })
            text = self._parse_tool_text(result)
            return "successfully committed" in text.lower() or "committed" in text.lower()
        except Exception as e:
            return False

    def get_ledger(self, project_id: str) -> Dict[str, Any]:
        """读取指定项目的完整 ledger（通过 runtime_query_memory）."""
        try:
            result = self._call_tool(self._QUERY_TOOL, {
                "query_intent": f"Get all records for project {project_id}",
                "limit": 10,
                "include_stale": True,
            })
            text = self._parse_tool_text(result)
            if text:
                return json.loads(text)
        except Exception:
            pass
        return {}


# ---------------------------------------------------------------------------
# 全局默认实例（v1 使用 Stub，v2 通过环境变量切换）
# ---------------------------------------------------------------------------

def get_memory_adapter() -> RealityMemoryPort:
    """
    工厂函数：根据环境变量返回合适的 MemoryAdapter 实例。

    Environment variables:
      RDI_MEMORY_ADAPTER (default: "noop")
        - "noop"      → NoopMemoryAdapter (Phase 6 默认，人类审计主权)
        - "stub"      → StubMemoryAdapter (本地 JSON)
        - "memguard"  → MemGuardMCPAdapter (v2 MCP stdio 连接)
    """
    adapter_type = os.getenv("RDI_MEMORY_ADAPTER", "noop").lower()
    if adapter_type == "noop":
        return NoopMemoryAdapter()
    if adapter_type == "stub":
        return StubMemoryAdapter()
    if adapter_type == "memguard":
        return MemGuardMCPAdapter()
    raise ValueError(f"Unsupported RDI_MEMORY_ADAPTER: {adapter_type}. Use 'noop', 'stub', or 'memguard'.")
