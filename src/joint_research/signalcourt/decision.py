"""Bot-facing deterministic trade decision schema derived from court verdicts."""

from __future__ import annotations

from dataclasses import dataclass

from joint_research.signalcourt.verdict import (
    ResearchCourtVerdict,
    VERDICT_ACTIVE_RESEARCH_WEAK,
    VERDICT_BLOCKED_PENDING_DIAGNOSTICS,
    VERDICT_CLOSED_EXPLORATORY_ONLY,
    VERDICT_READY_FOR_REVIEW,
)

ACTION_NO_TRADE = "NO_TRADE"
ACTION_WATCH_ONLY = "WATCH_ONLY"
ACTION_PAPER_ENTER = "PAPER_ENTER"
ACTION_PAPER_EXIT = "PAPER_EXIT"
ACTION_LIVE_REVIEW_REQUIRED = "LIVE_REVIEW_REQUIRED"
ACTION_LIVE_ENTER = "LIVE_ENTER"

EXECUTION_MODE_NONE = "NONE"
EXECUTION_MODE_PAPER = "PAPER"
EXECUTION_MODE_LIVE_REVIEW = "LIVE_REVIEW"
EXECUTION_MODE_LIVE = "LIVE"

EXECUTION_ACTIONS = {
    ACTION_PAPER_ENTER,
    ACTION_PAPER_EXIT,
    ACTION_LIVE_REVIEW_REQUIRED,
    ACTION_LIVE_ENTER,
}


@dataclass(frozen=True)
class TradeDecision:
    decision_id: str
    signal_id: str
    lane: str
    action: str
    execution_mode: str
    allowed: bool
    reason: str
    confidence_label: str
    promotion_allowed: bool
    trade_decision_allowed: bool
    risk_required: bool
    source_verdict: str
    source_status: str
    blockers: list[str]
    next_required_evidence: list[str]
    non_authorization_notice: str


def build_trade_decision(verdict: ResearchCourtVerdict) -> TradeDecision:
    action = ACTION_NO_TRADE
    execution_mode = EXECUTION_MODE_NONE
    allowed = False
    confidence_label = "LOW"

    if verdict.verdict == VERDICT_ACTIVE_RESEARCH_WEAK:
        action = ACTION_WATCH_ONLY
        reason = "Active weak research signal; continue watch-only diagnostics with no execution."
    elif verdict.verdict == VERDICT_BLOCKED_PENDING_DIAGNOSTICS:
        reason = "Lane is blocked pending diagnostics; no trade action authorized."
    elif verdict.verdict == VERDICT_CLOSED_EXPLORATORY_ONLY:
        reason = "Lane is closed exploratory-only and not tradeable."
    elif verdict.verdict == VERDICT_READY_FOR_REVIEW:
        reason = (
            "Verdict indicates review readiness, but execution is disabled in this phase "
            "until explicit paper/live gates are introduced."
        )
    else:
        reason = "Unrecognized verdict posture; defaulting to no-trade safety state."

    blockers = list(verdict.governance_blocks)
    if not blockers:
        blockers = ["governance review required before any execution path"]

    decision_id = f"{verdict.signal_id}:{verdict.lane}:{verdict.verdict}:{action}"

    return TradeDecision(
        decision_id=decision_id,
        signal_id=verdict.signal_id,
        lane=verdict.lane,
        action=action,
        execution_mode=execution_mode,
        allowed=allowed,
        reason=reason,
        confidence_label=confidence_label,
        promotion_allowed=verdict.promotion_allowed,
        trade_decision_allowed=verdict.trade_decision_allowed,
        risk_required=True,
        source_verdict=verdict.verdict,
        source_status=verdict.source_passport_status,
        blockers=blockers,
        next_required_evidence=[verdict.next_recommended_experiment],
        non_authorization_notice=verdict.non_authorization_notice,
    )


def decision_allows_execution(
    decision: TradeDecision,
    *,
    risk_gate_passed: bool = False,
) -> bool:
    if not decision.allowed:
        return False
    if decision.action not in EXECUTION_ACTIONS:
        return False
    if decision.execution_mode == EXECUTION_MODE_NONE:
        return False
    if not decision.trade_decision_allowed:
        return False
    if decision.risk_required and not risk_gate_passed:
        return False
    return True
