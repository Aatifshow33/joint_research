"""SignalCourt paper-to-micro-live readiness bundle (non-executing)."""

from __future__ import annotations

from dataclasses import dataclass

from joint_research.signalcourt.decision_preview import SignalCourtDecisionPreview
from joint_research.signalcourt.execution_adapter import ExecutionAdapterResult
from joint_research.signalcourt.micro_live_gate import (
    MICRO_LIVE_VERDICT_PAPER_REVIEW_ONLY,
    MICRO_LIVE_VERDICT_REVIEW_READY,
    MicroLiveGateResult,
)
from joint_research.signalcourt.paper_fill_simulator import PaperFillSimulationResult
from joint_research.signalcourt.paper_order_preview import SignalCourtPaperOrderPreview
from joint_research.signalcourt.paper_performance_gate import (
    PERFORMANCE_VERDICT_REVIEW_ONLY,
    PaperPerformanceReviewResult,
)
from joint_research.signalcourt.risk_gate import DecisionPreviewRiskResult

READINESS_VERDICT_BLOCKED = "READINESS_BLOCKED"
READINESS_VERDICT_PAPER_CHAIN_ONLY = "PAPER_CHAIN_ONLY"
READINESS_VERDICT_PAPER_REVIEW_READY = "PAPER_REVIEW_READY"
READINESS_VERDICT_MICRO_LIVE_REVIEW_READY = "MICRO_LIVE_REVIEW_READY"
READINESS_VERDICT_LIVE_EXECUTION_BLOCKED = "LIVE_EXECUTION_BLOCKED"


@dataclass(frozen=True)
class SignalCourtReadinessBundle:
    run_id: str
    lane: str
    symbol: str
    venue: str
    final_readiness_verdict: str
    paper_chain_complete: bool
    paper_review_allowed: bool
    micro_live_review_ready: bool
    micro_live_execution_allowed: bool
    live_execution_allowed: bool
    order_submitted: bool
    broker_call_performed: bool
    exchange_call_performed: bool
    blocked_reasons: list[str]
    required_next_gates: list[str]
    stage_verdicts: dict[str, str]
    non_authorization_notice: str
    readiness_safety_metadata: dict[str, bool]


def build_readiness_bundle(
    *,
    decision_preview: SignalCourtDecisionPreview,
    decision_risk: DecisionPreviewRiskResult,
    paper_order_preview: SignalCourtPaperOrderPreview,
    paper_fill_result: PaperFillSimulationResult,
    paper_performance_result: PaperPerformanceReviewResult,
    execution_adapter_result: ExecutionAdapterResult,
    micro_live_gate_result: MicroLiveGateResult,
) -> SignalCourtReadinessBundle:
    blocked_reasons = _collect_blocked_reasons(
        decision_preview=decision_preview,
        decision_risk=decision_risk,
        paper_order_preview=paper_order_preview,
        paper_fill_result=paper_fill_result,
        paper_performance_result=paper_performance_result,
        execution_adapter_result=execution_adapter_result,
        micro_live_gate_result=micro_live_gate_result,
    )
    required_next_gates = _collect_required_next_gates(
        decision_preview=decision_preview,
        decision_risk=decision_risk,
        paper_order_preview=paper_order_preview,
        paper_fill_result=paper_fill_result,
        paper_performance_result=paper_performance_result,
        execution_adapter_result=execution_adapter_result,
        micro_live_gate_result=micro_live_gate_result,
    )
    stage_verdicts = {
        "decision_preview": decision_preview.decision_action,
        "risk_gate": decision_risk.risk_verdict,
        "paper_order_preview": paper_order_preview.paper_order_action,
        "paper_fill_simulation": paper_fill_result.simulated_fill_status,
        "paper_performance_gate": paper_performance_result.performance_verdict,
        "execution_adapter": execution_adapter_result.execution_verdict,
        "micro_live_gate": micro_live_gate_result.micro_live_verdict,
    }

    paper_chain_complete = True
    paper_review_allowed = False
    micro_live_review_ready = bool(
        micro_live_gate_result.micro_live_verdict == MICRO_LIVE_VERDICT_REVIEW_READY
        and not blocked_reasons
    )
    micro_live_execution_allowed = False
    live_execution_allowed = False
    order_submitted = False
    broker_call_performed = False
    exchange_call_performed = False

    final_readiness_verdict = _select_readiness_verdict(
        blocked_reasons=blocked_reasons,
        paper_performance_result=paper_performance_result,
        micro_live_gate_result=micro_live_gate_result,
        micro_live_review_ready=micro_live_review_ready,
    )

    non_authorization_notice = (
        f"{decision_preview.non_authorization_notice} "
        f"{decision_risk.non_authorization_notice} "
        f"{paper_order_preview.non_authorization_notice} "
        f"{paper_fill_result.non_authorization_notice} "
        f"{paper_performance_result.non_authorization_notice} "
        f"{execution_adapter_result.non_authorization_notice} "
        f"{micro_live_gate_result.non_authorization_notice} "
        "Readiness bundle is non-executing and does not authorize paper/live order submission, "
        "broker calls, exchange calls, API/LLM calls, or execution."
    ).strip()

    return SignalCourtReadinessBundle(
        run_id=decision_preview.run_id,
        lane=decision_preview.lane,
        symbol=paper_order_preview.symbol,
        venue=paper_order_preview.venue,
        final_readiness_verdict=final_readiness_verdict,
        paper_chain_complete=paper_chain_complete,
        paper_review_allowed=paper_review_allowed,
        micro_live_review_ready=micro_live_review_ready,
        micro_live_execution_allowed=micro_live_execution_allowed,
        live_execution_allowed=live_execution_allowed,
        order_submitted=order_submitted,
        broker_call_performed=broker_call_performed,
        exchange_call_performed=exchange_call_performed,
        blocked_reasons=blocked_reasons,
        required_next_gates=required_next_gates,
        stage_verdicts=stage_verdicts,
        non_authorization_notice=non_authorization_notice,
        readiness_safety_metadata={
            "execution_performed": False,
            "broker_call_performed": False,
            "exchange_call_performed": False,
            "live_order_submitted": False,
            "paper_order_submitted": False,
            "artifact_written": False,
            "ingestion_run": False,
            "readiness_bundle_only": True,
            "live_submit_command_available": False,
        },
    )


