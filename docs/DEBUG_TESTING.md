# RDI-Agent Debug 能力实战测试指南

> **目标**：用一个真实项目验证 RDI-Agent 的端到端 debug 能力  
> **前提**：已完成 `pip install -e ".[dev]"` 和 `.env` 配置（可选）  
> **难度**：⭐⭐（stub 模式）/ ⭐⭐⭐（real 模式，需 API Key）

---

## 测试原理

RDI-Agent 的 debug 流程遵循 7 步框架，**现在从 §0 环境发现开始**：

```
用户请求:"修复 bug" → §0 Environment Discovery（自动检测语言+工具链+静态探针）→ §1 Verify Reality（复现）→ §2 Verify Measurement（确认）→ §3 Evidence Gate → §4 Change One Thing → §5 Build Knowledge → §6 Freeze
                     ↑                                    ↑
               三阶探针矩阵                              reproduce 工具执行测试脚本
               Static Check → Runtime Execution → LLM Analysis
```

**关键机制（三阶探针矩阵）：**

| 阶段 | 探针类型 | 何时运行 | 触发条件 |
|------|---------|---------|---------|
| **静态检查** | `cargo check`, `go build`, `python -m compileall .`, `npm run build` | §0 环境发现后 | 自动检测语言或 `RDI_STATIC_COMMAND` |
| **运行时执行** | Reproduce 脚本、Benchmark、Flamegraph | 静态检查通过后 | `--reproduce` 或 `RDI_REPRODUCE_COMMAND` |
| **LLM 分析** | 结构化推理（RealityCheck、MeasurementCheck） | 前两阶探针无法定位根因 | `--mode real` |

**升级规则：**
- 静态检查或运行时执行定位根因 → **跳过 LLM**，直接进入 `isolate_iteration`
- 两阶探针均无法定位 → **升级至 LLM 分析**
- 目标为 "investigate"（无复现）→ **跳过运行时探针**，进入 LLM 测量验证
- 静态检查编译失败 → **立即失败**，无需 LLM

**Zero-Config 环境发现：**
- `detected_language`：从 `Cargo.toml`/`go.mod`/`*.py`/`package.json` 自动推断
- `toolchain_available`：`shutil.which` 检查 `cargo`/`go`/`python`/`node`
- 工具链缺失 → `setup_guide_node` 触发，退出码 `4`，输出平台特定安装指南
- 语言无法识别 → 退出码 `5`，要求显式配置 `RDI_STATIC_COMMAND`

---

## 测试 1：快速验证（Stub 模式，无需 API Key）

### 步骤 1：创建带 Bug 的测试项目

在项目外创建测试目录：

```powershell
# 创建测试项目
mkdir C:\Temp\rdi-test-project
Set-Location C:\Temp\rdi-test-project

# 创建有 bug 的 Python 文件
@'
def divide(a, b):
    """意图：安全除法，但存在 bug"""
    return a / b  # Bug：未处理 b=0

def main():
    print("Starting calculation...")
    result = divide(10, 0)  # 触发 ZeroDivisionError
    print(f"Result: {result}")

if __name__ == "__main__":
    main()
'@ | Out-File -Encoding UTF8 buggy_app.py

# 创建测试脚本（Pytest 风格）
@'
import pytest
from buggy_app import divide

def test_divide_normal():
    assert divide(10, 2) == 5.0

def test_divide_by_zero():
    # 期望：返回 None 或抛出自定义异常
    # 实际：抛出 ZeroDivisionError（未捕获的 bug）
    with pytest.raises(ZeroDivisionError):
        divide(10, 0)  # 这条用例会暴露 bug

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
'@ | Out-File -Encoding UTF8 test_buggy.py
```

### 步骤 2：验证 Bug 真实存在

```powershell
python buggy_app.py
# 预期输出：ZeroDivisionError: division by zero

pytest test_buggy.py -v
# 预期：test_divide_by_zero PASSED（因为确实抛出了异常，但这不是设计意图）
```

### 步骤 3：运行 RDI-Agent（Stub 模式）

```powershell
# 返回 RDI-Agent 项目目录
Set-Location T:\work\RDIAgent

# 运行 debug 流程（stub 模式 = 本地启发式，不调用 LLM）
rdi run `
  --request "修复 divide 函数的除零崩溃" `
  --reproduce "python C:\Temp\rdi-test-project\buggy_app.py" `
  --mode stub `
  --verbose
```

