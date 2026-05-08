"""Deterministic Research Court verdict engine for SignalCourt passports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from joint_research.signalcourt.passport import (
    SignalPassport,
    build_derivatives_regime_passport,
    build_wallet_flow_passport,
    passport_allows_trade_decision,
)

VERDICT_CLOSED_EXPLORATORY_ONLY = "CLOSED_EXPLORATORY_ONLY"
VERDICT_ACTIVE_RESEARCH_WEAK = "ACTIVE_RESEARCH_WEAK"
VERDICT_BLOCKED_PENDING_DIAGNOSTICS = "BLOCKED_PENDING_DIAGNOSTICS"
VERDICT_READY_FOR_REVIEW = "READY_FOR_REVIEW"


@dataclass(frozen=True)
class ResearchCourtVerdict:
    signal_id: str
    lane: str
    verdict: str
    research_only: bool
    promotion_allowed: bool
    trade_decision_allowed: bool
    prosecutor_findings: list[str]
    defender_findings: list[str]
    governance_blocks: list[str]
    next_recommended_experiment: str
    source_passport_status: str
    non_authorization_notice: str


def prosecutor_review(passport: SignalPassport) -> list[str]:
    findings: list[str] = []
    if passport.research_only:
        findings.append("research_only flag is true")
    if not passport.tradeable:
        findings.append("tradeable flag is false")
    if passport.promotion_blocked:
        findings.append("promotion gate is blocked")
    if passport.trade_decision_blocked:
        findings.append("trade decision gate is blocked")
    if passport.simulation_ready_count == 0:
        findings.append("SIMULATION_READY count is zero")
    if passport.watchlist_count == 0:
        findings.append("WATCHLIST count is zero")
    if passport.top_blockers:
        findings.append("top blockers: " + ", ".join(passport.top_blockers))
    return findings


def defender_review(passport: SignalPassport) -> list[str]:
    findings: list[str] = []
    if passport.lane == "wallet_flow_signal":
        findings.append("lane remains closed exploratory-only; no optimistic defender claim is warranted")
        if passport.top_blockers:
            findings.append("next evidence should directly target blockers: " + ", ".join(passport.top_blockers))
        return findings

    if passport.weak_count > 0:
        findings.append("weak_count is non-zero, indicating weak but inspectable structure")
    if passport.top_blockers:
        findings.append("next evidence can be designed to reduce blockers: " + ", ".join(passport.top_blockers))
    if passport.lane == "derivatives_regime":
        findings.append("derivatives-regime remains active research with weak structure; keep interpretation restrained")
    return findings


def governance_review(passport: SignalPassport) -> list[str]:
    blocks: list[str] = []
    current_lane = passport.lane in {"wallet_flow_signal", "derivatives_regime"}
    if current_lane:
        blocks.append("current lane is restricted to research-only governance posture")
    if passport.promotion_blocked:
        blocks.append("promotion is blocked by readiness gates")
    if passport.trade_decision_blocked:
        blocks.append("trade decision is blocked by readiness gates")
    if passport.simulation_ready_count == 0:
        blocks.append("no SIMULATION_READY evidence exists")
    if passport.watchlist_count == 0:
        blocks.append("no WATCHLIST evidence exists")
    return blocks


def build_research_court_verdict(passport: SignalPassport) -> ResearchCourtVerdict:
    prosecutor_findings = prosecutor_review(passport)
    defender_findings = defender_review(passport)
    governance_blocks = governance_review(passport)

    promotion_allowed = False
    trade_decision_allowed = False

    verdict = _select_verdict(passport)
    next_recommended_experiment = _next_recommended_experiment(passport)

    return ResearchCourtVerdict(
        signal_id=passport.signal_id,
        lane=passport.lane,
        verdict=verdict,
        research_only=passport.research_only,
        promotion_allowed=promotion_allowed,
        trade_decision_allowed=trade_decision_allowed,
        prosecutor_findings=prosecutor_findings,
        defender_findings=defender_findings,
        governance_blocks=governance_blocks,
        next_recommended_experiment=next_recommended_experiment,
        source_passport_status=passport.status,
        non_authorization_notice=passport.non_authorization_notice,
    )


def build_derivatives_regime_verdict(
    *,
    results_csv_path: Path,
    candidates_json_path: Path,
    summary_md_path: Path,
    signal_id: str = "derivatives_regime",
) -> ResearchCourtVerdict:
    passport = build_derivatives_regime_passport(
        results_csv_path=results_csv_path,
        candidates_json_path=candidates_json_path,
        summary_md_path=summary_md_path,
        signal_id=signal_id,
    )
    return build_research_court_verdict(passport)


def build_wallet_flow_verdict(
    *,
    signal_summary_md_path: Path,
    rejection_diagnostics_csv_path: Path,
    rejection_summary_md_path: Path,
    signal_id: str = "wallet_flow_signal",
) -> ResearchCourtVerdict:
    passport = build_wallet_flow_passport(
        signal_summary_md_path=signal_summary_md_path,
        rejection_diagnostics_csv_path=rejection_diagnostics_csv_path,
        rejection_summary_md_path=rejection_summary_md_path,
        signal_id=signal_id,
    )
    return build_research_court_verdict(passport)


def _select_verdict(passport: SignalPassport) -> str:
    if passport.lane == "wallet_flow_signal":
        return VERDICT_CLOSED_EXPLORATORY_ONLY
    if passport_allows_trade_decision(passport):
        return VERDICT_READY_FOR_REVIEW
    if passport.lane == "derivatives_regime" and passport.weak_count > 0:
        return VERDICT_ACTIVE_RESEARCH_WEAK
    if passport.promotion_blocked or passport.trade_decision_blocked:
        return VERDICT_BLOCKED_PENDING_DIAGNOSTICS
    return VERDICT_BLOCKED_PENDING_DIAGNOSTICS


def _next_recommended_experiment(passport: SignalPassport) -> str:
    if passport.top_blockers:
        return "Target blockers in next study: " + ", ".join(passport.top_blockers)
    if passport.next_required_evidence:
        return passport.next_required_evidence[0]
    return "Collect additional diagnostics evidence before any promotion review."
