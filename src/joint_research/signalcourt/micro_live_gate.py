"""SignalCourt micro-live hard gate model (non-executing)."""

from __future__ import annotations

from dataclasses import dataclass

from joint_research.signalcourt.execution_adapter import (
    ADAPTER_MODE_LIVE_DISABLED,
    ExecutionAdapterResult,
)
from joint_research.signalcourt.paper_performance_gate import (
    PERFORMANCE_VERDICT_CANDIDATE,
    PERFORMANCE_VERDICT_REVIEW_ONLY,
    PaperPerformanceReviewResult,
)

MICRO_LIVE_VERDICT_BLOCKED = "MICRO_LIVE_BLOCKED"
MICRO_LIVE_VERDICT_PAPER_REVIEW_ONLY = "PAPER_REVIEW_ONLY"
MICRO_LIVE_VERDICT_REVIEW_READY = "MICRO_LIVE_REVIEW_READY"
MICRO_LIVE_VERDICT_LIVE_BLOCKED = "LIVE_EXECUTION_BLOCKED"
MICRO_LIVE_VERDICT_KILL_SWITCH_BLOCKED = "KILL_SWITCH_BLOCKED"
MICRO_LIVE_VERDICT_MANUAL_APPROVAL_REQUIRED = "MANUAL_APPROVAL_REQUIRED"


@dataclass(frozen=True)
class MicroLiveGatePolicy:
    micro_live_enabled: bool = False
    require_manual_approval: bool = True
    manual_approval_granted: bool = False
    kill_switch_enabled: bool = True
    max_micro_live_notional_usd: float = 5.0
    max_daily_loss_usd: float = 1.0
    max_session_loss_usd: float = 0.5
    allowlisted_symbols: tuple[str, ...] = ()
    allowlisted_venues: tuple[str, ...] = ()
    allow_market_orders: bool = False
    allow_leverage: bool = False
    require_paper_candidate: bool = True
    require_execution_adapter_live_disabled: bool = True
    require_no_execution_flags: bool = True
    require_golden_evaluations: bool = True
    require_operator_acknowledgement: bool = False


@dataclass(frozen=True)
class MicroLiveGateRequest:
    run_id: str
    lane: str
    symbol: str
    venue: str
    requested_notional_usd: float
    order_type: str
    leverage_requested: bool = False


@dataclass(frozen=True)
class MicroLiveGateResult:
    run_id: str
    lane: str
    symbol: str
    venue: str
    requested_notional_usd: float
    micro_live_verdict: str
    micro_live_review_ready: bool
    micro_live_execution_allowed: bool
    live_execution_allowed: bool
    blocked_reasons: list[str]
    required_next_gates: list[str]
    max_micro_live_notional_usd: float
    kill_switch_enabled: bool
    manual_approval_required: bool
    manual_approval_granted: bool
    non_authorization_notice: str
    gate_safety_metadata: dict[str, bool]


def default_micro_live_gate_policy() -> MicroLiveGatePolicy:
    return MicroLiveGatePolicy()


def build_micro_live_request(
    *,
    performance_result: PaperPerformanceReviewResult,
    execution_result: ExecutionAdapterResult,
    symbol: str = "",
    venue: str = "",
    requested_notional_usd: float = 0.0,
    order_type: str = "limit",
    leverage_requested: bool = False,
) -> MicroLiveGateRequest:
    return MicroLiveGateRequest(
        run_id=execution_result.run_id or performance_result.run_id,
        lane=execution_result.lane or performance_result.lane,
        symbol=symbol,
        venue=venue,
        requested_notional_usd=float(requested_notional_usd),
        order_type=order_type,
        leverage_requested=leverage_requested,
    )


def evaluate_micro_live_gate(
    *,
    performance_result: PaperPerformanceReviewResult,
    execution_result: ExecutionAdapterResult,
    policy: MicroLiveGatePolicy | None = None,
    request: MicroLiveGateRequest | None = None,
) -> MicroLiveGateResult:
    effective_policy = policy or default_micro_live_gate_policy()
    effective_request = request or build_micro_live_request(
        performance_result=performance_result,
        execution_result=execution_result,
    )
    blocked_reasons = _collect_blocked_reasons(
        performance_result=performance_result,
        execution_result=execution_result,
        policy=effective_policy,
        request=effective_request,
    )
    verdict = _select_verdict(
        blocked_reasons=blocked_reasons,
        policy=effective_policy,
        performance_result=performance_result,
    )
    review_ready = verdict == MICRO_LIVE_VERDICT_REVIEW_READY
    required_next_gates = _required_next_gates(
        blocked_reasons=blocked_reasons,
        policy=effective_policy,
    )
    notice = (
        f"{performance_result.non_authorization_notice} {execution_result.non_authorization_notice} "
        "Micro-live gate is a non-executing hard gate. It does not authorize order placement, "
        "broker calls, exchange calls, API/LLM calls, or live execution."
    ).strip()

    # Hard-off for this phase.
    micro_live_execution_allowed = False
    live_execution_allowed = False

    return MicroLiveGateResult(
        run_id=effective_request.run_id,
        lane=effective_request.lane,
        symbol=effective_request.symbol,
        venue=effective_request.venue,
        requested_notional_usd=effective_request.requested_notional_usd,
        micro_live_verdict=verdict,
        micro_live_review_ready=review_ready,
        micro_live_execution_allowed=micro_live_execution_allowed,
        live_execution_allowed=live_execution_allowed,
        blocked_reasons=blocked_reasons,
        required_next_gates=required_next_gates,
        max_micro_live_notional_usd=effective_policy.max_micro_live_notional_usd,
        kill_switch_enabled=effective_policy.kill_switch_enabled,
        manual_approval_required=effective_policy.require_manual_approval,
        manual_approval_granted=effective_policy.manual_approval_granted,
        non_authorization_notice=notice,
        gate_safety_metadata={
            "execution_performed": False,
            "broker_call_performed": False,
            "exchange_call_performed": False,
            "live_order_submitted": False,
            "paper_order_submitted": False,
            "artifact_written": False,
            "ingestion_run": False,
            "micro_live_gate_only": True,
            "live_submit_command_available": False,
        },
    )


