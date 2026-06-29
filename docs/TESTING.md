# RDI-Agent 本地测试操作手册

> **目标读者**：开发者、贡献者、CI/CD 维护者  
> **适用范围**：本地开发环境、预提交验证、CI 流水线  
> **更新日期**：2026-06-28  
> **配套版本**：v0.1.0

---

## 1. 前置条件

### 1.1 必需环境

| 组件 | 最低版本 | 验证命令 | 说明 |
|------|---------|----------|------|
| Python | 3.10+ | `python --version` | 项目使用 `match` 语法和 `typing.Annotated` |
| pip | 23.0+ | `pip --version` | 用于安装依赖 |
| Git | 2.30+ | `git --version` | 用于 MemGuard 工具链测试 |

### 1.2 可选环境（仅特定测试需要）

| 组件 | 验证命令 | 用途 |
|------|---------|------|
| Node.js + npx | `node --version` | MemGuard MCP 真实进程探测测试 |
| DeepSeek API Key | - | 真实 LLM API 抗噪测试 |
| Git 仓库 | `git status` | `CheckGitConsistency` 相关测试 |

### 1.3 环境快速检查

```bash
# 一键检查所有必需环境
python --version && pip --version && git --version

# 预期输出（示例）
# Python 3.14.5
# pip 25.0.0
# git version 2.48.0
```

---

## 2. 环境安装

### 2.1 克隆仓库（如未克隆）

```bash
git clone git@github.com:liuhengyuan666/RDI-Agent.git
cd RDI-Agent
```

### 2.2 安装依赖

```bash
# 基础依赖（运行必需）
pip install -e .

# 开发依赖（测试、代码检查）
pip install -e ".[dev]"
```

**依赖说明**：
- `langgraph>=0.2.0` — 图编排引擎
- `langchain-openai>=0.1.0` — OpenAI/DeepSeek 兼容 LLM 接口
- `pydantic>=2.0.0` — 结构化输出 Schema 验证
- `pytest>=8.0.0` — 测试框架

### 2.3 验证安装

```bash
python -c "from reality_agent.graph import compile_agent; print('Agent compiles OK')"
```

成功应输出：`Agent compiles OK`

---

## 3. 测试体系概览

### 3.1 测试矩阵（130 个用例）

| 测试模块 | 用例数 | 类型 | 外部依赖 | 平均耗时 |
|---------|--------|------|---------|---------|
| `test_benchmark_tools.py` | 12 | 单元测试 | 无（mock subprocess） | <1s |
| `test_debug_tools.py` | 8 | 单元测试 | Git 环境 | <1s |
| `test_environment_discovery.py` | 20 | 单元测试 | 无（mock filesystem） | <1s |
| `test_evidence_gate.py` | 6 | 单元测试 | 无 | <1s |
| `test_force_patch.py` | 4 | 单元测试 | 无 | <1s |
| `test_graph_routing.py` | 8 | 集成测试 | 无 | <1s |
| `test_llm_structured_outputs.py` | 12 | 集成测试 | 3个需真实 DeepSeek API | ~2-8s |
| `test_measurement_rejection.py` | 7 | 单元测试 | 无 | <1s |
| `test_memory_adapter.py` | 7 | 单元测试 | 无 | <1s |
| `test_rdi_memguard_integration.py` | 12 | 集成测试 | 2个需真实 npx/MCP | <2s |
| `test_setup_guide.py` | 3 | 单元测试 | 无 | <1s |
| `test_state_transitions.py` | 5 | 集成测试 | 无 | <1s |
| `test_success_criteria.py` | 6 | 集成测试 | 无 | <1s |

### 3.2 测试分类说明

- **🟢 必过测试（125 个）**：纯本地运行，零外部依赖， mock 隔离所有 I/O
- **🟡 可选测试（5 个）**：需配置环境变量激活，详见第 5 节

---

## 4. 运行测试

### 4.1 运行全部测试（推荐日常验证）

```bash
cd RDI-Agent
pytest tests/ -v
```

**预期输出**：
```text
============================= test session starts =============================
collected 130 items

tests/test_benchmark_tools.py::TestRunBenchmark::test_benchmark_success PASSED [  1%]
...
tests/test_success_criteria.py::TestSuccessCriteria::test_freeze_and_observe_recommended PASSED [100%]

================== 125 passed, 5 skipped in 6.86s ==================
```

> **说明**：5 个 skipped 是**预期行为**（见 4.4 节），不代表故障。

### 4.2 运行指定模块

