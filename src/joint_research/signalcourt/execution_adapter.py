"""SignalCourt execution adapter boundary with live-disabled default behavior."""

from __future__ import annotations

from dataclasses import dataclass

from joint_research.signalcourt.paper_fill_simulator import PaperFillSimulationResult
from joint_research.signalcourt.paper_order_preview import SignalCourtPaperOrderPreview
from joint_research.signalcourt.paper_performance_gate import PaperPerformanceReviewResult

ADAPTER_MODE_LIVE_DISABLED = "LIVE_DISABLED"
ADAPTER_MODE_PAPER_ONLY = "PAPER_ONLY"
ADAPTER_MODE_DRY_RUN = "DRY_RUN"

EXECUTION_VERDICT_BLOCKED = "EXECUTION_BLOCKED"
EXECUTION_VERDICT_PAPER_DRY_RUN_ONLY = "PAPER_DRY_RUN_ONLY"
EXECUTION_VERDICT_LIVE_DISABLED = "LIVE_DISABLED"
EXECUTION_VERDICT_KILL_SWITCH_BLOCKED = "KILL_SWITCH_BLOCKED"
EXECUTION_VERDICT_MANUAL_APPROVAL_REQUIRED = "MANUAL_APPROVAL_REQUIRED"


@dataclass(frozen=True)
class ExecutionAdapterPolicy:
    live_trading_enabled: bool = False
    paper_trading_enabled: bool = False
    require_manual_approval: bool = True
    kill_switch_enabled: bool = True
    max_notional_usd: float = 25.0
    allowlisted_symbols: tuple[str, ...] = ()
    allowlisted_venues: tuple[str, ...] = ()
    allow_market_orders: bool = False
    allow_leverage: bool = False
    adapter_mode: str = ADAPTER_MODE_LIVE_DISABLED


@dataclass(frozen=True)
class ExecutionRequest:
    run_id: str
    lane: str
    symbol: str
    side: str
    quantity: float
    limit_price: float
    notional_usd: float
    venue: str
    order_type: str
    requested_mode: str


@dataclass(frozen=True)
class ExecutionAdapterResult:
    run_id: str
    lane: str
    adapter_mode: str
    requested_mode: str
    execution_verdict: str
    paper_execution_allowed: bool
    live_execution_allowed: bool
    order_submitted: bool
    broker_call_performed: bool
    exchange_call_performed: bool
    blocked_reasons: list[str]
    required_next_gates: list[str]
    non_authorization_notice: str
    adapter_safety_metadata: dict[str, bool]


def default_execution_adapter_policy() -> ExecutionAdapterPolicy:
    return ExecutionAdapterPolicy()


def build_execution_request_from_preview(
    preview: SignalCourtPaperOrderPreview,
    *,
    requested_mode: str = ADAPTER_MODE_LIVE_DISABLED,
) -> ExecutionRequest:
    return ExecutionRequest(
        run_id=preview.run_id,
        lane=preview.lane,
        symbol=preview.symbol,
        side=preview.side,
        quantity=float(preview.quantity),
        limit_price=float(preview.limit_price),
        notional_usd=float(preview.notional_usd),
        venue=preview.venue,
        order_type=preview.order_type,
        requested_mode=requested_mode,
    )


def evaluate_execution_adapter(
    *,
    preview: SignalCourtPaperOrderPreview,
    fill_result: PaperFillSimulationResult,
    performance_result: PaperPerformanceReviewResult,
    request: ExecutionRequest | None = None,
    policy: ExecutionAdapterPolicy | None = None,
) -> ExecutionAdapterResult:
    effective_policy = policy or default_execution_adapter_policy()
    effective_request = request or build_execution_request_from_preview(
        preview,
        requested_mode=effective_policy.adapter_mode,
    )

    blocked_reasons = _collect_blocked_reasons(
        preview=preview,
        fill_result=fill_result,
        performance_result=performance_result,
        request=effective_request,
        policy=effective_policy,
    )
    verdict = _select_verdict(blocked_reasons=blocked_reasons, policy=effective_policy)
    next_gates = _required_next_gates(blocked_reasons=blocked_reasons)
    notice = (
        f"{preview.non_authorization_notice} {fill_result.non_authorization_notice} "
        f"{performance_result.non_authorization_notice} Execution adapter is non-executing and "
        "does not authorize paper/live order placement, broker calls, exchange calls, API/LLM calls, "
        "or execution."
    ).strip()

    # Hard-off in this phase: no paper/live execution allowed.
    paper_execution_allowed = False
    live_execution_allowed = False

    return ExecutionAdapterResult(
        run_id=effective_request.run_id,
        lane=effective_request.lane,
        adapter_mode=effective_policy.adapter_mode,
        requested_mode=effective_request.requested_mode,
        execution_verdict=verdict,
        paper_execution_allowed=paper_execution_allowed,
        live_execution_allowed=live_execution_allowed,
        order_submitted=False,
        broker_call_performed=False,
        exchange_call_performed=False,
        blocked_reasons=blocked_reasons,
        required_next_gates=next_gates,
        non_authorization_notice=notice,
        adapter_safety_metadata={
            "execution_performed": False,
            "broker_call_performed": False,
            "exchange_call_performed": False,
            "live_order_submitted": False,
            "paper_order_submitted": False,
            "artifact_written": False,
            "ingestion_run": False,
            "live_disabled_by_default": True,
        },
    )


