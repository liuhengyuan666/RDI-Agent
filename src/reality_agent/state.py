"""Reality-Driven Agent — State definition with immutable accumulation patterns."""

from operator import add
from typing import Annotated, List, Literal, Optional

from pydantic import BaseModel, Field


class RealityAgentState(BaseModel):
    """
    Core state machine for the Reality-Driven Iteration Agent.

    All list fields use Annotated[list, operator.add] to enforce
    **append-only accumulation** across LangGraph node transitions.
    This prevents later nodes from accidentally overwriting evidence
    collected by earlier nodes.
    """

    # ------------------------------------------------------------------
    # 1. Core cognitive phase (§1 七步框架)
    # ------------------------------------------------------------------
    current_phase: Literal[
        "Environment_Discovery",
        "Setup_Guide",
        "Reality_Check",
        "Measurement_Check",
        "Evidence_Gate",
        "Isolate_Iteration",
        "Build_Knowledge",
        "Observe_Freeze",
        "END",
    ] = Field(default="Environment_Discovery", description="当前所处的认知审计阶段")

    # ------------------------------------------------------------------
    # 2. Evidence accumulation (§2 Verify Reality, §4 Evidence Gate)
    # ------------------------------------------------------------------
    facts: Annotated[List[str], add] = Field(
        default_factory=list,
        description="已证实的客观事实 (Facts). 使用 operator.add 保证追加不覆盖.",
    )
    hypotheses: Annotated[List[str], add] = Field(
        default_factory=list,
        description="未经证实的假设 (Hypotheses). 使用 operator.add 保证追加不覆盖.",
    )
    evidence_level: Literal["Observation", "Hypothesis", "Evidence", "Verified"] = Field(
        default="Observation",
        description="当前证据等级",
    )

    # ------------------------------------------------------------------
    # 3. Measurement consistency (§3 Verify Measurement)
    # ------------------------------------------------------------------
    provenance_verified: bool = Field(
        default=False,
        description="数据来源与口径是否已验证一致",
    )
    data_sources_aligned: Optional[bool] = Field(
        default=None,
        description="Dashboard / Backtest / Report / DB 数字是否指向同一数据源",
    )
    time_window_aligned: Optional[bool] = Field(
        default=None,
        description="不同系统的观测时间是否对齐",
    )
    version_aligned: Optional[bool] = Field(
        default=None,
        description="代码版本、数据版本、配置版本是否一致",
    )
    snapshot_fresh: Optional[bool] = Field(
        default=None,
        description="缓存/快照是否已过期",
    )

    # ------------------------------------------------------------------
    # 4. Isolation iteration control (§5 Change One Thing)
    # ------------------------------------------------------------------
    variables_changed_count: int = Field(
        default=0,
        description="本次迭代中已修改的变量数 (严格限制为 0 或 1)",
    )
    pre_change_expected: Optional[str] = Field(
        default=None,
        description="修改前记录的预期结果",
    )
    post_change_actual: Optional[str] = Field(
        default=None,
        description="修改后实际观测到的结果",
    )
    change_accepted: Optional[bool] = Field(
        default=None,
        description="实际结果是否与预期一致，且深层机制已被解释",
    )

    # ------------------------------------------------------------------
    # 5. Knowledge & debt (§6 Build Knowledge, §13 Fallback)
    # ------------------------------------------------------------------
    knowledge_gained: Annotated[List[str], add] = Field(
        default_factory=list,
        description="本次迭代获得的可复用系统理解",
    )
    falsified_hypotheses: Annotated[List[str], add] = Field(
        default_factory=list,
        description="被证伪的假设，防止未来重复踩坑",
    )
    cognitive_debt_added: bool = Field(
        default=False,
        description="是否触发了 force_patch 降级，产生了认知债务",
    )
    cognitive_debt_records: Annotated[List[str], add] = Field(
        default_factory=list,
        description="认知债务明细记录",
    )

    # ------------------------------------------------------------------
    # 6. Trap detection (§9 Optimization Trap Detection)
    # ------------------------------------------------------------------
    trap_detected: Optional[str] = Field(
        default=None,
        description="检测到的优化陷阱类型: Explanation/MetricWorship/Narrative/Recency/Confirmation/PrematureTuning/None",
    )
    trap_details: Optional[str] = Field(
        default=None,
        description="陷阱的具体描述与拦截理由",
    )

    # ------------------------------------------------------------------
    # 7. Freeze & observe (§7 Freeze And Observe)
    # ------------------------------------------------------------------
    freeze_until: Optional[str] = Field(
        default=None,
        description="观察期冻结截止时间 (ISO-8601)",
    )
    freeze_reason: Optional[str] = Field(
        default=None,
        description="进入观察期的原因",
    )
    frozen_project_id: Optional[str] = Field(
        default=None,
        description="被冻结的项目/模块标识",
    )

    # ------------------------------------------------------------------
    # 8. Raw context from user / environment
    # ------------------------------------------------------------------
    user_request: str = Field(
        default="",
        description="用户的原始请求文本",
    )
    raw_logs: Annotated[List[str], add] = Field(
        default_factory=list,
        description="收集到的原始日志 / 堆栈 / 指标数据",
    )
    tool_outputs: Annotated[List[str], add] = Field(
        default_factory=list,
        description="工具调用返回的原始输出",
    )

    # ------------------------------------------------------------------
    # 10. Environment discovery (§0 Zero-Config)
    # ------------------------------------------------------------------
    detected_language: Optional[str] = Field(
        default=None,
        description="自动识别的项目语言: rust/python/go/node/polyglot/unknown",
    )
    toolchain_available: bool = Field(
        default=True,
        description="本地是否具备运行该语言工具链的环境",
    )
    setup_plan: Optional[str] = Field(
        default=None,
        description="当工具链缺失时，提供给人类的本地环境配置/安装指南",
    )

    # ------------------------------------------------------------------
    # 11. Structured observability log (§11)
    # ------------------------------------------------------------------
    iteration_summary: Optional[dict] = Field(
        default=None,
        description="第11节要求的结构化认知日志",
    )
