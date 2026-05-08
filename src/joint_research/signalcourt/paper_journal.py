"""Deterministic paper journal model for SignalCourt audit/review."""

from __future__ import annotations

from dataclasses import dataclass

from joint_research.signalcourt.decision import TradeDecision
from joint_research.signalcourt.paper_decision import PaperDecisionResult
from joint_research.signalcourt.passport import SignalPassport
from joint_research.signalcourt.readiness import SignalReadiness
from joint_research.signalcourt.risk_gate import RiskGateResult
from joint_research.signalcourt.verdict import ResearchCourtVerdict


@dataclass(frozen=True)
class PaperJournalEntry:
    journal_id: str
    signal_id: str
    lane: str
    readiness_status: str
    passport_status: str
    verdict: str
    trade_action: str
    paper_action: str
    risk_allowed: bool
    paper_order_allowed: bool
    live_order_allowed: bool
    final_status: str
    blocked: bool
    block_reasons: list[str]
    account_equity_usd: float
    max_risk_usd: float
    max_position_notional_usd: float
    source_artifacts: list[str]
    decision_trace: list[str]
    non_authorization_notice: str


def build_paper_journal_entry(
    readiness: SignalReadiness,
    passport: SignalPassport,
    verdict: ResearchCourtVerdict,
    trade_decision: TradeDecision,
    paper_decision: PaperDecisionResult,
    risk_gate_result: RiskGateResult,
) -> PaperJournalEntry:
    block_reasons = list(dict.fromkeys(risk_gate_result.block_reasons or []))
    blocked = bool(risk_gate_result.blocked or not risk_gate_result.paper_order_allowed)
    final_status = _final_status(
        trade_action=trade_decision.action,
        paper_action=paper_decision.paper_action,
        blocked=blocked,
    )
    decision_trace = [
        f"readiness:{readiness.status}",
        f"passport:{passport.status}",
        f"verdict:{verdict.verdict}",
        f"trade_decision:{trade_decision.action}",
        f"paper_decision:{paper_decision.paper_action}",
        f"risk_gate:risk_allowed={risk_gate_result.risk_allowed}",
    ]
    journal_id = f"{risk_gate_result.decision_id}:{final_status}"

    return PaperJournalEntry(
        journal_id=journal_id,
        signal_id=readiness.signal_id,
        lane=readiness.lane,
        readiness_status=readiness.status,
        passport_status=passport.status,
        verdict=verdict.verdict,
        trade_action=trade_decision.action,
        paper_action=paper_decision.paper_action,
        risk_allowed=risk_gate_result.risk_allowed,
        paper_order_allowed=risk_gate_result.paper_order_allowed,
        live_order_allowed=risk_gate_result.live_order_allowed,
        final_status=final_status,
        blocked=blocked,
        block_reasons=block_reasons,
        account_equity_usd=risk_gate_result.account_equity_usd,
        max_risk_usd=risk_gate_result.max_risk_usd,
        max_position_notional_usd=risk_gate_result.max_position_notional_usd,
        source_artifacts=list(readiness.source_artifacts),
        decision_trace=decision_trace,
        non_authorization_notice=risk_gate_result.non_authorization_notice,
    )


def journal_entry_allows_order(entry: PaperJournalEntry) -> bool:
    if entry.blocked:
        return False
    if not entry.risk_allowed:
        return False
    if not entry.paper_order_allowed:
        return False
    if entry.live_order_allowed:
        return False
    if entry.paper_action not in {"PAPER_ENTER", "PAPER_EXIT"}:
        return False
    return True


def _final_status(*, trade_action: str, paper_action: str, blocked: bool) -> str:
    if blocked:
        if trade_action == "WATCH_ONLY" or paper_action == "PAPER_WATCH_ONLY":
            return "WATCH_ONLY_BLOCKED"
        return "NO_TRADE_BLOCKED"
    if paper_action == "PAPER_ENTER":
        return "PAPER_ENTER_READY"
    if paper_action == "PAPER_EXIT":
        return "PAPER_EXIT_READY"
    if paper_action == "PAPER_WATCH_ONLY":
        return "WATCH_ONLY"
    return "NO_TRADE"
