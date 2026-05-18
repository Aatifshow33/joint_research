"""Deterministic SignalCourt risk gate over paper decision results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from joint_research.signalcourt.paper_decision import (
    PAPER_ACTION_ENTER,
    PAPER_ACTION_EXIT,
    PaperDecisionResult,
)


@dataclass(frozen=True)
class RiskConfig:
    account_equity_usd: float
    max_risk_per_trade_pct: float
    max_daily_loss_pct: float
    max_weekly_loss_pct: float
    max_position_notional_usd: float
    max_open_positions: int
    allow_leverage: bool
    allow_shorting: bool
    allow_live_trading: bool


@dataclass(frozen=True)
class RiskGateResult:
    decision_id: str
    signal_id: str
    lane: str
    risk_allowed: bool
    blocked: bool
    block_reasons: list[str]
    account_equity_usd: float
    max_risk_usd: float
    max_daily_loss_usd: float
    max_weekly_loss_usd: float
    max_position_notional_usd: float
    paper_order_allowed: bool
    live_order_allowed: bool
    non_authorization_notice: str


def default_tiny_account_risk_config(account_equity_usd: float) -> RiskConfig:
    equity = max(float(account_equity_usd), 0.0)
    conservative_position_cap = round(equity * 0.10, 2)
    return RiskConfig(
        account_equity_usd=equity,
        max_risk_per_trade_pct=1.0,
        max_daily_loss_pct=2.0,
        max_weekly_loss_pct=5.0,
        max_position_notional_usd=conservative_position_cap,
        max_open_positions=1,
        allow_leverage=False,
        allow_shorting=False,
        allow_live_trading=False,
    )


def evaluate_risk_gate(
    paper_decision_result: PaperDecisionResult,
    risk_config: RiskConfig,
) -> RiskGateResult:
    max_risk_usd = _pct_to_usd(
        equity=risk_config.account_equity_usd,
        pct=risk_config.max_risk_per_trade_pct,
    )
    max_daily_loss_usd = _pct_to_usd(
        equity=risk_config.account_equity_usd,
        pct=risk_config.max_daily_loss_pct,
    )
    max_weekly_loss_usd = _pct_to_usd(
        equity=risk_config.account_equity_usd,
        pct=risk_config.max_weekly_loss_pct,
    )

    block_reasons: list[str] = []
    if not paper_decision_result.paper_allowed:
        block_reasons.append("paper decision is not allowed")
    if paper_decision_result.blocked:
        block_reasons.append("paper decision is already blocked")
    if paper_decision_result.execution_mode != "PAPER":
        block_reasons.append("execution mode is not PAPER")
    if paper_decision_result.paper_action not in {PAPER_ACTION_ENTER, PAPER_ACTION_EXIT}:
        block_reasons.append("paper action is non-executable")
    if not risk_config.allow_live_trading:
        block_reasons.append("live trading is disabled by risk config")
    if risk_config.allow_leverage:
        block_reasons.append("leverage must remain disabled in this phase")
    if risk_config.allow_shorting:
        block_reasons.append("shorting must remain disabled in this phase")
    if risk_config.max_open_positions < 1:
        block_reasons.append("max_open_positions must be at least 1")

    if paper_decision_result.block_reasons:
        block_reasons.extend(paper_decision_result.block_reasons)

    normalized_block_reasons = list(dict.fromkeys(block_reasons))

    risk_allowed = not normalized_block_reasons and paper_decision_result.paper_allowed
    paper_order_allowed = risk_allowed
    live_order_allowed = False
    blocked = not risk_allowed

    return RiskGateResult(
        decision_id=paper_decision_result.decision_id,
        signal_id=paper_decision_result.signal_id,
        lane=paper_decision_result.lane,
        risk_allowed=risk_allowed,
        blocked=blocked,
        block_reasons=normalized_block_reasons,
        account_equity_usd=float(risk_config.account_equity_usd),
        max_risk_usd=max_risk_usd,
        max_daily_loss_usd=max_daily_loss_usd,
        max_weekly_loss_usd=max_weekly_loss_usd,
        max_position_notional_usd=float(risk_config.max_position_notional_usd),
        paper_order_allowed=paper_order_allowed,
        live_order_allowed=live_order_allowed,
        non_authorization_notice=paper_decision_result.non_authorization_notice,
    )


def risk_gate_allows_order(
    result: RiskGateResult,
    *,
    risk_gate_passed: bool = False,
) -> bool:
    if not result.risk_allowed:
        return False
    if not result.paper_order_allowed:
        return False
    if result.blocked:
        return False
    if not risk_gate_passed:
        return False
    return True


def _pct_to_usd(*, equity: float, pct: float) -> float:
    return round(max(equity, 0.0) * max(pct, 0.0) / 100.0, 2)


RISK_VERDICT_BLOCKED = "RISK_BLOCKED"
RISK_VERDICT_PAPER_REVIEW_ONLY = "PAPER_RISK_REVIEW_ONLY"
RISK_VERDICT_PAPER_ALLOWED = "PAPER_ALLOWED"
RISK_VERDICT_LIVE_BLOCKED = "LIVE_BLOCKED"
RISK_VERDICT_MICRO_LIVE_REVIEW_REQUIRED = "MICRO_LIVE_REVIEW_REQUIRED"


@dataclass(frozen=True)
class DecisionPreviewRiskPolicy:
    max_notional_usd: float
    max_position_notional_usd: float
    max_daily_loss_usd: float
    max_session_loss_usd: float
    allowlisted_lanes: tuple[str, ...]
    allowlisted_symbols: tuple[str, ...]
    allowlisted_venues: tuple[str, ...]
    paper_trading_enabled: bool
    live_trading_enabled: bool
    kill_switch_enabled: bool
    require_manual_approval: bool
    allow_market_orders: bool
    allow_leverage: bool


@dataclass(frozen=True)
class DecisionPreviewRiskResult:
    run_id: str
    lane: str
    decision_action: str
    risk_verdict: str
    paper_allowed: bool
    live_allowed: bool
    blocked_reasons: list[str]
    required_next_gates: list[str]
    max_notional_usd: float
    kill_switch_enabled: bool
    non_authorization_notice: str


def default_decision_preview_risk_policy() -> DecisionPreviewRiskPolicy:
    return DecisionPreviewRiskPolicy(
        max_notional_usd=25.0,
        max_position_notional_usd=10.0,
        max_daily_loss_usd=1.0,
        max_session_loss_usd=0.5,
        allowlisted_lanes=("wallet_flow_signal", "derivatives_regime"),
        allowlisted_symbols=(),
        allowlisted_venues=(),
        paper_trading_enabled=False,
        live_trading_enabled=False,
        kill_switch_enabled=True,
        require_manual_approval=True,
        allow_market_orders=False,
        allow_leverage=False,
    )


def evaluate_decision_preview_risk_gate(
    decision_preview: Any,
    *,
    risk_policy: DecisionPreviewRiskPolicy | None = None,
) -> DecisionPreviewRiskResult:
    policy = risk_policy or default_decision_preview_risk_policy()
    lane = str(getattr(decision_preview, "lane", "unknown"))
    run_id = str(getattr(decision_preview, "run_id", "unknown"))
    decision_action = str(getattr(decision_preview, "decision_action", "NO_TRADE"))
    blocked_reasons = list(getattr(decision_preview, "blocked_reasons", []) or [])

    if lane not in policy.allowlisted_lanes:
        blocked_reasons.append(f"lane '{lane}' is not allowlisted")
    if policy.kill_switch_enabled:
        blocked_reasons.append("kill switch is enabled")
    if not policy.paper_trading_enabled:
        blocked_reasons.append("paper trading is disabled by policy")
    if not policy.live_trading_enabled:
        blocked_reasons.append("live trading is disabled by policy")
    if getattr(decision_preview, "paper_eligible", False) is not True:
        blocked_reasons.append("decision preview is not paper eligible")
    if getattr(decision_preview, "live_eligible", False) is not True:
        blocked_reasons.append("decision preview is not live eligible")
    if policy.require_manual_approval:
        blocked_reasons.append("manual approval is required")
    if not policy.allow_market_orders:
        blocked_reasons.append("market orders are disabled")
    if policy.allow_leverage:
        blocked_reasons.append("leverage must remain disabled in this phase")

    deduped_reasons = list(dict.fromkeys(reason for reason in blocked_reasons if reason))

    # This phase remains non-executing: no lane may be paper/live allowed yet.
    paper_allowed = False
    live_allowed = False
    risk_verdict = _risk_verdict_for_preview(
        decision_action=decision_action,
        live_eligible=bool(getattr(decision_preview, "live_eligible", False)),
    )
    required_next_gates = _required_risk_next_gates(
        blocked_reasons=deduped_reasons,
        policy=policy,
    )

    upstream_notice = str(getattr(decision_preview, "non_authorization_notice", "")).strip()
    non_auth_notice = (
        f"{upstream_notice} Risk gate evaluation is non-executing; it does not authorize "
        "paper/live trading, order placement, broker calls, exchange calls, API/LLM calls, "
        "or execution."
    ).strip()

    return DecisionPreviewRiskResult(
        run_id=run_id,
        lane=lane,
        decision_action=decision_action,
        risk_verdict=risk_verdict,
        paper_allowed=paper_allowed,
        live_allowed=live_allowed,
        blocked_reasons=deduped_reasons,
        required_next_gates=required_next_gates,
        max_notional_usd=policy.max_notional_usd,
        kill_switch_enabled=policy.kill_switch_enabled,
        non_authorization_notice=non_auth_notice,
    )


def _risk_verdict_for_preview(*, decision_action: str, live_eligible: bool) -> str:
    if live_eligible:
        return RISK_VERDICT_LIVE_BLOCKED
    if decision_action == "WATCH_ONLY":
        return RISK_VERDICT_PAPER_REVIEW_ONLY
    return RISK_VERDICT_BLOCKED


def _required_risk_next_gates(
    *,
    blocked_reasons: list[str],
    policy: DecisionPreviewRiskPolicy,
) -> list[str]:
    gates: list[str] = []
    if policy.kill_switch_enabled:
        gates.append("Disable kill switch only under explicit future approval.")
    if not policy.paper_trading_enabled:
        gates.append("Enable paper trading only after explicit paper gate phases.")
    if not policy.live_trading_enabled:
        gates.append("Keep live trading disabled in current phase.")
    if policy.require_manual_approval:
        gates.append("Manual approval gate remains required.")
    for reason in blocked_reasons:
        gates.append(f"Resolve blocker: {reason}")
    gates.append("Keep golden evaluations passing.")
    return list(dict.fromkeys(gates))