def _collect_blocked_reasons(
    *,
    decision_preview: SignalCourtDecisionPreview,
    decision_risk: DecisionPreviewRiskResult,
    paper_order_preview: SignalCourtPaperOrderPreview,
    paper_fill_result: PaperFillSimulationResult,
    paper_performance_result: PaperPerformanceReviewResult,
    execution_adapter_result: ExecutionAdapterResult,
    micro_live_gate_result: MicroLiveGateResult,
) -> list[str]:
    reasons = [
        *decision_preview.blocked_reasons,
        *decision_risk.blocked_reasons,
        *paper_order_preview.blocked_reasons,
        *paper_fill_result.blocked_reasons,
        *paper_performance_result.blocked_reasons,
        *execution_adapter_result.blocked_reasons,
        *micro_live_gate_result.blocked_reasons,
    ]

    if execution_adapter_result.order_submitted:
        reasons.append("execution adapter indicates order submitted")
    if execution_adapter_result.broker_call_performed:
        reasons.append("execution adapter indicates broker call performed")
    if execution_adapter_result.exchange_call_performed:
        reasons.append("execution adapter indicates exchange call performed")
    if micro_live_gate_result.micro_live_execution_allowed:
        reasons.append("micro-live gate indicates micro-live execution allowed")
    if micro_live_gate_result.live_execution_allowed:
        reasons.append("micro-live gate indicates live execution allowed")

    if _has_true_safety_flag(
        paper_fill_result.simulator_safety_metadata,
        keys=("execution_performed", "broker_call_performed", "exchange_call_performed", "live_order_submitted", "paper_order_submitted"),
    ):
        reasons.append("paper fill simulation contains execution-like safety flags")
    if _has_true_safety_flag(
        paper_performance_result.review_safety_metadata,
        keys=("execution_performed", "broker_call_performed", "exchange_call_performed", "live_order_submitted", "paper_order_submitted"),
    ):
        reasons.append("paper performance review contains execution-like safety flags")
    if _has_true_safety_flag(
        execution_adapter_result.adapter_safety_metadata,
        keys=("execution_performed", "broker_call_performed", "exchange_call_performed", "live_order_submitted", "paper_order_submitted"),
    ):
        reasons.append("execution adapter contains execution-like safety flags")
    if _has_true_safety_flag(
        micro_live_gate_result.gate_safety_metadata,
        keys=("execution_performed", "broker_call_performed", "exchange_call_performed", "live_order_submitted", "paper_order_submitted"),
    ):
        reasons.append("micro-live gate contains execution-like safety flags")

    return list(dict.fromkeys(reason for reason in reasons if reason))


def _collect_required_next_gates(
    *,
    decision_preview: SignalCourtDecisionPreview,
    decision_risk: DecisionPreviewRiskResult,
    paper_order_preview: SignalCourtPaperOrderPreview,
    paper_fill_result: PaperFillSimulationResult,
    paper_performance_result: PaperPerformanceReviewResult,
    execution_adapter_result: ExecutionAdapterResult,
    micro_live_gate_result: MicroLiveGateResult,
) -> list[str]:
    gates = [
        *decision_preview.required_next_gates,
        *decision_risk.required_next_gates,
        *paper_order_preview.required_next_gates,
        *paper_fill_result.required_next_gates,
        *paper_performance_result.required_next_gates,
        *execution_adapter_result.required_next_gates,
        *micro_live_gate_result.required_next_gates,
        "Readiness bundle remains non-executing until explicit future execution phases are approved.",
        "Keep golden evaluations passing.",
    ]
    return list(dict.fromkeys(gate for gate in gates if gate))


def _select_readiness_verdict(
    *,
    blocked_reasons: list[str],
    paper_performance_result: PaperPerformanceReviewResult,
    micro_live_gate_result: MicroLiveGateResult,
    micro_live_review_ready: bool,
) -> str:
    if micro_live_review_ready:
        return READINESS_VERDICT_MICRO_LIVE_REVIEW_READY
    if micro_live_gate_result.micro_live_verdict == "LIVE_EXECUTION_BLOCKED":
        return READINESS_VERDICT_LIVE_EXECUTION_BLOCKED
    if blocked_reasons:
        if (
            paper_performance_result.performance_verdict == PERFORMANCE_VERDICT_REVIEW_ONLY
            or micro_live_gate_result.micro_live_verdict == MICRO_LIVE_VERDICT_PAPER_REVIEW_ONLY
        ):
            return READINESS_VERDICT_PAPER_CHAIN_ONLY
        return READINESS_VERDICT_BLOCKED
    if paper_performance_result.paper_review_allowed:
        return READINESS_VERDICT_PAPER_REVIEW_READY
    return READINESS_VERDICT_PAPER_CHAIN_ONLY


def _has_true_safety_flag(metadata: dict[str, bool], *, keys: tuple[str, ...]) -> bool:
    return any(bool(metadata.get(key, False)) for key in keys)
