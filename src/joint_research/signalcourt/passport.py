"""Human-readable SignalCourt passports derived from readiness objects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from joint_research.signalcourt.readiness import (
    SignalReadiness,
    build_derivatives_regime_readiness,
    build_wallet_flow_readiness,
)

LANE_TITLES = {
    "derivatives_regime": "Derivatives-Regime",
    "wallet_flow_signal": "Wallet-Flow",
}


@dataclass(frozen=True)
class SignalPassport:
    signal_id: str
    lane: str
    title: str
    status: str
    tradeable: bool
    research_only: bool
    promotion_blocked: bool
    trade_decision_blocked: bool
    readiness_status: str
    simulation_ready_count: int
    watchlist_count: int
    weak_count: int
    rejected_count: int
    top_blockers: list[str]
    evidence_summary: str
    source_artifacts: list[str]
    next_required_evidence: list[str]
    operator_warning: str
    non_authorization_notice: str


def build_signal_passport(readiness: SignalReadiness) -> SignalPassport:
    title = LANE_TITLES.get(readiness.lane, _humanize_title(readiness.lane))
    readiness_status = _derive_readiness_status(readiness)
    operator_warning = _derive_operator_warning(readiness)
    evidence_summary = (
        f"{title} evidence: SIMULATION_READY={readiness.simulation_ready_count}, "
        f"WATCHLIST={readiness.watchlist_count}, WEAK={readiness.weak_count}, "
        f"REJECTED={readiness.rejected_count}. "
        f"Promotion blocked={readiness.promotion_blocked}, "
        f"trade decision blocked={readiness.trade_decision_blocked}."
    )

    return SignalPassport(
        signal_id=readiness.signal_id,
        lane=readiness.lane,
        title=title,
        status=readiness.status,
        tradeable=readiness.tradeable,
        research_only=readiness.research_only,
        promotion_blocked=readiness.promotion_blocked,
        trade_decision_blocked=readiness.trade_decision_blocked,
        readiness_status=readiness_status,
        simulation_ready_count=readiness.simulation_ready_count,
        watchlist_count=readiness.watchlist_count,
        weak_count=readiness.weak_count,
        rejected_count=readiness.rejected_count,
        top_blockers=list(readiness.top_blockers),
        evidence_summary=evidence_summary,
        source_artifacts=list(readiness.source_artifacts),
        next_required_evidence=list(readiness.next_required_evidence),
        operator_warning=operator_warning,
        non_authorization_notice=readiness.non_authorization_notice,
    )


def build_derivatives_regime_passport(
    *,
    results_csv_path: Path,
    candidates_json_path: Path,
    summary_md_path: Path,
    signal_id: str = "derivatives_regime",
) -> SignalPassport:
    readiness = build_derivatives_regime_readiness(
        results_csv_path=results_csv_path,
        candidates_json_path=candidates_json_path,
        summary_md_path=summary_md_path,
        signal_id=signal_id,
    )
    return build_signal_passport(readiness)


def build_wallet_flow_passport(
    *,
    signal_summary_md_path: Path,
    rejection_diagnostics_csv_path: Path,
    rejection_summary_md_path: Path,
    signal_id: str = "wallet_flow_signal",
) -> SignalPassport:
    readiness = build_wallet_flow_readiness(
        signal_summary_md_path=signal_summary_md_path,
        rejection_diagnostics_csv_path=rejection_diagnostics_csv_path,
        rejection_summary_md_path=rejection_summary_md_path,
        signal_id=signal_id,
    )
    return build_signal_passport(readiness)


def passport_allows_trade_decision(passport: SignalPassport) -> bool:
    if passport.tradeable is not True:
        return False
    if passport.research_only is not False:
        return False
    if passport.promotion_blocked is not False:
        return False
    if passport.trade_decision_blocked is not False:
        return False
    return passport.simulation_ready_count > 0


def _derive_readiness_status(readiness: SignalReadiness) -> str:
    if (
        readiness.tradeable
        and not readiness.research_only
        and not readiness.promotion_blocked
        and not readiness.trade_decision_blocked
        and readiness.simulation_ready_count > 0
    ):
        return "READY_FOR_DECISION_REVIEW"
    if readiness.research_only or readiness.trade_decision_blocked:
        return "RESEARCH_ONLY_BLOCKED"
    return "BLOCKED"


def _derive_operator_warning(readiness: SignalReadiness) -> str:
    if readiness.research_only and readiness.trade_decision_blocked:
        return (
            "Exploratory-only evidence. Not tradeable and trade decision is blocked "
            "until promotion and decision gates are explicitly cleared."
        )
    if readiness.trade_decision_blocked:
        return "Trade decision remains blocked pending additional evidence gates."
    return "No operator warning."


def _humanize_title(lane: str) -> str:
    normalized = lane.replace("-", "_").strip("_")
    parts = [piece for piece in normalized.split("_") if piece]
    if not parts:
        return "Signal"
    return "-".join(part.capitalize() for part in parts)
