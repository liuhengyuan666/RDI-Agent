"""Reality-Driven Agent — CLI Console Entry (Phase 6)

Usage:
    rdi run --request "fix panic" --mode stub
    rdi run --request "optimize API" --mode real --commit
    rdi run --help

Phase 6 存储策略:
    - 默认仅向控制台打印结构化报告（scannable text）
    - 只有 --commit 显式为 True 时，才触发 MemoryAdapter 持久化写入
    - 人类拥有最终审计主权：默认不写入任何外部存储
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, Optional

from reality_agent.graph import compile_agent
from reality_agent.state import RealityAgentState


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rdi",
        description="Reality-Driven Iteration Agent — Evidence-First Cognitive Guard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  LLM_PROVIDER          openai | anthropic | deepseek (default: openai)
  LLM_MODEL             Model name (default: gpt-4o)
  LLM_BASE_URL          API base URL (for deepseek/local models)
  LLM_API_KEY           API key (or provider-specific env var)
  LLM_TEMPERATURE       0.0-1.0 (default: 0.0 for deterministic guardrails)
  RDI_LLM_MODE          stub | real (default: stub — use real to activate LLM)
  RDI_MEMORY_ADAPTER    stub | memguard | noop (default: stub; noop when --commit=False)
  RDI_REPRODUCE_COMMAND Reproduce script command
  RDI_BENCHMARK_COMMAND Benchmark command

Storage Strategy:
  --commit=False (default): Console-only report, NO persistent storage. Dry-run.
  --commit=True:            Activates MemoryAdapter (stub or memguard) to write.

Examples:
  # Dry-run: console report only, no storage
  rdi run --request "fix panic" --reproduce "pytest tests/test_panic.py"

  # Commit: persist cognitive debt / knowledge to MemoryAdapter
  rdi run --request "optimize API" --bench "cargo bench" --commit
        """,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- run subcommand ---
    run_parser = subparsers.add_parser(
        "run",
        help="Execute the full 7-step Reality-Driven Iteration loop",
    )
    run_parser.add_argument(
        "--request",
        type=str,
        required=True,
        help="The user's original request / issue description",
    )
    run_parser.add_argument(
        "--reproduce",
        type=str,
        dest="reproduce_cmd",
        help="Override RDI_REPRODUCE_COMMAND for this run (e.g., 'pytest tests/test_x.py')",
    )
    run_parser.add_argument(
        "--bench",
        type=str,
        dest="bench_cmd",
        help="Override RDI_BENCHMARK_COMMAND for this run (e.g., 'cargo bench')",
    )
    run_parser.add_argument(
        "--mode",
        type=str,
        choices=["stub", "real"],
        default=os.getenv("RDI_LLM_MODE", "stub"),
        help="LLM mode: stub=heuristic, real=activate LLM structured output (default: env or stub)",
    )
    run_parser.add_argument(
        "--project-id",
        type=str,
        default="default",
        help="Project identifier (default: default)",
    )
    run_parser.add_argument(
        "--logs",
        type=str,
        nargs="*",
        default=[],
        help="Optional log files or inline log strings to attach",
    )
    run_parser.add_argument(
        "--output",
        type=str,
        choices=["json", "text", "both"],
        default="text",
        help="Output format (default: text — scannable console report)",
    )
    run_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print intermediate node outputs and tool results",
    )
    run_parser.add_argument(
        "--commit",
        action="store_true",
        default=False,
        dest="commit",
        help="EXPLICITLY enable persistent storage write (default: False — human audit required)",
    )

    return parser


def _prepare_env(args: argparse.Namespace) -> None:
    """Apply CLI overrides to environment variables."""
    if args.reproduce_cmd:
        os.environ["RDI_REPRODUCE_COMMAND"] = args.reproduce_cmd
    if args.bench_cmd:
        os.environ["RDI_BENCHMARK_COMMAND"] = args.bench_cmd
    os.environ["RDI_LLM_MODE"] = args.mode

    # Phase 6: Storage strategy — default noop, --commit enables real adapter
    if not args.commit:
        # Human audit required: default to noop (no persistent storage)
        os.environ["RDI_MEMORY_ADAPTER"] = "noop"
    else:
        # --commit=True: use configured adapter (default stub if not set)
        if not os.getenv("RDI_MEMORY_ADAPTER"):
            os.environ["RDI_MEMORY_ADAPTER"] = "stub"


def _build_initial_state(args: argparse.Namespace) -> RealityAgentState:
    """Construct initial state from CLI arguments."""
    raw_logs = []
    for log_path in args.logs or []:
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                raw_logs.append(f.read())
        else:
            raw_logs.append(log_path)  # Treat as inline log string

    return RealityAgentState(
        user_request=args.request,
        raw_logs=raw_logs,
        frozen_project_id=args.project_id,
    )


