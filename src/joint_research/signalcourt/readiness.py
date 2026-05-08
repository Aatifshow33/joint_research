"""Normalized SignalCourt readiness objects from read-only research artifacts."""

from __future__ import annotations

import csv
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from joint_research.research.derivatives_regime_diagnostics import (
    run_derivatives_regime_diagnostics,
)

LANE_DERIVATIVES_REGIME = "derivatives_regime"
LANE_WALLET_FLOW = "wallet_flow_signal"

RESEARCH_ONLY_STATUS = "EXPLORATORY_ONLY_NOT_TRADEABLE"
NON_AUTHORIZATION_NOTICE = (
    "Research diagnostics only. No ingestion refresh, no candidate promotion, "
    "no paper/live trading authorization, and no execution path is implied."
)
DEFAULT_NEXT_REQUIRED_EVIDENCE = [
    "Increase sample depth across regimes before reconsidering thresholds.",
    "Improve train/test directional stability for candidate segments.",
    "Demonstrate consistent post-cost uplift before promotion gates can reopen.",
]
RESEARCH_GUARD_MARKERS = (
    "exploratory only - not tradeable",
    "not tradeable",
    "no live trading",
    "no execution",
)


@dataclass(frozen=True)
class SignalReadiness:
    signal_id: str
    lane: str
    status: str
    research_only: bool
    tradeable: bool
    promotion_blocked: bool
    trade_decision_blocked: bool
    simulation_ready_count: int
    watchlist_count: int
    weak_count: int
    rejected_count: int
    top_blockers: list[str]
    source_artifacts: list[str]
    readiness_summary: str
    next_required_evidence: list[str]
    non_authorization_notice: str


@dataclass(frozen=True)
class DerivativesRegimeReadinessPaths:
    results_csv_path: Path
    candidates_json_path: Path
    summary_md_path: Path


@dataclass(frozen=True)
class WalletFlowReadinessPaths:
    signal_summary_md_path: Path
    rejection_diagnostics_csv_path: Path
    rejection_summary_md_path: Path


def build_derivatives_regime_readiness(
    *,
    results_csv_path: Path,
    candidates_json_path: Path,
    summary_md_path: Path,
    signal_id: str = "derivatives_regime",
) -> SignalReadiness:
    _ensure_file_exists(results_csv_path)
    _ensure_file_exists(candidates_json_path)
    _ensure_file_exists(summary_md_path)

    diagnostics = run_derivatives_regime_diagnostics(
        results_csv_path=results_csv_path,
        candidates_json_path=candidates_json_path,
        summary_md_path=summary_md_path,
    )

    summary_text = summary_md_path.read_text(encoding="utf-8")
    research_only = _is_research_only(summary_text)
    tradeable = False

    weak_count = diagnostics.grade_counts.get("WEAK", 0)
    rejected_count = diagnostics.grade_counts.get("REJECTED", 0)
    blockers = [_humanize_blocker(reason) for reason in diagnostics.top_blocker_names]

    readiness_summary = (
        "Derivatives-regime remains exploratory-only with blocked promotion and "
        f"blocked trade decisions. Counts: SIMULATION_READY={diagnostics.simulation_ready_count}, "
        f"WATCHLIST={diagnostics.watchlist_count}, WEAK={weak_count}, REJECTED={rejected_count}."
    )

    return SignalReadiness(
        signal_id=signal_id,
        lane=LANE_DERIVATIVES_REGIME,
        status=RESEARCH_ONLY_STATUS if research_only else "RESEARCH_REVIEW_REQUIRED",
        research_only=research_only,
        tradeable=tradeable,
        promotion_blocked=diagnostics.promotion_blocked,
        trade_decision_blocked=diagnostics.trade_decision_blocked,
        simulation_ready_count=diagnostics.simulation_ready_count,
        watchlist_count=diagnostics.watchlist_count,
        weak_count=weak_count,
        rejected_count=rejected_count,
        top_blockers=blockers,
        source_artifacts=[
            str(results_csv_path),
            str(candidates_json_path),
            str(summary_md_path),
        ],
        readiness_summary=readiness_summary,
        next_required_evidence=list(DEFAULT_NEXT_REQUIRED_EVIDENCE),
        non_authorization_notice=NON_AUTHORIZATION_NOTICE,
    )