def _collect_blocked_reasons(
    *,
    performance_result: PaperPerformanceReviewResult,
    execution_result: ExecutionAdapterResult,
    policy: MicroLiveGatePolicy,
    request: MicroLiveGateRequest,
) -> list[str]:
    reasons = list(performance_result.blocked_reasons)
    reasons.extend(execution_result.blocked_reasons)

    if policy.kill_switch_enabled:
        reasons.append("kill switch is enabled")
    if not policy.micro_live_enabled:
        reasons.append("micro-live is disabled by policy")
    if policy.require_manual_approval and not policy.manual_approval_granted:
        reasons.append("manual approval has not been granted")
    if policy.require_operator_acknowledgement:
        reasons.append("operator acknowledgement is required")
    if policy.max_micro_live_notional_usd > 0 and request.requested_notional_usd > policy.max_micro_live_notional_usd:
        reasons.append(
            f"requested notional {request.requested_notional_usd:.4f} exceeds max {policy.max_micro_live_notional_usd:.4f}"
        )
    if policy.allowlisted_symbols and request.symbol not in policy.allowlisted_symbols:
        reasons.append(f"symbol '{request.symbol}' is not allowlisted")
    if policy.allowlisted_venues and request.venue not in policy.allowlisted_venues:
        reasons.append(f"venue '{request.venue}' is not allowlisted")
    if request.order_type.lower() == "market" and not policy.allow_market_orders:
        reasons.append("market orders are disabled")
    if request.leverage_requested and not policy.allow_leverage:
        reasons.append("leverage is disabled")
    if execution_result.order_submitted:
        reasons.append("execution adapter indicates order was submitted")
    if execution_result.broker_call_performed:
        reasons.append("execution adapter indicates broker call was performed")
    if execution_result.exchange_call_performed:
        reasons.append("execution adapter indicates exchange call was performed")
    if policy.require_execution_adapter_live_disabled and execution_result.adapter_mode != ADAPTER_MODE_LIVE_DISABLED:
        reasons.append("execution adapter mode is not live-disabled")
    if execution_result.live_execution_allowed:
        reasons.append("execution adapter indicates live execution allowed")
    if execution_result.paper_execution_allowed:
        reasons.append("execution adapter indicates paper execution allowed")
    if policy.require_no_execution_flags and _has_execution_flags(execution_result):
        reasons.append("execution-like safety metadata detected")
    if policy.require_paper_candidate and performance_result.performance_verdict != PERFORMANCE_VERDICT_CANDIDATE:
        reasons.append("paper performance is not a paper candidate")

    return list(dict.fromkeys(reason for reason in reasons if reason))


def _has_execution_flags(execution_result: ExecutionAdapterResult) -> bool:
    keys = (
        "execution_performed",
        "broker_call_performed",
        "exchange_call_performed",
        "live_order_submitted",
        "paper_order_submitted",
    )
    return any(bool(execution_result.adapter_safety_metadata.get(key, False)) for key in keys)


def _select_verdict(
    *,
    blocked_reasons: list[str],
    policy: MicroLiveGatePolicy,
    performance_result: PaperPerformanceReviewResult,
) -> str:
    if policy.kill_switch_enabled:
        return MICRO_LIVE_VERDICT_KILL_SWITCH_BLOCKED
    if policy.require_manual_approval and not policy.manual_approval_granted:
        return MICRO_LIVE_VERDICT_MANUAL_APPROVAL_REQUIRED
    if any("live execution allowed" in reason for reason in blocked_reasons):
        return MICRO_LIVE_VERDICT_LIVE_BLOCKED
    if blocked_reasons:
        if performance_result.performance_verdict == PERFORMANCE_VERDICT_REVIEW_ONLY:
            return MICRO_LIVE_VERDICT_PAPER_REVIEW_ONLY
        return MICRO_LIVE_VERDICT_BLOCKED
    return MICRO_LIVE_VERDICT_REVIEW_READY


def _required_next_gates(
    *,
    blocked_reasons: list[str],
    policy: MicroLiveGatePolicy,
) -> list[str]:
    gates: list[str] = [
        "Keep golden evaluations passing.",
        "Micro-live gate does not enable execution in this phase.",
        "A future explicit live submit command and production controls are required before any live trading.",
    ]
    if not policy.micro_live_enabled:
        gates.append("Enable micro-live only in a future explicitly authorized phase.")
    if policy.require_manual_approval and not policy.manual_approval_granted:
        gates.append("Grant explicit manual approval before micro-live review readiness.")
    for reason in blocked_reasons:
        gates.append(f"Resolve blocker: {reason}")
    return list(dict.fromkeys(gates))