def _collect_blocked_reasons(
    *,
    preview: SignalCourtPaperOrderPreview,
    fill_result: PaperFillSimulationResult,
    performance_result: PaperPerformanceReviewResult,
    request: ExecutionRequest,
    policy: ExecutionAdapterPolicy,
) -> list[str]:
    reasons = list(preview.blocked_reasons)
    reasons.extend(fill_result.blocked_reasons)
    reasons.extend(performance_result.blocked_reasons)

    if policy.kill_switch_enabled:
        reasons.append("kill switch is enabled")
    if not policy.live_trading_enabled:
        reasons.append("live trading is disabled by policy")
    if policy.require_manual_approval:
        reasons.append("manual approval is required")
    if not policy.paper_trading_enabled:
        reasons.append("paper trading is disabled by policy")
    if fill_result.live_fill_allowed:
        reasons.append("source fill indicates live fill allowance")
    if performance_result.live_review_allowed:
        reasons.append("performance result indicates live review allowance")
    if preview.live_order_allowed:
        reasons.append("preview indicates live order allowance")
    if request.requested_mode == ADAPTER_MODE_LIVE_DISABLED:
        reasons.append("requested mode is live-disabled")
    if request.requested_mode not in {ADAPTER_MODE_LIVE_DISABLED, ADAPTER_MODE_PAPER_ONLY, ADAPTER_MODE_DRY_RUN}:
        reasons.append(f"requested mode '{request.requested_mode}' is unsupported")
    if policy.adapter_mode == ADAPTER_MODE_LIVE_DISABLED:
        reasons.append("adapter mode is live-disabled")
    if policy.max_notional_usd > 0 and request.notional_usd > policy.max_notional_usd:
        reasons.append(
            f"requested notional {request.notional_usd:.4f} exceeds max {policy.max_notional_usd:.4f}"
        )
    if policy.allowlisted_symbols and request.symbol not in policy.allowlisted_symbols:
        reasons.append(f"symbol '{request.symbol}' is not allowlisted")
    if policy.allowlisted_venues and request.venue not in policy.allowlisted_venues:
        reasons.append(f"venue '{request.venue}' is not allowlisted")
    if request.order_type.lower() == "market" and not policy.allow_market_orders:
        reasons.append("market orders are disabled by policy")
    if policy.allow_leverage:
        reasons.append("leverage must remain disabled in this phase")

    return list(dict.fromkeys(reason for reason in reasons if reason))


def _select_verdict(
    *,
    blocked_reasons: list[str],
    policy: ExecutionAdapterPolicy,
) -> str:
    if policy.kill_switch_enabled:
        return EXECUTION_VERDICT_KILL_SWITCH_BLOCKED
    if policy.require_manual_approval:
        return EXECUTION_VERDICT_MANUAL_APPROVAL_REQUIRED
    if not policy.live_trading_enabled:
        return EXECUTION_VERDICT_LIVE_DISABLED
    if blocked_reasons:
        return EXECUTION_VERDICT_BLOCKED
    return EXECUTION_VERDICT_PAPER_DRY_RUN_ONLY


def _required_next_gates(*, blocked_reasons: list[str]) -> list[str]:
    gates = [
        "Keep golden evaluations passing.",
        "Maintain live-disabled mode until explicit future live gate approval.",
        "Require explicit manual approval + risk signoff before any paper/live execution enablement.",
    ]
    for reason in blocked_reasons:
        gates.append(f"Resolve blocker: {reason}")
    return list(dict.fromkeys(gates))
