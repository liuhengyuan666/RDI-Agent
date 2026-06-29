"""Environment Discovery Node — Zero-Config (§0).

Auto-discovers project language, verifies toolchain availability, and
hard-cuts the graph if infrastructure is missing (with setup guide)."""

import os
from typing import Any, Dict

from reality_agent.state import RealityAgentState
from reality_agent.tools.debug_tools import discover_project_language, verify_toolchain_executable


def environment_discovery_node(state: RealityAgentState) -> Dict[str, Any]:
    """
    §0 Environment Discovery — the first physical checkpoint before any LLM or probe.

    Steps:
    1. Scan cwd for language markers (Cargo.toml, go.mod, etc.)
    2. Check if toolchain executable exists in PATH
    3. If missing: mark toolchain_available=False, prepare setup_plan
    4. If present: mark toolchain_available=True, proceed silently

    Returns state updates (no side effects, no sys.exit).
    """
    lang = discover_project_language()
    available, detail = verify_toolchain_executable(lang)

    updates: Dict[str, Any] = {
        "current_phase": "Environment_Discovery",
        "detected_language": lang,
        "toolchain_available": available,
    }

    if not available:
        # Build a human-friendly setup guide (stub mode, zero LLM cost)
        setup_guide = _build_setup_guide(lang, detail)
        updates["setup_plan"] = setup_guide
        updates["knowledge_gained"] = [
            f"Environment Discovery: detected {lang}, but toolchain unavailable ({detail}). "
            "Halted before any static/runtime probe to prevent environment pollution."
        ]
    else:
        updates["knowledge_gained"] = [
            f"Environment Discovery: {lang} project detected, toolchain available at {detail}."
        ]

    return updates