```bash
# 仅测试内存适配器
pytest tests/test_memory_adapter.py -v

# 仅测试证据门路由
pytest tests/test_evidence_gate.py -v

# 仅测试环境发现（§0 Zero-Config）
pytest tests/test_environment_discovery.py -v
pytest tests/test_setup_guide.py -v
pytest tests/test_graph_routing.py -v

# 仅测试 MemGuard 集成（mock 版）
pytest tests/test_rdi_memguard_integration.py -v
```

### 4.3 运行指定用例

```bash
# 精确到类
pytest tests/test_benchmark_tools.py::TestRunBenchmark -v

# 精确到方法
pytest tests/test_evidence_gate.py::TestEvidenceGateRouting::test_observation_level_blocked -v

# 匹配关键字
pytest tests/ -k "freeze" -v
```

### 4.4 可选测试：真实 DeepSeek API

**用途**：验证 LLM 结构化输出在真实大模型上的抗噪能力（网络抖动、格式瑕疵）。

**前置条件**：拥有 DeepSeek API Key

```bash
# 方式 1：环境变量注入（推荐）
$env:DEEPSEEK_API_KEY = "sk-你的密钥"   # PowerShell
export DEEPSEEK_API_KEY=sk-你的密钥     # Bash

# 方式 2：直接在前缀中运行
$env:DEEPSEEK_API_KEY = "sk-..."; pytest tests/test_llm_structured_outputs.py::TestDeepSeekRealAPI -v
```

**预期输出**：
```text
tests/test_llm_structured_outputs.py::TestDeepSeekRealAPI::test_reality_check_structured_output_with_deepseek PASSED [ 33%]
tests/test_llm_structured_outputs.py::TestDeepSeekRealAPI::test_measurement_check_structured_output_with_deepseek PASSED [ 66%]
tests/test_llm_structured_outputs.py::TestDeepSeekRealAPI::test_deepseek_llm_factory PASSED [100%]

======================== 3 passed, 1 warning in 7.89s ==================
```

**故障排查**：
- 如果 3 个用例全部 `SKIPPED` → `DEEPSEEK_API_KEY` 未正确设置
- 如果 `test_deepseek_llm_factory` 失败 → 检查 `LLM_API_KEY` 或 `LLM_BASE_URL`
- 如果超时 → 检查网络连通性（`https://api.deepseek.com/v1`）

### 4.5 可选测试：真实 MemGuard MCP 进程

**用途**：验证 `MemGuardMCPAdapter` 与真实 `npx @henry_lhy/memguard-mcp` 的 stdio 通信。

**前置条件**：Node.js + npx 可用

```bash
# 设置环境变量后运行
$env:MEMGUARD_MCP_PROBE = "1"
pytest tests/test_rdi_memguard_integration.py::TestMemGuardMCPAdapterRealProbe -v
```

**预期输出**：
```text
tests/test_rdi_memguard_integration.py::TestMemGuardMCPAdapterRealProbe::test_real_probe_bootstrap PASSED
tests/test_rdi_memguard_integration.py::TestMemGuardMCPAdapterRealProbe::test_real_probe_commit_event PASSED
```

**注意**：若未安装 `@henry_lhy/memguard-mcp`，测试会自动失败或被跳过。

---

## 5. 环境变量配置指南

### 5.1 完整环境变量列表

```bash
# ── LLM 配置 ──
export LLM_PROVIDER=deepseek          # openai | anthropic | deepseek
export LLM_MODEL=deepseek-v4-pro
export LLM_BASE_URL=https://api.deepseek.com/v1
export LLM_API_KEY=sk-...            # 或 provider 特定 key
export LLM_TEMPERATURE=0.0           # 0.0 = 确定性守卫模式

# ── RDI 运行模式 ──
export RDI_LLM_MODE=stub            # stub=启发式 | real=激活 LLM
export RDI_MEMORY_ADAPTER=noop        # noop=默认 | stub=本地JSON | memguard=MCP

# ── 测试专用 ──
export DEEPSEEK_API_KEY=sk-...       # 4.4 节真实 API 测试
export MEMGUARD_MCP_PROBE=1          # 4.5 节真实 MCP 探测

# ── 工具链配置（可选） ──
export RDI_REPRODUCE_COMMAND="pytest tests/test_bug.py"
export RDI_BENCHMARK_COMMAND="cargo bench"
```

### 5.2 PowerShell 环境配置（Windows）

```powershell
# 设置
$env:DEEPSEEK_API_KEY = "sk-你的DeepSeek密钥"
$env:RDI_LLM_MODE = "real"
$env:LLM_PROVIDER = "deepseek"

# 查看
$env:DEEPSEEK_API_KEY

# 临时运行测试（当前会话有效）
$env:DEEPSEEK_API_KEY = "sk-..."; pytest tests/test_llm_structured_outputs.py::TestDeepSeekRealAPI -v
```

### 5.3 Bash 环境配置（Linux/macOS）

