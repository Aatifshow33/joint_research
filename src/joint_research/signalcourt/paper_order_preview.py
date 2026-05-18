"""Non-executing SignalCourt paper order preview object."""

from __future__ import annotations

from dataclasses import dataclass

from joint_research.signalcourt.decision_preview import (
    ACTION_NO_TRADE,
    ACTION_WATCH_ONLY,
    SignalCourtDecisionPreview,
)
from joint_research.signalcourt.risk_gate import DecisionPreviewRiskResult

PAPER_ORDER_ACTION_NO_TRADE = "PAPER_NO_TRADE"
PAPER_ORDER_ACTION_WATCH_ONLY = "PAPER_WATCH_ONLY"
PAPER_ORDER_ACTION_BLOCKED = "PAPER_BLOCKED"
PAPER_ORDER_ACTION_PREVIEW_ONLY = "PAPER_PREVIEW_ONLY"

_NON_AUTH_NOTICE = (
    "Paper order preview is non-executing and does not authorize broker/exchange calls, "
    "order placement, paper/live trading, or execution."
)


@dataclass(frozen=True)
class PaperOrderRequest:
    symbol: str = ""
    side: str = ""
    quantity: float = 0.0
    limit_price: float = 0.0
    notional_usd: float = 0.0
    venue: str = ""
    order_type: str = ""


@dataclass(frozen=True)
class SignalCourtPaperOrderPreview:
    run_id: str
    lane: str
    symbol: str
    side: str
    quantity: float
    limit_price: float
    notional_usd: float
    venue: str
    order_type: str
    paper_order_action: str
    paper_order_allowed: bool
    live_order_allowed: bool
    blocked_reasons: list[str]
    required_next_gates: list[str]
    non_authorization_notice: str


def build_paper_order_preview(
    decision_preview: SignalCourtDecisionPreview,
    risk_result: DecisionPreviewRiskResult,
    *,
    order_request: PaperOrderRequest | None = None,
) -> SignalCourtPaperOrderPreview:
    request = order_request or PaperOrderRequest()

    blocked_reasons = list(dict.fromkeys([
        *(decision_preview.blocked_reasons or []),
        *(risk_result.blocked_reasons or []),
    ]))
    required_next_gates = list(dict.fromkeys([
        *(decision_preview.required_next_gates or []),
        *(risk_result.required_next_gates or []),
        "Keep golden evaluations passing.",
    ]))

    paper_eligible_by_inputs = bool(
        risk_result.paper_allowed
        and decision_preview.paper_eligible
        and risk_result.risk_verdict not in {"RISK_BLOCKED", "LIVE_BLOCKED"}
    )
    # Hard-off in this phase by design: preview only, never executable.
    paper_allowed = False
    live_allowed = False

    action = _map_paper_order_action(
        decision_action=decision_preview.decision_action,
        paper_allowed=paper_eligible_by_inputs,
        blocked_reasons=blocked_reasons,
    )

    non_auth_notice = (
        f"{decision_preview.non_authorization_notice} {risk_result.non_authorization_notice} "
        f"{_NON_AUTH_NOTICE}"
    ).strip()

    return SignalCourtPaperOrderPreview(
        run_id=decision_preview.run_id,
        lane=decision_preview.lane,
        symbol=request.symbol,
        side=request.side,
        quantity=float(request.quantity),
        limit_price=float(request.limit_price),
        notional_usd=float(request.notional_usd),
        venue=request.venue,
        order_type=request.order_type,
        paper_order_action=action,
        paper_order_allowed=paper_allowed,
        live_order_allowed=live_allowed,
        blocked_reasons=blocked_reasons,
        required_next_gates=required_next_gates,
        non_authorization_notice=non_auth_notice,
    )


def _map_paper_order_action(
    *,
    decision_action: str,
    paper_allowed: bool,
    blocked_reasons: list[str],
) -> str:
    if decision_action == ACTION_NO_TRADE:
        return PAPER_ORDER_ACTION_NO_TRADE
    if decision_action == ACTION_WATCH_ONLY:
        return PAPER_ORDER_ACTION_WATCH_ONLY
    if paper_allowed and not blocked_reasons:
        return PAPER_ORDER_ACTION_PREVIEW_ONLY
    return PAPER_ORDER_ACTION_BLOCKED
