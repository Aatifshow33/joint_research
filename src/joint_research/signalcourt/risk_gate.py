"""Deterministic SignalCourt risk gate over paper decision results."""

from __future__ import annotations

from dataclasses import dataclass

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