```bash
# 设置
export DEEPSEEK_API_KEY=sk-...
export RDI_LLM_MODE=real

# 持久化（写入 ~/.bashrc 或 ~/.zshrc）
echo 'export DEEPSEEK_API_KEY=sk-...' >> ~/.bashrc
source ~/.bashrc
```

---

## 6. 测试调试指南

### 6.1 查看详细失败信息

```bash
# 显示完整的 traceback 和局部变量
pytest tests/ -v --tb=long

# 失败时自动进入 PDB 调试
pytest tests/ -v --pdb

# 仅重新运行上次失败的测试
pytest tests/ --lf
```

### 6.2 常见失败场景与修复

| 现象 | 原因 | 修复 |
|------|------|------|
| `ModuleNotFoundError` | 未安装依赖 | `pip install -e ".[dev]"` |
| `5 skipped` 且期望通过 | 缺少 `DEEPSEEK_API_KEY` | 按 4.4 节设置 API Key |
| `SKIPPED` 在 `TestDeepSeekRealAPI` | `LLM_API_KEY` 未正确传递 | 检查 `patch.dict` 和 `os.environ` 时序 |
| `MemGuard bootstrap failed` | 未安装 `npx @henry_lhy/memguard-mcp` | 这是预期行为，mock 测试仍通过 |
| `AssertionError` 在 `test_default_returns_noop` | 环境变量污染 | `RDI_MEMORY_ADAPTER` 被设置为非 `noop` | 检查并清除 `env:RDI_MEMORY_ADAPTER` |
| `pytest` 命令不存在 | 未安装 pytest | `pip install pytest` 或 `pip install -e ".[dev]"` |

### 6.3 测试覆盖率检查（可选）

```bash
# 安装覆盖率插件
pip install pytest-cov

# 运行并生成报告
pytest tests/ --cov=src/reality_agent --cov-report=term-missing

# 生成 HTML 报告
pytest tests/ --cov=src/reality_agent --cov-report=html
# 查看 htmlcov/index.html
```

---

## 7. 代码质量检查（可选）

```bash
# 代码格式化（Black）
black src/ tests/

# 代码风格检查（Ruff）
ruff check src/ tests/

# 类型检查（mypy）
mypy src/
```

---

## 8. CI/CD 流水线配置建议

### 8.1 GitHub Actions 示例（`.github/workflows/test.yml`）

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: pip install -e ".[dev]"

      - name: Run tests
        run: pytest tests/ -v --tb=short
        # 预期：125 passed, 5 skipped（无需 DeepSeek API Key）

      # 可选：仅在有密钥时运行真实 API 测试
      - name: Run DeepSeek real API tests
        if: env.DEEPSEEK_API_KEY != ''
        run: pytest tests/test_llm_structured_outputs.py::TestDeepSeekRealAPI -v
        env:
          DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
```

### 8.2 测试策略建议

| 场景 | 运行命令 | 预期结果 |
|------|---------|---------|
| 日常开发 | `pytest tests/ -v` | 125 passed, 5 skipped |
| 预提交检查 | `pytest tests/ -v --tb=short` | 同上 |
| 发布前验证 | `pytest tests/ -v` + 手动运行可选测试 | 130 passed |
| CI 流水线 | `pytest tests/ -v` | 125 passed, 5 skipped（无需 secrets） |

---

## 9. 快速故障排查清单

```bash
# 1. 验证 Python 版本
python --version                          # 应 >= 3.10

# 2. 验证依赖安装
python -c "import langgraph, pydantic, pytest; print('OK')"

# 3. 验证 Agent 编译
python -c "from reality_agent.graph import compile_agent; compile_agent(); print('OK')"

# 4. 运行必过测试
pytest tests/ -q                          # 应显示 125 passed, 5 skipped

# 5. 验证环境变量（如有 API Key）
python -c "import os; print('DEEPSEEK_API_KEY:', bool(os.getenv('DEEPSEEK_API_KEY')))"

# 6. 运行指定可选测试
pytest tests/test_llm_structured_outputs.py::TestDeepSeekRealAPI -v
```

---

## 10. 获取帮助

- **测试架构问题**：查看 `tests/` 目录内各文件顶部的模块 docstring
- **Agent 行为问题**：参考 `memory/decisions.md` 和 `memory/traps.md`
- **MemGuard 集成**：参考 `src/reality_agent/adapters/memory_adapter.py` 中的 `MemGuardMCPAdapter` 类注释
- **Issue 上报**：请访问 [GitHub Issues](https://github.com/liuhengyuan666/RDI-Agent/issues)

---

> **测试哲学**：RDI-Agent 自身遵循 Evidence-First 原则。测试即证据——每个测试用例都是对人类审计主权的承诺。
