# RDI-Agent

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](pyproject.toml)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-green.svg)](https://langchain.com/langgraph)
[![Version](https://img.shields.io/badge/version-0.1.0-orange.svg)](https://github.com/liuhengyuan666/RDI-Agent)

> **Do not optimize on explanations. Optimize only on evidence.**
>
> A production-grade, runnable implementation of the Reality-Driven Iteration (RDI) SOP — a LangGraph-based cognitive guard agent that enforces Evidence-First auditing before any code modification.

This repository is the **reference implementation** of the [reality-driven-iteration](https://github.com/liuhengyuan666/reality-driven-iteration) behavioral SOP. While the skill version provides the cognitive contract, **RDI-Agent** provides the full execution infrastructure: subprocess tooling, LLM structured output, memory persistence, and a CLI with human-audit sovereignty.

---

## ⚡ Why This Agent?

| The Problem in Vanilla Agents | The RDI-Agent Way |
| :--- | :--- |
| **Shotgun debugging** — changing 10 things at once, not knowing which fixed it | **One variable at a time** — isolated iteration with mandatory mechanism explanation |
| **Metric worship** — "improve latency by 20%" without asking *why* | **Target the reality goal** — trace the metric back to the real-world objective it proxies |
| **Explanation-driven optimization** — "this sounds reasonable, let's try it" | **Evidence Gate** — three-tier lock: Observation → Hypothesis → Evidence |
| **Provenance blindness** — Dashboard shows A, Backtest shows B, database shows C | **Provenance Before Optimization** — confirm data source, time window, version, snapshot consistency |
| **Premature optimization** — refactoring before understanding the root cause | **Debug Pyramid** — lock reality → measurement → causality → implementation → assumption, bottom-up |
| **Over-optimization** — never stop tuning, never let the system run stable | **Freeze And Observe** — when stable, stop. Let the system speak. |
| **Cognitive debt** — "it works, don't touch it" | **Build Knowledge, Not Features** — every iteration must yield permanent understanding |

---

## 🧠 Core Philosophy: The 7-Step Loop

```text
Verify Reality          ← Is the phenomenon real?
    ↓
Verify Measurement      ← Is the data trustworthy? Sources aligned?
    ↓
Verify Causality        ← Is the cause proven, not just hypothesized?
    ↓ [Evidence Gate]
Change One Thing        ← Only one variable per iteration
    ↓
Build Knowledge         ← Record what we learned, what we falsified
    ↓
Freeze And Observe      ← Stop optimizing. Enter observation period.
    ↓
Reopen Only With Evidence ← New verifiable failure only
```

The agent installs a **cognitive circuit breaker** into the execution loop:

1. **Intercept** — Accept user request via CLI (`rdi run --request "..."`)
2. **Audit** — Run the 7-step Evidence-First loop via LangGraph
3. **Evidence Gate** — Only proceed if causality is verified
4. **Isolate** — Modify one variable at a time
5. **Explain** — If it works, say *why* with evidence
6. **Log** — Emit structured `iteration_summary` (knowledge, traps, debt)
7. **Freeze** — When stable, enter observation phase

---

## 🚀 Quick Start

### Installation

```bash
git clone git@github.com:liuhengyuan666/RDI-Agent.git
cd RDI-Agent
pip install -e ".[dev]"
```

### Dry Run (Console Report Only — No Persistent Storage)

```bash
# Default: --commit=False, RDI_MEMORY_ADAPTER=noop
# Prints a scannable text report to stdout, zero side effects
rdi run --request "fix timeout in payment API" \
  --reproduce "pytest tests/test_payment.py::test_timeout" \
  --mode stub
```

### Commit Mode (Persist to Memory)

```bash
# Explicitly enable persistence with --commit
# RDI_MEMORY_ADAPTER=stub (local JSON) or memguard (MCP server)
rdi run --request "optimize API latency" \
  --bench "locust -f load_test.py --headless" \
  --mode real \
  --commit
```

### Environment Configuration

```bash
export LLM_PROVIDER=deepseek
export LLM_MODEL=deepseek-v4-pro
export LLM_BASE_URL=https://api.deepseek.com/v1
export LLM_API_KEY=sk-...
export RDI_LLM_MODE=real       # stub=heuristic, real=activate LLM
export RDI_MEMORY_ADAPTER=noop  # noop=default, stub=local JSON, memguard=MCP
```

---

## 🎯 CLI Usage

```bash
rdi run --request "fix panic" --mode stub
rdi run --request "optimize API" --mode real --commit
rdi run --help
```

| Flag | Description | Default |
|------|-------------|---------|
| `--request` | User's original request / issue description | **Required** |
| `--reproduce` | Override reproduction command | `RDI_REPRODUCE_COMMAND` env |
| `--bench` | Override benchmark command | `RDI_BENCHMARK_COMMAND` env |
| `--mode` | `stub` (heuristic) or `real` (LLM) | `stub` |
| `--project-id` | Project identifier | `default` |
| `--logs` | Attach log files or inline strings | `[]` |
| `--output` | `text`, `json`, or `both` | `text` |
| `--verbose` | Print intermediate node outputs | `False` |
| `--commit` | **Explicitly enable persistent storage** | `False` |

**Human Audit Sovereignty:** By default, `--commit=False` means the agent runs in **dry-run mode** — it produces a scannable console report but **writes nothing to disk, no MCP server calls, no external side effects**. You must explicitly pass `--commit` to persist cognitive debt or knowledge.

---

## 🔧 The 7-Step Evidence-First Loop (Implementation)

The agent is implemented as a LangGraph state machine with 6 nodes and conditional routing:

### 1. Verify Reality (`reality_check`)
- Confirm the phenomenon exists (not cache, sampling, or version mismatch)
- List `[verified facts]` vs `[unverified assumptions]`
- LLM structured output with `RealityCheckBrainOutput` (stub mode uses heuristic fallback)

### 2. Verify Measurement (`measurement_check`)
- Provenance audit: Dashboard, Backtest, Report, DB — all aligned?
- Time window, version, snapshot consistency
- `MeasurementCheckBrainOutput` with 4 boolean alignment checks

### 3. Evidence Gate (`evidence_gate`)
- **Strict routing logic (no LLM):**
  - `Observation` → Block. Return to `build_knowledge`.
  - `Hypothesis` → Block. Return to `build_knowledge`.
  - `Evidence` + `provenance_verified=True` → Allow `isolate_iteration`.
  - `Verified` + `provenance_verified=True` → Allow `isolate_iteration`.
- Frozen project check via `MemoryAdapter.is_project_frozen()`

### 4. Change One Thing (`isolate_iteration`)
- One variable per iteration
- Record pre-change expected result; compare post-change actual
- If outcome diverges, re-enter Evidence Gate

### 5. Build Knowledge (`build_knowledge`)
- What did we discover? What did we rule out?
- Which assumption was falsified?
- Archive knowledge permanently via `MemoryAdapter`

### 6. Freeze And Observe (`observe_freeze`)
- When stable (`provenance_verified`, no trap, `change_accepted`), enter freeze
- `MemoryAdapter.log_freeze()` records observation period
- **Forbidden during freeze:** tuning, refactoring, new factors

### 7. Reopen Only With Evidence
- Only valid restart reason: **new, verifiable failure evidence**
- `MemoryAdapter.is_project_frozen()` enforces this across sessions

---

## 🛡️ Optimization Trap Detection

| Trap | Detection | Action |
|------|-----------|--------|
| **Explanation Trap** | Changing because explanation sounds reasonable | Stop. Demand evidence. |
| **Metric Worship** | Changing because metric can go higher | Stop. Trace to real-world goal. |
| **Narrative Bias** | Adjusting because market fits recent story | Stop. Narrative ≠ Evidence. |
| **Recency Bias** | Rushing because last run was bad | Stop. Check time window. |
| **Confirmation Bias** | Only looking for supporting data | Stop. Mandate counter-evidence. |
| **Premature Tuning** | Tuning before system is stable | Stop. Enter observation first. |

---

## 🏗️ Architecture

### Hexagonal Architecture (Port & Adapter)

```
┌─────────────────────────────────────────────────────────┐
│  LangGraph Nodes (Domain)                                │
│  ├── reality_check_node                                  │
│  ├── measurement_check_node                              │
│  ├── evidence_gate_node                                  │
│  ├── isolate_iteration_node                              │
│  ├── build_knowledge_node                                │
│  └── observe_freeze_node                                 │
│                                                          │
│  State: RealityAgentState (Pydantic, append-only lists)  │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  Port: RealityMemoryPort (Protocol)                       │
│  ├── is_project_frozen()                                │
│  ├── log_iteration_checkpoint()                           │
│  ├── log_cognitive_debt()                                 │
│  └── log_freeze()                                         │
└─────────────────────────────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
   │ NoopAdapter   │ │ StubAdapter │ │ MemGuardMCP │
   │ (default)     │ │ (local JSON) │ │ (MCP stdio) │
   └──────────────┘ └──────────────┘ └──────────────┘
```

### Memory Adapters

| Adapter | Side Effects | Use Case |
|---------|-------------|----------|
| `NoopMemoryAdapter` (default) | None | Dry-run, human audit sovereignty |
| `StubMemoryAdapter` | Writes `.reality_ledger.json` | Local persistence, no external deps |
| `MemGuardMCPAdapter` | JSON-RPC 2.0 over stdio to `memguard-mcp` | Cross-agent memory, enterprise audit |

### LLM Provider (Pluggable)

```python
LLM_PROVIDER=openai|anthropic|deepseek
LLM_MODEL=gpt-4o|claude-3-opus|deepseek-v4-pro
LLM_BASE_URL=https://api.deepseek.com/v1  # For DeepSeek/local
LLM_API_KEY=sk-...                           # Or provider-specific env var
LLM_TEMPERATURE=0.0                          # Deterministic guardrails
```

---

## 📂 Repository Structure

```text
RDI-Agent/
├── README.md                              # This file
├── LICENSE                                # MIT License
├── pyproject.toml                         # Package metadata & dependencies
├── .gitignore                             # Git ignore rules
│
├── src/reality_agent/                     # Core agent package
│   ├── __init__.py
│   ├── state.py                           # RealityAgentState (Pydantic, append-only)
│   ├── graph.py                           # LangGraph topology & routing
│   ├── cli.py                             # Console entry point (rdi run)
│   ├── llm.py                             # LLM provider factory (OpenAI/Anthropic/DeepSeek)
│   │
│   ├── adapters/                          # Memory persistence (Port & Adapter)
│   │   ├── __init__.py
│   │   └── memory_adapter.py             # Noop, Stub, MemGuardMCP adapters
│   │
│   ├── nodes/                             # LangGraph cognitive audit nodes
│   │   ├── __init__.py
│   │   ├── reality_check.py              # §1 Verify Reality
│   │   ├── measurement_check.py          # §2 Verify Measurement
│   │   ├── evidence_gate.py             # §3 Evidence Gate (routing)
│   │   ├── isolate_iteration.py          # §4 Change One Thing
│   │   ├── build_knowledge.py           # §5 Build Knowledge
│   │   └── observe_freeze.py            # §6 Freeze And Observe
│   │
│   ├── tools/                             # Subprocess execution tools
│   │   ├── __init__.py
│   │   ├── benchmark_tools.py            # Benchmark, flamegraph, differential test
│   │   ├── debug_tools.py                # Reproduce, git root, git consistency, env check
│   │   ├── traps_detection.py           # Trap detection logic
│   │   └── force_patch.py               # Fallback force patch (cognitive debt)
│   │
│   └── prompts/                         # LLM prompt templates
│       ├── reality_check.txt
│       ├── measurement_check.txt
│       └── traps_detection.txt
│
├── tests/                                 # 100 test cases (95 passed, 5 skipped)
│   ├── test_benchmark_tools.py
│   ├── test_debug_tools.py
│   ├── test_evidence_gate.py
│   ├── test_force_patch.py
│   ├── test_llm_structured_outputs.py    # DeepSeek real API tests (optional)
│   ├── test_measurement_rejection.py
│   ├── test_memory_adapter.py
│   ├── test_rdi_memguard_integration.py  # MCP mock integration tests
│   ├── test_state_transitions.py
│   └── test_success_criteria.py
│
├── memory/                                # Project memory (git-tracked)
│   ├── traps.md
│   └── decisions.md
│
└── .memguard/                             # MemGuard runtime state (git-ignored)
    ├── search_index.json
    └── runtime_state.json
```

---

## 🧪 Testing

```bash
# Full test suite (100 cases, 98 pass, 2 skip for optional real API)
pytest tests/ -v

# With DeepSeek real API (requires DEEPSEEK_API_KEY)
DEEPSEEK_API_KEY=sk-... pytest tests/test_llm_structured_outputs.py::TestDeepSeekRealAPI -v

# With MemGuard real MCP probe (requires npx + memguard-mcp)
MEMGUARD_MCP_PROBE=1 pytest tests/test_rdi_memguard_integration.py -v
```

---

## 🔌 MemGuard Integration (Optional)

RDI-Agent supports the [MemGuard MCP server](https://github.com/liuhengyuan666/memguard-mcp) for cross-agent persistent memory:

```bash
# Start memguard-mcp (handled automatically by MemGuardMCPAdapter)
npx -y @henry_lhy/memguard-mcp
```

```bash
# Use MemGuard as memory backend
export RDI_MEMORY_ADAPTER=memguard
rdi run --request "optimize API" --commit
```

The adapter implements the full JSON-RPC 2.0 stdio handshake:
- `initialize` → `initialized` notification
- `tools/call` with `runtime_bootstrap`, `runtime_commit_event`, `runtime_query_memory`
- Automatic payload mapping: `cognitive_debt` → `TrapRecorded`, `freeze` → `PhaseChanged`

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.

Copyright (c) 2026 Liu Hengyuan ([@liuhengyuan666](https://github.com/liuhengyuan666))

---

## 🔗 Related Projects

| Repository | Type | Description |
|------------|------|-------------|
| [reality-driven-iteration](https://github.com/liuhengyuan666/reality-driven-iteration) | Skill | Pure behavioral SOP for OpenCode/OhMyOpenAgent |
| [memguard-mcp](https://github.com/liuhengyuan666/memguard-mcp) | MCP Server | Persistent memory server for cross-agent audit |
| **RDI-Agent** | **Python Package** | This repo — runnable LangGraph implementation |

---

## 👤 Author

**Liu Hengyuan** ([@liuhengyuan666](https://github.com/liuhengyuan666))

- **Skill & SOP:** [reality-driven-iteration](https://github.com/liuhengyuan666/reality-driven-iteration)
- **Memory Infrastructure:** [memguard-mcp](https://github.com/liuhengyuan666/memguard-mcp)
- **Reference Implementation:** [RDI-Agent](https://github.com/liuhengyuan666/RDI-Agent)

---

## 🙏 Acknowledgments

This project implements the **Reality-Driven Iteration** SOP, a cognitive framework designed to prevent blind optimization and explanation-driven development in AI agents. The architecture is built on [LangGraph](https://langchain.com/langgraph) and follows hexagonal (Port & Adapter) patterns for maximum testability and pluggability.

> *"The only valid reason to modify: new evidence proves the system has a problem."*
