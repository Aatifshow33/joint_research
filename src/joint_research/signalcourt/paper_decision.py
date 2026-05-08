"""Deterministic paper decision engine derived from bot-facing trade decisions."""

from __future__ import annotations

from dataclasses import dataclass

from joint_research.signalcourt.decision import (
    ACTION_NO_TRADE,
    ACTION_PAPER_ENTER,
    ACTION_PAPER_EXIT,
    ACTION_WATCH_ONLY,
    EXECUTION_MODE_PAPER,
    TradeDecision,
)

PAPER_ACTION_NO_TRADE = "PAPER_NO_TRADE"
PAPER_ACTION_WATCH_ONLY = "PAPER_WATCH_ONLY"
PAPER_ACTION_ENTER = "PAPER_ENTER"
PAPER_ACTION_EXIT = "PAPER_EXIT"


@dataclass(frozen=True)
class PaperDecisionResult:
    decision_id: str
    signal_id: str
    lane: str
    requested_action: str
    paper_action: str
    paper_allowed: bool
    execution_mode: str
    blocked: bool
    block_reasons: list[str]
    simulated_order_required: bool
    journal_required: bool
    source_decision_action: str
    source_decision_allowed: bool
    non_authorization_notice: str


def build_paper_decision_result(decision: TradeDecision) -> PaperDecisionResult:
    paper_action = _map_paper_action(decision.action)
    simulated_order_required = paper_action in {PAPER_ACTION_ENTER, PAPER_ACTION_EXIT}
    requested_action = decision.action

    block_reasons: list[str] = []
    if not decision.allowed:
        block_reasons.append("source decision is not allowed")
    if decision.execution_mode != EXECUTION_MODE_PAPER:
        block_reasons.append("execution mode is not PAPER")
    if paper_action not in {PAPER_ACTION_ENTER, PAPER_ACTION_EXIT}:
        block_reasons.append("paper action is non-executable")
    if not decision.trade_decision_allowed:
        block_reasons.append("source verdict does not allow trade decision")
    if decision.blockers:
        block_reasons.extend(decision.blockers)

    # Deduplicate while preserving order.
    normalized_block_reasons = list(dict.fromkeys(block_reasons))
    paper_allowed = (
        decision.allowed
        and decision.execution_mode == EXECUTION_MODE_PAPER
        and paper_action in {PAPER_ACTION_ENTER, PAPER_ACTION_EXIT}
        and decision.trade_decision_allowed
    )
    blocked = not paper_allowed
    journal_required = paper_allowed and simulated_order_required

    return PaperDecisionResult(
        decision_id=decision.decision_id,
        signal_id=decision.signal_id,
        lane=decision.lane,
        requested_action=requested_action,
        paper_action=paper_action,
        paper_allowed=paper_allowed,
        execution_mode=decision.execution_mode,
        blocked=blocked,
        block_reasons=normalized_block_reasons,
        simulated_order_required=simulated_order_required,
        journal_required=journal_required,
        source_decision_action=decision.action,
        source_decision_allowed=decision.allowed,
        non_authorization_notice=decision.non_authorization_notice,
    )


def paper_decision_allows_order(
    result: PaperDecisionResult,
    *,
    risk_gate_passed: bool = False,
) -> bool:
    if not result.paper_allowed:
        return False
    if result.paper_action not in {PAPER_ACTION_ENTER, PAPER_ACTION_EXIT}:
        return False
    if result.blocked:
        return False
    if result.execution_mode != EXECUTION_MODE_PAPER:
        return False
    if not risk_gate_passed:
        return False
    return True


def _map_paper_action(action: str) -> str:
    if action == ACTION_NO_TRADE:
        return PAPER_ACTION_NO_TRADE
    if action == ACTION_WATCH_ONLY:
        return PAPER_ACTION_WATCH_ONLY
    if action == ACTION_PAPER_ENTER:
        return PAPER_ACTION_ENTER
    if action == ACTION_PAPER_EXIT:
        return PAPER_ACTION_EXIT
    return PAPER_ACTION_NO_TRADE