### 步骤 4：解读输出

**预期输出结构（含 §0 环境发现）：**

```text
============================================================
 RDI Agent Launching
============================================================
  LLM Mode: stub
  Memory Adapter: noop
  Commit: False
  Reproduce CMD: python C:\Temp\rdi-test-project\buggy_app.py
============================================================

[Agent Stream]
  → Phase: Environment_Discovery
      Detected Language: python
      Toolchain Available: True
      Static Check: python -m compileall . (auto-detected)
      Static Check Result: PASS  ← 语法检查通过，无编译错误
  → Phase: Reality_Check
      Reproduce Output: ZeroDivisionError: division by zero
      Evidence Level: Observation
  → Phase: Measurement_Check
  → Phase: Evidence_Gate

============================================================
 Reality-Driven Iteration Agent — Result
============================================================

Final Phase: Evidence_Gate
Evidence Level: Observation        ← 因为 stub 模式看到日志中的 Traceback
Provenance Verified: False

⚠️  Trap Detected: Explanation
    Details: 日志显示异常，但未确认根因

📋 Facts (1):
   • 执行 reproduce 命令返回非零退出码

❓ Hypotheses (1):
   • 脚本在运行第 5 行时崩溃（ZeroDivisionError）

🧠 Knowledge Gained (0):

📊 Iteration Summary:
   evidence_level: Observation
   trap_detected: Explanation
   detected_language: python
   toolchain_available: True
   static_check_passed: True

⚠️  COGNITIVE DEBT ADDED (unverified optimization)
   • 仅看到崩溃日志，未隔离变量根因

💾 Storage: noop (DRY-RUN)
```

**关键判断：**
- `Detected Language: python` → 从 `*.py` 文件自动推断
- `Static Check Result: PASS` → 语法正确，无编译错误（如果编译失败会提前退出，无需 LLM）
- `Evidence Level: Observation` → 正确，因为只确认了现象（崩溃），未确认原因
- `Trap Detected: Explanation` → 正确，因为 `divide(10, 0)` 虽然解释了崩溃位置，但没有解释"为什么应该返回什么"
- 退出码：1（被 Evidence Gate 拦截，禁止修改）

---

## 测试 2：进阶验证（Real 模式，需 DeepSeek API Key）

### 步骤 1：确认环境变量

```powershell
# 检查 .env 是否加载（如果在 RDI-Agent 目录内）
python -c "import os; print('Key:', os.getenv('DEEPSEEK_API_KEY', 'NOT SET')[:20] + '...')"
# 预期：Key: sk-6decae528f0b4fc78...
```

### 步骤 2：运行 Real 模式

```powershell
Set-Location T:\work\RDIAgent

rdi run `
  --request "修复 divide 函数的除零崩溃，使其在 b=0 时返回 None" `
  --reproduce "python C:\Temp\rdi-test-project\buggy_app.py" `
  --mode real `
  --verbose `
  --project-id "rdi-test-divide-bug"
```

### 步骤 3：Real 模式的差异

与 Stub 模式不同，`reality_check_node` 会调用 LLM（DeepSeek）分析 `reproduce_issue` 的输出：

```python
# LLM 结构化输出（RealityCheckBrainOutput）
{
  "is_reproduced": True,
  "facts": ["ZeroDivisionError 在 divide(10, 0) 时触发"],
  "hypotheses": ["缺少对除数 b 的零值检查"],
  "evidence_level": "Hypothesis",  # 比 Observation 高一级，但仍不够
  "trap_detected": "Explanation",
  "trap_details": "用户要求修复'除零崩溃'，但日志本身已证明现象存在，无需额外解释"
}
```

**Evidence Gate 判断：**
- `Hypothesis` 级别 → 允许记录假设，但**禁止修改代码**（必须进入 `build_knowledge`）
- 要提升到 `Evidence` 级别，需要证明："修复后确实不再崩溃，且返回 None 是设计意图"

---

## 测试 3：验证"修复后"的场景（迭代验证）

### 步骤 1：先修复 Bug（手动模拟一次正确迭代）

```powershell
Set-Location C:\Temp\rdi-test-project

# 修复后的版本
@'
def divide(a, b):
    """安全除法：b=0 时返回 None"""
    if b == 0:
        return None
    return a / b

def main():
    print("Starting calculation...")
    result = divide(10, 0)
    print(f"Result: {result}")  # 应输出 None

if __name__ == "__main__":
    main()