def build_wallet_flow_readiness(
    *,
    signal_summary_md_path: Path,
    rejection_diagnostics_csv_path: Path,
    rejection_summary_md_path: Path,
    signal_id: str = "wallet_flow_signal",
) -> SignalReadiness:
    _ensure_file_exists(signal_summary_md_path)
    _ensure_file_exists(rejection_diagnostics_csv_path)
    _ensure_file_exists(rejection_summary_md_path)

    signal_summary = signal_summary_md_path.read_text(encoding="utf-8")
    rejection_summary = rejection_summary_md_path.read_text(encoding="utf-8")
    retained_grade_counts = _wallet_flow_retained_grade_counts(rejection_diagnostics_csv_path)
    top_blockers = _wallet_flow_top_blockers(rejection_summary)

    simulation_ready_count = retained_grade_counts.get("SIMULATION_READY", 0)
    watchlist_count = retained_grade_counts.get("WATCHLIST", 0)
    weak_count = retained_grade_counts.get("WEAK", 0)
    rejected_count = retained_grade_counts.get("REJECTED", 0)

    research_only = _is_research_only(signal_summary) or _is_research_only(rejection_summary)
    tradeable = False
    promotion_blocked = simulation_ready_count == 0 and watchlist_count == 0
    trade_decision_blocked = True

    readiness_summary = (
        "Wallet-flow remains exploratory-only and non-tradeable with no promoted "
        f"segments. Counts: SIMULATION_READY={simulation_ready_count}, WATCHLIST={watchlist_count}, "
        f"WEAK={weak_count}, REJECTED={rejected_count}."
    )

    return SignalReadiness(
        signal_id=signal_id,
        lane=LANE_WALLET_FLOW,
        status=RESEARCH_ONLY_STATUS if research_only else "RESEARCH_REVIEW_REQUIRED",
        research_only=research_only,
        tradeable=tradeable,
        promotion_blocked=promotion_blocked,
        trade_decision_blocked=trade_decision_blocked,
        simulation_ready_count=simulation_ready_count,
        watchlist_count=watchlist_count,
        weak_count=weak_count,
        rejected_count=rejected_count,
        top_blockers=top_blockers,
        source_artifacts=[
            str(signal_summary_md_path),
            str(rejection_diagnostics_csv_path),
            str(rejection_summary_md_path),
        ],
        readiness_summary=readiness_summary,
        next_required_evidence=list(DEFAULT_NEXT_REQUIRED_EVIDENCE),
        non_authorization_notice=NON_AUTHORIZATION_NOTICE,
    )


def readiness_allows_trade_decision(readiness: SignalReadiness) -> bool:
    if readiness.tradeable is not True:
        return False
    if readiness.research_only is not False:
        return False
    if readiness.promotion_blocked is not False:
        return False
    if readiness.trade_decision_blocked is not False:
        return False
    return readiness.simulation_ready_count > 0


def _ensure_file_exists(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"required artifact not found: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"required artifact is not a file: {path}")


def _is_research_only(text: str) -> bool:
    normalized = text.lower().replace("_", " ")
    return any(marker in normalized for marker in RESEARCH_GUARD_MARKERS)


def _wallet_flow_retained_grade_counts(path: Path) -> Counter[str]:
    counts: Counter[str] = Counter()
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        required = {"retained_after_dedup", "final_grade"}
        missing = sorted(required - set(fieldnames))
        if missing:
            raise ValueError(
                "wallet-flow diagnostics CSV missing required fields: " + ", ".join(missing)
            )
        for row in reader:
            if str(row.get("retained_after_dedup", "")).strip() == "True":
                grade = str(row.get("final_grade", "")).strip().upper()
                if grade:
                    counts[grade] += 1
    return counts


def _wallet_flow_top_blockers(summary_text: str) -> list[str]:
    section_match = re.search(
        r"##\s*Top Blockers\s*\n(?P<body>.*?)(?:\n##\s+|\Z)",
        summary_text,
        flags=re.DOTALL,
    )
    if not section_match:
        return []
    section_body = section_match.group("body")
    matches = re.findall(r"^\s*-\s*([a-zA-Z0-9_]+):\s*\d+\s*$", section_body, flags=re.MULTILINE)
    if not matches:
        return []
    blockers: list[str] = []
    for label in matches[:3]:
        blockers.append(_humanize_blocker(label))
    return blockers


def _humanize_blocker(raw_label: str) -> str:
    normalized = raw_label.strip().replace("-", "_").replace(" ", "_").upper()
    if not normalized:
        return "UNKNOWN_BLOCKER"
    return normalized
