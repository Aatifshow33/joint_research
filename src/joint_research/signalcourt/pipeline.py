"""Deterministic in-memory SignalCourt pipeline assembler."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from joint_research.signalcourt.decision import (
    TradeDecision,
    build_trade_decision,
    decision_allows_execution,
)
from joint_research.signalcourt.paper_decision import (
    PaperDecisionResult,
    build_paper_decision_result,
    paper_decision_allows_order,
)
from joint_research.signalcourt.paper_journal import (
    PaperJournalEntry,
    build_paper_journal_entry,
    journal_entry_allows_order,
)
from joint_research.signalcourt.passport import SignalPassport, build_signal_passport
from joint_research.signalcourt.readiness import (
    SignalReadiness,
    build_derivatives_regime_readiness,
    build_wallet_flow_readiness,
)
from joint_research.signalcourt.risk_gate import (
    RiskConfig,
    RiskGateResult,
    evaluate_risk_gate,
    risk_gate_allows_order,
)
from joint_research.signalcourt.verdict import ResearchCourtVerdict, build_research_court_verdict


@dataclass(frozen=True)
class SignalCourtPipelineResult:
    lane: str
    signal_id: str
    readiness: SignalReadiness
    passport: SignalPassport
    verdict: ResearchCourtVerdict
    trade_decision: TradeDecision
    paper_decision: PaperDecisionResult
    risk_gate: RiskGateResult
    journal_entry: PaperJournalEntry
    final_status: str
    blocked: bool
    paper_order_allowed: bool
    live_order_allowed: bool
    non_authorization_notice: str


def build_wallet_flow_pipeline(
    *,
    signal_summary_md_path: Path,
    rejection_diagnostics_csv_path: Path,
    rejection_summary_md_path: Path,
    risk_config: RiskConfig,
    signal_id: str = "wallet_flow_signal",
) -> SignalCourtPipelineResult:
    readiness = build_wallet_flow_readiness(
        signal_summary_md_path=signal_summary_md_path,
        rejection_diagnostics_csv_path=rejection_diagnostics_csv_path,
        rejection_summary_md_path=rejection_summary_md_path,
        signal_id=signal_id,
    )
    return _assemble_pipeline(readiness=readiness, risk_config=risk_config)


def build_derivatives_regime_pipeline(
    *,
    results_csv_path: Path,
    candidates_json_path: Path,
    summary_md_path: Path,
    risk_config: RiskConfig,
    signal_id: str = "derivatives_regime",
) -> SignalCourtPipelineResult:
    readiness = build_derivatives_regime_readiness(
        results_csv_path=results_csv_path,
        candidates_json_path=candidates_json_path,
        summary_md_path=summary_md_path,
        signal_id=signal_id,
    )
    return _assemble_pipeline(readiness=readiness, risk_config=risk_config)


def pipeline_allows_order(result: SignalCourtPipelineResult) -> bool:
    if not decision_allows_execution(result.trade_decision):
        return False
    if not paper_decision_allows_order(result.paper_decision):
        return False
    if not risk_gate_allows_order(result.risk_gate):
        return False
    if not journal_entry_allows_order(result.journal_entry):
        return False
    if result.blocked:
        return False
    if not result.paper_order_allowed:
        return False
    if result.live_order_allowed:
        return False
    return True


def _assemble_pipeline(
    *,
    readiness: SignalReadiness,
    risk_config: RiskConfig,
) -> SignalCourtPipelineResult:
    passport = build_signal_passport(readiness)
    verdict = build_research_court_verdict(passport)
    trade_decision = build_trade_decision(verdict)
    paper_decision = build_paper_decision_result(trade_decision)
    risk_gate = evaluate_risk_gate(paper_decision, risk_config)
    journal_entry = build_paper_journal_entry(
        readiness,
        passport,
        verdict,
        trade_decision,
        paper_decision,
        risk_gate,
    )
    return SignalCourtPipelineResult(
        lane=readiness.lane,
        signal_id=readiness.signal_id,
        readiness=readiness,
        passport=passport,
        verdict=verdict,
        trade_decision=trade_decision,
        paper_decision=paper_decision,
        risk_gate=risk_gate,
        journal_entry=journal_entry,
        final_status=journal_entry.final_status,
        blocked=journal_entry.blocked,
        paper_order_allowed=journal_entry.paper_order_allowed,
        live_order_allowed=journal_entry.live_order_allowed,
        non_authorization_notice=journal_entry.non_authorization_notice,
    )
