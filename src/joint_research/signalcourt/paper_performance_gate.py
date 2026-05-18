"""Deterministic non-executing paper performance review gate."""

from __future__ import annotations

from dataclasses import dataclass

from joint_research.signalcourt.paper_fill_simulator import (
    FILL_STATUS_SIMULATED,
    PaperFillSimulationResult,
)

PERFORMANCE_VERDICT_BLOCKED = "PERFORMANCE_BLOCKED"
PERFORMANCE_VERDICT_REVIEW_ONLY = "PAPER_REVIEW_ONLY"
PERFORMANCE_VERDICT_CANDIDATE = "PAPER_CANDIDATE"
PERFORMANCE_VERDICT_LIVE_REVIEW_BLOCKED = "LIVE_REVIEW_BLOCKED"


@dataclass(frozen=True)
class PaperPerformancePolicy:
    min_fills: int = 1
    min_win_rate: float = 0.50
    max_drawdown_usd: float = 5.0
    max_loss_usd: float = 5.0
    min_net_pnl_usd: float = 0.0
    require_all_non_live: bool = True
    require_no_execution_flags: bool = True
    require_golden_evaluations: bool = True


@dataclass(frozen=True)
class PaperPerformanceReviewResult:
    run_id: str
    lane: str
    fill_count: int
    simulated_win_count: int
    simulated_loss_count: int
    simulated_win_rate: float
    simulated_gross_pnl_usd: float
    simulated_fees_usd: float
    simulated_net_pnl_usd: float
    simulated_max_drawdown_usd: float
    performance_verdict: str
    paper_review_allowed: bool
    live_review_allowed: bool
    blocked_reasons: list[str]
    required_next_gates: list[str]
    non_authorization_notice: str
    review_safety_metadata: dict[str, bool]


def review_paper_performance(
    fills: list[PaperFillSimulationResult],
    *,
    policy: PaperPerformancePolicy | None = None,
    run_id: str | None = None,
    lane: str | None = None,
) -> PaperPerformanceReviewResult:
    effective_policy = policy or PaperPerformancePolicy()
    fill_count = len(fills)

    effective_run_id = run_id or (fills[0].run_id if fills else "paper_performance_review:empty")
    effective_lane = lane or (fills[0].lane if fills else "unknown")

    if not fills:
        blocked_reasons = ["no paper fill simulation results provided"]
        return _build_result(
            run_id=effective_run_id,
            lane=effective_lane,
            fill_count=0,
            win_count=0,
            loss_count=0,
            gross_pnl=0.0,
            fees=0.0,
            net_pnl=0.0,
            drawdown=0.0,
            performance_verdict=PERFORMANCE_VERDICT_BLOCKED,
            blocked_reasons=blocked_reasons,
            required_next_gates=_required_next_gates(
                blocked_reasons=blocked_reasons,
                policy=effective_policy,
            ),
            notice="Paper performance review is non-executing and does not authorize paper/live trading or execution.",
        )

    gross_pnl, fees, win_count, loss_count, drawdown = _aggregate_simulated_pnl(fills)
    net_pnl = round(gross_pnl - fees, 8)
    win_rate = round(win_count / fill_count, 8) if fill_count else 0.0

    blocked_reasons: list[str] = []
    if fill_count < effective_policy.min_fills:
        blocked_reasons.append(
            f"fill count {fill_count} is below minimum required {effective_policy.min_fills}"
        )
    if win_rate < effective_policy.min_win_rate:
        blocked_reasons.append(
            f"simulated win rate {win_rate:.4f} is below minimum {effective_policy.min_win_rate:.4f}"
        )
    if drawdown > effective_policy.max_drawdown_usd:
        blocked_reasons.append(
            f"simulated max drawdown {drawdown:.4f} exceeds max {effective_policy.max_drawdown_usd:.4f}"
        )
    if net_pnl < (-1.0 * effective_policy.max_loss_usd):
        blocked_reasons.append(
            f"simulated net pnl {net_pnl:.4f} exceeds max loss {-1.0 * effective_policy.max_loss_usd:.4f}"
        )
    if net_pnl < effective_policy.min_net_pnl_usd:
        blocked_reasons.append(
            f"simulated net pnl {net_pnl:.4f} is below minimum {effective_policy.min_net_pnl_usd:.4f}"
        )
    if any(not fill.paper_fill_allowed for fill in fills):
        blocked_reasons.append("one or more source fills are not paper-fill-allowed")
    if effective_policy.require_all_non_live and any(fill.live_fill_allowed for fill in fills):
        blocked_reasons.append("one or more source fills are live-fill-allowed")
    if effective_policy.require_no_execution_flags and _has_execution_like_safety_flags(fills):
        blocked_reasons.append("execution-like safety metadata detected in source fills")

    verdict = _select_verdict(blocked_reasons=blocked_reasons)
    required_next_gates = _required_next_gates(
        blocked_reasons=blocked_reasons,
        policy=effective_policy,
    )
    notice = _combine_notices(fills)

    return _build_result(
        run_id=effective_run_id,
        lane=effective_lane,
        fill_count=fill_count,
        win_count=win_count,
        loss_count=loss_count,
        gross_pnl=gross_pnl,
        fees=fees,
        net_pnl=net_pnl,
        drawdown=drawdown,
        performance_verdict=verdict,
        blocked_reasons=blocked_reasons,
        required_next_gates=required_next_gates,
        notice=notice,
    )


