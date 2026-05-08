from __future__ import annotations

import csv
from pathlib import Path

import pytest

from joint_research.signalcourt.readiness import (
    build_derivatives_regime_readiness,
    build_wallet_flow_readiness,
    readiness_allows_trade_decision,
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


def test_build_derivatives_regime_readiness_from_committed_artifacts() -> None:
    readiness = build_derivatives_regime_readiness(
        results_csv_path=DERIVATIVES_RESULTS_CSV,
        candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        summary_md_path=DERIVATIVES_SUMMARY_MD,
    )

    assert readiness.research_only is True
    assert readiness.tradeable is False
    assert readiness.promotion_blocked is True
    assert readiness.trade_decision_blocked is True
    assert readiness.simulation_ready_count == 0
    assert readiness.watchlist_count == 0
    assert readiness.weak_count == 158
    assert readiness.rejected_count == 423
    assert "INSUFFICIENT_SAMPLES" in readiness.top_blockers
    assert "TRAIN_TEST_DIRECTION_MISMATCH" in readiness.top_blockers
    assert "NO_IMPROVEMENT_OVER_BASELINE" in readiness.top_blockers
    assert readiness_allows_trade_decision(readiness) is False


def test_build_wallet_flow_readiness_from_committed_artifacts() -> None:
    readiness = build_wallet_flow_readiness(
        signal_summary_md_path=WALLET_FLOW_SIGNAL_SUMMARY_MD,
        rejection_diagnostics_csv_path=WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV,
        rejection_summary_md_path=WALLET_FLOW_REJECTION_SUMMARY_MD,
    )

    assert readiness.research_only is True
    assert readiness.tradeable is False
    assert readiness.promotion_blocked is True
    assert readiness.trade_decision_blocked is True
    assert readiness.simulation_ready_count == 0
    assert readiness.watchlist_count == 0
    assert readiness.weak_count == 0
    assert readiness.rejected_count == 1082
    assert readiness.status == "EXPLORATORY_ONLY_NOT_TRADEABLE"
    assert "IMPROVEMENT_BELOW_COST_BUFFER" in readiness.top_blockers
    assert "INSUFFICIENT_UNIQUE_FLOW_HOURS" in readiness.top_blockers
    assert "WEAK_WIN_RATE" in readiness.top_blockers
    assert readiness_allows_trade_decision(readiness) is False


def test_missing_artifacts_fail_clearly(tmp_path: Path) -> None:
    missing_results = tmp_path / "missing_results.csv"
    with pytest.raises(FileNotFoundError, match="required artifact not found"):
        build_derivatives_regime_readiness(
            results_csv_path=missing_results,
            candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
            summary_md_path=DERIVATIVES_SUMMARY_MD,
        )

    missing_wallet = tmp_path / "missing_wallet_summary.md"
    with pytest.raises(FileNotFoundError, match="required artifact not found"):
        build_wallet_flow_readiness(
            signal_summary_md_path=missing_wallet,
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

    _ = build_derivatives_regime_readiness(
        results_csv_path=derivatives_results,
        candidates_json_path=derivatives_candidates,
        summary_md_path=derivatives_summary,
        signal_id="test-derivatives",
    )
    _ = build_wallet_flow_readiness(
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