def _build_setup_guide(lang: str, detail: str) -> str:
    """
    Build platform-aware setup guide (stub heuristic, zero LLM cost).
    
    Uses platform.system() with fallback for unknown OS.
    """
    import platform

    os_name = platform.system().lower()

    # Platform-specific package managers
    guides = {
        "rust": {
            "windows": (
                "[RDI Environment Alert] 检测到 Rust 项目 (Cargo.toml)，但本地缺少 'cargo' 编译器。\n\n"
                "请按照以下方案配置本地环境后重新运行 RDI：\n"
                "1. Windows (Scoop):  scoop install rustup\n"
                "2. Windows (Chocolatey): choco install rustup\n"
                "3. 官方安装: https://rustup.rs/\n\n"
                "RDI 进程已安全中断，未产生任何认知债务或代码污染。"
            ),
            "darwin": (
                "[RDI Environment Alert] 检测到 Rust 项目 (Cargo.toml)，但本地缺少 'cargo' 编译器。\n\n"
                "请按照以下方案配置本地环境后重新运行 RDI：\n"
                "1. macOS (Homebrew):  brew install rustup\n"
                "2. 官方安装: https://rustup.rs/\n\n"
                "RDI 进程已安全中断，未产生任何认知债务或代码污染。"
            ),
            "linux": (
                "[RDI Environment Alert] 检测到 Rust 项目 (Cargo.toml)，但本地缺少 'cargo' 编译器。\n\n"
                "请按照以下方案配置本地环境后重新运行 RDI：\n"
                "1. Ubuntu/Debian:  sudo apt install rustc cargo\n"
                "2. Fedora:  sudo dnf install rust cargo\n"
                "3. Arch:  sudo pacman -S rust\n"
                "4. 官方安装: https://rustup.rs/\n\n"
                "RDI 进程已安全中断，未产生任何认知债务或代码污染。"
            ),
            "fallback": (
                "[RDI Environment Alert] 检测到 Rust 项目 (Cargo.toml)，但本地缺少 'cargo' 编译器。\n\n"
                "请访问官方安装指南配置环境后重新运行 RDI：\n"
                "https://rustup.rs/\n\n"
                "RDI 进程已安全中断，未产生任何认知债务或代码污染。"
            ),
        },
        "go": {
            "windows": (
                "[RDI Environment Alert] 检测到 Go 项目 (go.mod)，但本地缺少 'go' 编译器。\n\n"
                "请按照以下方案配置本地环境后重新运行 RDI：\n"
                "1. Windows (Scoop):  scoop install go\n"
                "2. Windows (Chocolatey): choco install golang\n"
                "3. 官方安装: https://go.dev/dl/\n\n"
                "RDI 进程已安全中断，未产生任何认知债务或代码污染。"
            ),
            "darwin": (
                "[RDI Environment Alert] 检测到 Go 项目 (go.mod)，但本地缺少 'go' 编译器。\n\n"
                "请按照以下方案配置本地环境后重新运行 RDI：\n"
                "1. macOS (Homebrew):  brew install go\n"
                "2. 官方安装: https://go.dev/dl/\n\n"
                "RDI 进程已安全中断，未产生任何认知债务或代码污染。"
            ),
            "linux": (
                "[RDI Environment Alert] 检测到 Go 项目 (go.mod)，但本地缺少 'go' 编译器。\n\n"
                "请按照以下方案配置本地环境后重新运行 RDI：\n"
                "1. Ubuntu/Debian:  sudo apt install golang-go\n"
                "2. Fedora:  sudo dnf install golang\n"
                "3. Arch:  sudo pacman -S go\n"
                "4. 官方安装: https://go.dev/dl/\n\n"
                "RDI 进程已安全中断，未产生任何认知债务或代码污染。"
            ),
            "fallback": (
                "[RDI Environment Alert] 检测到 Go 项目 (go.mod)，但本地缺少 'go' 编译器。\n\n"
                "请访问官方安装指南配置环境后重新运行 RDI：\n"
                "https://go.dev/dl/\n\n"
                "RDI 进程已安全中断，未产生任何认知债务或代码污染。"
            ),
        },
        "python": {
            "windows": (
                "[RDI Environment Alert] 检测到 Python 项目，但本地缺少 'python' 解释器。\n\n"
                "请按照以下方案配置本地环境后重新运行 RDI：\n"
                "1. Windows (Microsoft Store): 搜索 'Python' 并安装\n"
                "2. Windows (Scoop):  scoop install python\n"
                "3. 官方安装: https://python.org/downloads/\n\n"
                "RDI 进程已安全中断，未产生任何认知债务或代码污染。"
            ),
            "darwin": (
                "[RDI Environment Alert] 检测到 Python 项目，但本地缺少 'python' 解释器。\n\n"
                "请按照以下方案配置本地环境后重新运行 RDI：\n"
                "1. macOS (Homebrew):  brew install python\n"
                "2. 官方安装: https://python.org/downloads/\n\n"
                "RDI 进程已安全中断，未产生任何认知债务或代码污染。"
            ),
            "linux": (
                "[RDI Environment Alert] 检测到 Python 项目，但本地缺少 'python' 解释器。\n\n"
                "请按照以下方案配置本地环境后重新运行 RDI：\n"
                "1. Ubuntu/Debian:  sudo apt install python3 python3-pip\n"
                "2. Fedora:  sudo dnf install python3\n"
                "3. Arch:  sudo pacman -S python\n"
                "4. 官方安装: https://python.org/downloads/\n\n"
                "RDI 进程已安全中断，未产生任何认知债务或代码污染。"
            ),
            "fallback": (
                "[RDI Environment Alert] 检测到 Python 项目，但本地缺少 'python' 解释器。\n\n"
                "请访问官方安装指南配置环境后重新运行 RDI：\n"
                "https://python.org/downloads/\n\n"
                "RDI 进程已安全中断，未产生任何认知债务或代码污染。"
            ),
        },
        "node": {
            "windows": (
                "[RDI Environment Alert] 检测到 Node.js 项目 (package.json)，但本地缺少 'node' 运行时。\n\n"
                "请按照以下方案配置本地环境后重新运行 RDI：\n"
                "1. Windows (Scoop):  scoop install nodejs\n"
                "2. Windows (Chocolatey): choco install nodejs\n"
                "3. 官方安装: https://nodejs.org/en/download/\n\n"
                "RDI 进程已安全中断，未产生任何认知债务或代码污染。"
            ),
            "darwin": (
                "[RDI Environment Alert] 检测到 Node.js 项目 (package.json)，但本地缺少 'node' 运行时。\n\n"
                "请按照以下方案配置本地环境后重新运行 RDI：\n"
                "1. macOS (Homebrew):  brew install node\n"
                "2. 官方安装: https://nodejs.org/en/download/\n\n"
                "RDI 进程已安全中断，未产生任何认知债务或代码污染。"
            ),
            "linux": (
                "[RDI Environment Alert] 检测到 Node.js 项目 (package.json)，但本地缺少 'node' 运行时。\n\n"
                "请按照以下方案配置本地环境后重新运行 RDI：\n"
                "1. Ubuntu/Debian:  sudo apt install nodejs npm\n"
                "2. Fedora:  sudo dnf install nodejs\n"
                "3. Arch:  sudo pacman -S nodejs npm\n"
                "4. 官方安装: https://nodejs.org/en/download/\n\n"
                "RDI 进程已安全中断，未产生任何认知债务或代码污染。"
            ),
            "fallback": (
                "[RDI Environment Alert] 检测到 Node.js 项目 (package.json)，但本地缺少 'node' 运行时。\n\n"
                "请访问官方安装指南配置环境后重新运行 RDI：\n"
                "https://nodejs.org/en/download/\n\n"
                "RDI 进程已安全中断，未产生任何认知债务或代码污染。"
            ),
        },
    }

    lang_guide = guides.get(lang, {})
    if not lang_guide:
        return (
            f"[RDI Environment Alert] 检测到未知项目类型，但工具链不可用 ({detail})。\n\n"
            f"请安装对应语言环境后重新运行 RDI。\n\n"
            f"RDI 进程已安全中断，未产生任何认知债务或代码污染。"
        )

    # Select platform-specific guide with fallback for unknown OS
    if os_name in ("windows", "darwin", "linux"):
        return lang_guide.get(os_name, lang_guide["fallback"])
    else:
        return lang_guide["fallback"]