def _build_result(
    *,
    run_id: str,
    lane: str,
    fill_count: int,
    win_count: int,
    loss_count: int,
    gross_pnl: float,
    fees: float,
    net_pnl: float,
    drawdown: float,
    performance_verdict: str,
    blocked_reasons: list[str],
    required_next_gates: list[str],
    notice: str,
) -> PaperPerformanceReviewResult:
    deduped_reasons = list(dict.fromkeys(reason for reason in blocked_reasons if reason))
    deduped_gates = list(dict.fromkeys(gate for gate in required_next_gates if gate))
    win_rate = round(win_count / fill_count, 8) if fill_count else 0.0

    # Hard-off for this phase: performance review remains non-executing.
    paper_review_allowed = False
    live_review_allowed = False

    return PaperPerformanceReviewResult(
        run_id=run_id,
        lane=lane,
        fill_count=fill_count,
        simulated_win_count=win_count,
        simulated_loss_count=loss_count,
        simulated_win_rate=win_rate,
        simulated_gross_pnl_usd=round(gross_pnl, 8),
        simulated_fees_usd=round(fees, 8),
        simulated_net_pnl_usd=round(net_pnl, 8),
        simulated_max_drawdown_usd=round(drawdown, 8),
        performance_verdict=performance_verdict,
        paper_review_allowed=paper_review_allowed,
        live_review_allowed=live_review_allowed,
        blocked_reasons=deduped_reasons,
        required_next_gates=deduped_gates,
        non_authorization_notice=notice,
        review_safety_metadata={
            "execution_performed": False,
            "broker_call_performed": False,
            "exchange_call_performed": False,
            "live_order_submitted": False,
            "paper_order_submitted": False,
            "artifact_written": False,
            "ingestion_run": False,
            "review_only": True,
        },
    )


def _aggregate_simulated_pnl(
    fills: list[PaperFillSimulationResult],
) -> tuple[float, float, int, int, float]:
    gross_pnl = 0.0
    fees = 0.0
    win_count = 0
    loss_count = 0
    cumulative = 0.0
    peak = 0.0
    max_drawdown = 0.0

    for fill in fills:
        pnl = _estimate_fill_pnl(fill)
        gross_pnl += pnl
        fees += max(float(fill.simulated_fee_usd), 0.0)
        if pnl > 0:
            win_count += 1
        elif pnl < 0:
            loss_count += 1

        cumulative += pnl - max(float(fill.simulated_fee_usd), 0.0)
        peak = max(peak, cumulative)
        max_drawdown = max(max_drawdown, peak - cumulative)

    return gross_pnl, fees, win_count, loss_count, max_drawdown


def _estimate_fill_pnl(fill: PaperFillSimulationResult) -> float:
    if fill.simulated_fill_status != FILL_STATUS_SIMULATED:
        return 0.0

    quantity = max(float(fill.simulated_fill_quantity), 0.0)
    requested_limit = float(fill.requested_limit_price)
    simulated_price = float(fill.simulated_fill_price)
    side = fill.side.upper()
    if side == "BUY":
        return round((requested_limit - simulated_price) * quantity, 8)
    if side == "SELL":
        return round((simulated_price - requested_limit) * quantity, 8)
    return 0.0


def _has_execution_like_safety_flags(fills: list[PaperFillSimulationResult]) -> bool:
    keys = (
        "execution_performed",
        "broker_call_performed",
        "exchange_call_performed",
        "live_order_submitted",
        "paper_order_submitted",
    )
    for fill in fills:
        metadata = fill.simulator_safety_metadata
        for key in keys:
            if bool(metadata.get(key, False)):
                return True
    return False


def _select_verdict(*, blocked_reasons: list[str]) -> str:
    if any("live-fill-allowed" in reason for reason in blocked_reasons):
        return PERFORMANCE_VERDICT_LIVE_REVIEW_BLOCKED
    if blocked_reasons:
        return PERFORMANCE_VERDICT_BLOCKED
    # Future-ready verdicts, still non-executing in this phase.
    return PERFORMANCE_VERDICT_REVIEW_ONLY


def _required_next_gates(
    *,
    blocked_reasons: list[str],
    policy: PaperPerformancePolicy,
) -> list[str]:
    gates: list[str] = []
    if policy.require_golden_evaluations:
        gates.append("Keep golden evaluations passing.")
    gates.append("Performance review remains non-executing until explicit future paper/live gates.")
    for reason in blocked_reasons:
        gates.append(f"Resolve blocker: {reason}")
    return list(dict.fromkeys(gates))


def _combine_notices(fills: list[PaperFillSimulationResult]) -> str:
    upstream = " ".join(
        fill.non_authorization_notice.strip()
        for fill in fills
        if fill.non_authorization_notice
    ).strip()
    return (
        f"{upstream} Paper performance review is non-executing and does not authorize broker/exchange "
        "calls, order placement, paper/live trading, or execution."
    ).strip()
