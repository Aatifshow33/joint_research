from __future__ import annotations

import csv
from pathlib import Path

import pytest

from joint_research.signalcourt.passport import (
    build_derivatives_regime_passport,
    build_wallet_flow_passport,
)
from joint_research.signalcourt.verdict import (
    VERDICT_ACTIVE_RESEARCH_WEAK,
    VERDICT_BLOCKED_PENDING_DIAGNOSTICS,
    VERDICT_CLOSED_EXPLORATORY_ONLY,
    VERDICT_READY_FOR_REVIEW,
    build_derivatives_regime_verdict,
    build_research_court_verdict,
    build_wallet_flow_verdict,
)


REPO_ROOT = Path(__file__).resolve().parents[1]

DERIVATIVES_ARTIFACT_DIR = REPO_ROOT / "artifacts/research/derivatives_regime"
DERIVATIVES_RESULTS_CSV = DERIVATIVES_ARTIFACT_DIR / "derivatives_regime_results.csv"
DERIVATIVES_CANDIDATES_JSON = DERIVATIVES_ARTIFACT_DIR / "derivatives_regime_candidates.json"
DERIVATIVES_SUMMARY_MD = DERIVATIVES_ARTIFACT_DIR / "derivatives_regime_summary.md"

WALLET_FLOW_ARTIFACT_DIR = REPO_ROOT / "artifacts/research/wallet_flow_signal"
WALLET_FLOW_SIGNAL_SUMMARY_MD = WALLET_FLOW_ARTIFACT_DIR / "wallet_flow_signal_summary.md"
WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV = (
    WALLET_FLOW_ARTIFACT_DIR / "wallet_flow_rejection_diagnostics.csv"
)
WALLET_FLOW_REJECTION_SUMMARY_MD = WALLET_FLOW_ARTIFACT_DIR / "wallet_flow_rejection_summary.md"


def test_wallet_flow_verdict_from_committed_artifacts() -> None:
    verdict = build_wallet_flow_verdict(
        signal_summary_md_path=WALLET_FLOW_SIGNAL_SUMMARY_MD,
        rejection_diagnostics_csv_path=WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV,
        rejection_summary_md_path=WALLET_FLOW_REJECTION_SUMMARY_MD,
    )

    assert verdict.verdict == VERDICT_CLOSED_EXPLORATORY_ONLY
    assert verdict.promotion_allowed is False
    assert verdict.trade_decision_allowed is False
    assert verdict.prosecutor_findings
    assert verdict.governance_blocks
    assert verdict.verdict != VERDICT_READY_FOR_REVIEW


def test_derivatives_regime_verdict_from_committed_artifacts() -> None:
    verdict = build_derivatives_regime_verdict(
        results_csv_path=DERIVATIVES_RESULTS_CSV,
        candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        summary_md_path=DERIVATIVES_SUMMARY_MD,
    )

    assert verdict.verdict in {VERDICT_ACTIVE_RESEARCH_WEAK, VERDICT_BLOCKED_PENDING_DIAGNOSTICS}
    assert verdict.promotion_allowed is False
    assert verdict.trade_decision_allowed is False
    assert verdict.prosecutor_findings
    assert verdict.governance_blocks
    assert verdict.verdict != VERDICT_READY_FOR_REVIEW


def test_current_lanes_never_ready_for_review() -> None:
    wallet_passport = build_wallet_flow_passport(
        signal_summary_md_path=WALLET_FLOW_SIGNAL_SUMMARY_MD,
        rejection_diagnostics_csv_path=WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV,
        rejection_summary_md_path=WALLET_FLOW_REJECTION_SUMMARY_MD,
    )
    derivatives_passport = build_derivatives_regime_passport(
        results_csv_path=DERIVATIVES_RESULTS_CSV,
        candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        summary_md_path=DERIVATIVES_SUMMARY_MD,
    )

    wallet_verdict = build_research_court_verdict(wallet_passport)
    derivatives_verdict = build_research_court_verdict(derivatives_passport)

    assert wallet_verdict.verdict != VERDICT_READY_FOR_REVIEW
    assert derivatives_verdict.verdict != VERDICT_READY_FOR_REVIEW


def test_verdict_is_deterministic() -> None:
    passport = build_derivatives_regime_passport(
        results_csv_path=DERIVATIVES_RESULTS_CSV,
        candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        summary_md_path=DERIVATIVES_SUMMARY_MD,
    )

    verdict_a = build_research_court_verdict(passport)
    verdict_b = build_research_court_verdict(passport)
    assert verdict_a == verdict_b


def test_missing_artifacts_fail_clearly(tmp_path: Path) -> None:
    missing = tmp_path / "missing.csv"
    with pytest.raises(FileNotFoundError, match="required artifact not found"):
        build_derivatives_regime_verdict(
            results_csv_path=missing,
            candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
            summary_md_path=DERIVATIVES_SUMMARY_MD,
        )

    with pytest.raises(FileNotFoundError, match="required artifact not found"):
        build_wallet_flow_verdict(
            signal_summary_md_path=missing,
            rejection_diagnostics_csv_path=WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV,
            rejection_summary_md_path=WALLET_FLOW_REJECTION_SUMMARY_MD,
        )


def test_no_output_files_are_written(tmp_path: Path) -> None:
    derivatives_results = tmp_path / "derivatives_results.csv"
    derivatives_results.write_text(
        "grade,filter_reason\nREJECTED,insufficient_samples\n",
        encoding="utf-8",
    )
    derivatives_candidates = tmp_path / "derivatives_candidates.json"
    derivatives_candidates.write_text("[]", encoding="utf-8")
    derivatives_summary = tmp_path / "derivatives_summary.md"
    derivatives_summary.write_text(
        "EXPLORATORY ONLY - NOT TRADEABLE\nNo live trading.",
        encoding="utf-8",
    )

    wallet_signal_summary = tmp_path / "wallet_signal_summary.md"
    wallet_signal_summary.write_text(
        "EXPLORATORY ONLY - NOT TRADEABLE\nNo live trading.",
        encoding="utf-8",
    )
    wallet_rejection_summary = tmp_path / "wallet_rejection_summary.md"
    wallet_rejection_summary.write_text(
        "## Top Blockers\n- improvement_below_cost_buffer: 10\n- weak_win_rate: 8\n",
        encoding="utf-8",
    )
    wallet_rejection_csv = tmp_path / "wallet_rejection.csv"
    with wallet_rejection_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["retained_after_dedup", "final_grade"],
        )
        writer.writeheader()
        writer.writerow({"retained_after_dedup": "True", "final_grade": "REJECTED"})

    before_snapshot = {
        file_path.relative_to(tmp_path).as_posix(): file_path.read_bytes()
        for file_path in sorted(tmp_path.rglob("*"))
        if file_path.is_file()
    }

    _ = build_derivatives_regime_verdict(
        results_csv_path=derivatives_results,
        candidates_json_path=derivatives_candidates,
        summary_md_path=derivatives_summary,
        signal_id="test-derivatives",
    )
    _ = build_wallet_flow_verdict(
        signal_summary_md_path=wallet_signal_summary,
        rejection_diagnostics_csv_path=wallet_rejection_csv,
        rejection_summary_md_path=wallet_rejection_summary,
        signal_id="test-wallet",
    )

    after_snapshot = {
        file_path.relative_to(tmp_path).as_posix(): file_path.read_bytes()
        for file_path in sorted(tmp_path.rglob("*"))
        if file_path.is_file()
    }
    assert after_snapshot == before_snapshot
