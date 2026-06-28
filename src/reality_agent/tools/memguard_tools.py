"""
Memguard integration — DEPRECATED in v1.

All memory operations in v1 go through the adapter layer:
  src/reality_agent/adapters/memory_adapter.py

This file is kept as a compatibility stub for v2 migration.
TODO: v2-memguard-mapping — replace with MemGuardMCPAdapter.
"""

from typing import Any, Dict, List, Optional

from reality_agent.adapters.memory_adapter import get_memory_adapter


def query_memguard_memory(project_id: str) -> List[Dict[str, Any]]:
    """Deprecated: use adapter.get_ledger(project_id) instead."""
    adapter = get_memory_adapter()
    return [adapter.get_ledger(project_id)]


def write_knowledge(record: Dict[str, Any]) -> bool:
    """Deprecated: use adapter.log_iteration_checkpoint() instead."""
    adapter = get_memory_adapter()
    return adapter.log_iteration_checkpoint(record)


def check_freeze_status(project_id: str) -> Optional[Dict[str, Any]]:
    """Deprecated: use adapter.is_project_frozen(project_id) instead."""
    adapter = get_memory_adapter()
    frozen, reason = adapter.is_project_frozen(project_id)
    if frozen:
        return {"frozen": True, "reason": reason}
    return None