'@ | Out-File -Encoding UTF8 buggy_app_fixed.py
```

### 步骤 2：运行差分测试（Differential Test）

RDI-Agent 支持 `run_differential_test` 工具，比较修改前后的输出：

```powershell
Set-Location T:\work\RDIAgent

# 创建 differential test 配置（可选，agent 会自动检测）
# 或直接用 CLI 模拟：
rdi run `
  --request "验证修复后的 divide 函数是否安全处理 b=0" `
  --reproduce "python C:\Temp\rdi-test-project\buggy_app_fixed.py" `
  --mode stub `
  --verbose
```

**预期输出变化：**
- `Evidence Level: Evidence` 或 `Verified`（因为退出码 0 + 输出包含 "None"）
- `trap_detected: None`（没有陷阱）
- Evidence Gate 放行 → 进入 `isolate_iteration` → 可以修改代码

---

## 测试 4：测量一致性陷阱（Provenance Audit）

### 场景：Dashboard 显示正常，但 CLI 报错

创建故意不一致的数据源：

```powershell
Set-Location C:\Temp\rdi-test-project

# 模拟"Dashboard 数据"（假数据，声称正常）
@'
{"status": "ok", "error_rate": 0.0}
'@ | Out-File -Encoding UTF8 dashboard_report.json

# 模拟"真实日志"（实际报错）
@'
[ERROR] 2025-06-28 10:00:01 ZeroDivisionError in divide()
[ERROR] 2025-06-28 10:00:02 ZeroDivisionError in divide()
[ERROR] 2025-06-28 10:00:03 ZeroDivisionError in divide()
'@ | Out-File -Encoding UTF8 error_logs.txt

# 创建需要检查数据源的 reproduce 脚本
@'
import json
import sys

# 读取 Dashboard（虚假信息）
with open("dashboard_report.json") as f:
    dash = json.load(f)

# 读取真实日志（实际故障）
with open("error_logs.txt") as f:
    logs = f.read()
    error_count = logs.count("ZeroDivisionError")

print(f"Dashboard says: {dash['status']}, error_rate={dash['error_rate']}")
print(f"Logs say: {error_count} errors in 3 seconds")

if error_count > 0 and dash['error_rate'] == 0.0:
    print("PROVENANCE MISMATCH: Dashboard and logs disagree!")
    sys.exit(1)
'@ | Out-File -Encoding UTF8 check_provenance.py
```

### 运行测试

```powershell
Set-Location T:\work\RDIAgent

rdi run `
  --request "Dashboard 显示正常但用户反馈报错，确认数据来源一致性" `
  --reproduce "python C:\Temp\rdi-test-project\check_provenance.py" `
  --mode stub `
  --verbose
```

**预期结果：**
- `measurement_check_node` 检测到 `provenance_verified: False`
- Evidence Gate 拦截（因为 `data_sources_aligned` 为 False）
- 要求用户先修复数据源一致性问题，再谈修复 bug

---

## 测试 5：Git 一致性检查（可选）

如果测试项目本身是一个 Git 仓库：

```powershell
Set-Location C:\Temp\rdi-test-project
git init
# 故意制造 dirty 状态（模拟开发中途修改）
"# dirty" >> buggy_app.py

git add -A
git commit -m "Initial commit"
# 修改但不提交
"# another change" >> buggy_app.py
```

然后运行：

```powershell
rdi run `
  --request "修复 divide 函数" `
  --reproduce "python C:\Temp\rdi-test-project\buggy_app.py" `
  --mode stub `
  --verbose
```

`measurement_check_node`（stub 模式）会检测到 Git dirty 状态，标记 `git_clean=False`，这可能导致 `provenance_verified` 降级，触发 Evidence Gate 拦截。

---

## 测试 6：环境发现缺失工具链（Exit Code 4）⭐ NEW

### 场景：项目语言已识别但工具链未安装

```powershell
Set-Location C:\Temp\rdi-test-project

# 创建一个 Rust 项目（但故意不安装 Rust 工具链）
@'
[package]
name = "rdi-test-rust"
version = "0.1.0"
edition = "2021"
'@ | Out-File -Encoding UTF8 Cargo.toml

@'
fn main() {
    println!("Hello, RDI!");
}
'@ | Out-File -Encoding UTF8 main.rs
```

### 运行测试

```powershell
Set-Location T:\work\RDIAgent