def _format_output(
    final_state: Dict[str, Any],
    output_format: str,
    verbose: bool,
) -> str:
    """Format the final state for human or machine consumption."""
    lines = []

    # Header
    lines.append("=" * 60)
    lines.append(" Reality-Driven Iteration Agent — Result")
    lines.append("=" * 60)

    # Phase
    lines.append(f"\nFinal Phase: {final_state.get('current_phase', 'Unknown')}")
    lines.append(f"Evidence Level: {final_state.get('evidence_level', 'Unknown')}")
    lines.append(f"Provenance Verified: {final_state.get('provenance_verified', False)}")

    # Trap detection
    trap = final_state.get("trap_detected")
    if trap:
        lines.append(f"\n⚠️  Trap Detected: {trap}")
        details = final_state.get("trap_details")
        if details:
            lines.append(f"    Details: {details}")
    else:
        lines.append("\n✅ No traps detected")

    # Facts / Hypotheses
    facts = final_state.get("facts", [])
    if facts:
        lines.append(f"\n📋 Facts ({len(facts)}):")
        for f in facts:
            lines.append(f"   • {f}")

    hypotheses = final_state.get("hypotheses", [])
    if hypotheses:
        lines.append(f"\n❓ Hypotheses ({len(hypotheses)}):")
        for h in hypotheses:
            lines.append(f"   • {h}")

    # Knowledge gained
    knowledge = final_state.get("knowledge_gained", [])
    if knowledge:
        lines.append(f"\n🧠 Knowledge Gained ({len(knowledge)}):")
        for k in knowledge[-5:]:  # Show last 5
            lines.append(f"   • {k}")

    # Iteration summary
    summary = final_state.get("iteration_summary")
    if summary:
        lines.append("\n📊 Iteration Summary:")
        for key, val in summary.items():
            lines.append(f"   {key}: {val}")

    # Cognitive debt
    debt = final_state.get("cognitive_debt_added", False)
    if debt:
        lines.append("\n⚠️  COGNITIVE DEBT ADDED (unverified optimization)")
        records = final_state.get("cognitive_debt_records", [])
        for r in records:
            lines.append(f"   • {r}")

    # Freeze status
    freeze = final_state.get("freeze_until")
    if freeze:
        lines.append(f"\n🧊 Observation Freeze: {freeze}")

    # Tool outputs (verbose)
    if verbose:
        tool_outputs = final_state.get("tool_outputs", [])
        if tool_outputs:
            lines.append(f"\n🔧 Tool Outputs ({len(tool_outputs)}):")
            for to in tool_outputs[-3:]:
                lines.append(f"   {to[:200]}")

    # Storage audit trail
    adapter = os.getenv("RDI_MEMORY_ADAPTER", "noop")
    lines.append(f"\n💾 Storage: {adapter} ({'PERSISTED' if adapter != 'noop' else 'DRY-RUN'})")

    text_result = "\n".join(lines)

    if output_format == "text":
        return text_result
    elif output_format == "json":
        return json.dumps(final_state, indent=2, ensure_ascii=False, default=str)
    else:  # both
        return f"{text_result}\n\n{'='*60}\nJSON:\n{'='*60}\n{json.dumps(final_state, indent=2, ensure_ascii=False, default=str)}"


def _main() -> int:
    """Main entry point."""
    parser = _build_parser()
    args = parser.parse_args()

    if args.command != "run":
        parser.print_help()
        return 1

    # Apply env overrides (including storage strategy)
    _prepare_env(args)

    # Build initial state
    state = _build_initial_state(args)

    # Print config
    print("=" * 60, file=sys.stderr)
    print(" RDI Agent Launching", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"  LLM Mode: {args.mode}", file=sys.stderr)
    print(f"  LLM Provider: {os.getenv('LLM_PROVIDER', 'openai')}", file=sys.stderr)
    print(f"  LLM Model: {os.getenv('LLM_MODEL', 'gpt-4o')}", file=sys.stderr)
    print(f"  Memory Adapter: {os.getenv('RDI_MEMORY_ADAPTER', 'noop')}", file=sys.stderr)
    print(f"  Commit: {args.commit}", file=sys.stderr)
    print(f"  Reproduce CMD: {os.getenv('RDI_REPRODUCE_COMMAND', 'NOT SET')}", file=sys.stderr)
    print(f"  Benchmark CMD: {os.getenv('RDI_BENCHMARK_COMMAND', 'NOT SET')}", file=sys.stderr)
    print(f"  Project ID: {args.project_id}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    try:
        # Compile and run the agent
        agent = compile_agent()

        # Stream outputs for verbose mode
        if args.verbose:
            print("\n[Agent Stream]", file=sys.stderr)
            for step in agent.stream(state, stream_mode="values"):
                phase = step.get("current_phase", "unknown")
                print(f"  → Phase: {phase}", file=sys.stderr)

        final_state = agent.invoke(state)

        # Format and print output
        output = _format_output(final_state, args.output, args.verbose)
        print(output)

        # Exit code based on whether iteration was allowed
        if final_state.get("cognitive_debt_added"):
            return 2  # Unverified optimization (cognitive debt)
        if final_state.get("evidence_level") in ("Observation", "Hypothesis"):
            return 1  # Blocked by evidence gate (expected behavior)
        if final_state.get("trap_detected"):
            return 3  # Trap detected
        return 0  # Success

    except Exception as e:
        print(f"\n💥 Agent execution failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 255


if __name__ == "__main__":
    sys.exit(_main())