# 目标目录为 Rust 项目，但 cargo 未安装
rdi run `
  --request "修复 Rust 项目的编译错误" `
  --reproduce "cargo run --manifest-path C:\Temp\rdi-test-project\Cargo.toml" `
  --mode stub `
  --verbose
```

**预期结果：**
- `environment_discovery_node` 检测到 `Cargo.toml` → `detected_language = "rust"`
- `verify_toolchain_executable("cargo")` 返回 `False` → `toolchain_available = False`
- 路由至 `setup_guide_node`
- 输出平台特定安装指南（Windows: `scoop install rustup` / `winget install Rustlang.Rustup`）
- 退出码：`4`

**关键判断：**
- 退出码 `4` → 正确，工具链缺失
- `setup_guide` 包含具体安装命令 → 正确，平台感知
- 未尝试运行 reproduce 命令 → 正确，安全熔断

---

## 检查清单（每次测试后对照）

| 检查项 | 通过标准 | 失败含义 |
|--------|---------|---------|
| reproduce 命令确实执行了 | stderr 中显示 `[Agent Stream]` 有 reproduce 输出 | 工具未正确调用 |
| 环境发现正确识别语言 | `Detected Language` 与项目文件匹配 | 文件扫描逻辑错误 |
| 静态检查结果符合预期 | Python 语法错误 → 编译失败; 无错误 → PASS | 静态探针配置错误 |
| 退出码符合预期 | Observation=1, Hypothesis=1, Evidence=0, Verified=0, Missing Toolchain=4, Unsupported Language=5 | 拦截策略失效 |
| Trap 被正确识别 | Explanation Trap 在 stub 模式下被触发 | 陷阱检测失效 |
| 知识被记录 | `Knowledge Gained` 列表非空 | 记忆系统未激活 |
| 存储状态匹配 | `noop` 模式下不写入文件 | `Stub` 模式写入 `.reality_ledger.json` |

---

## 故障排查

### Q1: `rdi` 命令不存在

```powershell
# 确保在 RDI-Agent 目录内，且已安装
cd T:\work\RDIAgent
pip install -e .

# 如果仍然找不到，直接用 Python 模块方式运行
python -m reality_agent.cli run --request "..." --reproduce "..."
```

### Q2: Reproduce 命令返回"找不到文件"

路径问题：Windows 路径包含空格时需要用引号包裹。

```powershell
# 错误（如果路径有空格）
rdi run --reproduce "python C:\My Projects\test.py"

# 正确
rdi run --reproduce '"python "C:\My Projects\test.py""'
# 或移动项目到无空格路径
```

### Q3: Real 模式调用 DeepSeek 超时

```powershell
# 检查网络
Invoke-RestMethod -Uri "https://api.deepseek.com/v1" -Method Head

# 检查 API Key 是否有效（在 .env 中）
python -c "import os; print(os.getenv('DEEPSEEK_API_KEY')[:10])"

# 如果 Key 无效，stub 模式仍然可用
```

### Q4: 输出全是英文/不够详细

```powershell
# 添加 --verbose 和 --output both
rdi run --request "..." --reproduce "..." --verbose --output both
```

---

## 进阶：自定义测试场景

你可以替换 `C:\Temp\rdi-test-project` 中的内容，测试以下场景：

| 场景 | 预期 Trap | 预期 Evidence Level | 退出码 |
|------|-----------|---------------------|--------|
| 请求"优化性能"但无基准数据 | Metric Worship | Observation | 1 |
| 日志只有最近 1 小时的 | Recency Bias | Hypothesis | 1 |
| 声称"修复了"但无 reproduce | Explanation Trap | Observation | 1 |
| 修改 10 个文件后要求审查 | 被 Evidence Gate 拦截（multiple changes） | N/A | 1 |
| 数据源 A 和 B 显示不一致 | Provenance 失败 | Observation | 1 |
| 工具链缺失（cargo 未安装）| N/A（环境发现拦截）| N/A | 4 |
| 语言无法识别（无已知文件）| N/A（环境发现拦截）| N/A | 5 |
| 静态检查编译失败（语法错误）| N/A（立即失败）| N/A | 1 |

---

> **测试哲学**：真实的 bug 不是教科书上的例题，而是混乱的现实。RDI-Agent 的价值在于它拒绝在混乱中盲目行动，而是强制你提供**可复现的证据**、**可测量的改进**、**可解释的知识**。这份指南就是让你亲手制造混乱，然后验证 Agent 是否能守住防线。
