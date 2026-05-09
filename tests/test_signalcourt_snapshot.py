from __future__ import annotations

import csv
from pathlib import Path

from joint_research.signalcourt.pipeline import (
    build_derivatives_regime_pipeline,
    build_wallet_flow_pipeline,
)
from joint_research.signalcourt.risk_gate import default_tiny_account_risk_config
from joint_research.signalcourt.snapshot import (
    build_pipeline_snapshot,
    snapshot_allows_order,
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


def test_wallet_flow_snapshot_from_pipeline() -> None:
    pipeline = build_wallet_flow_pipeline(
        signal_summary_md_path=WALLET_FLOW_SIGNAL_SUMMARY_MD,
        rejection_diagnostics_csv_path=WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV,
        rejection_summary_md_path=WALLET_FLOW_REJECTION_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(50.0),
    )
    snapshot = build_pipeline_snapshot(pipeline)

    assert snapshot.lane == "wallet_flow_signal"
    assert snapshot.signal_id
    assert snapshot.final_status == "NO_TRADE_BLOCKED"
    assert snapshot.blocked is True
    assert snapshot.paper_order_allowed is False
    assert snapshot.live_order_allowed is False
    assert snapshot.readiness_status
    assert snapshot.passport_status
    assert snapshot.verdict
    assert snapshot.trade_action
    assert snapshot.paper_action
    assert snapshot.block_reasons
    assert snapshot.source_artifacts
    assert snapshot.next_required_evidence
    normalized_summary = snapshot.operator_summary.lower()
    assert "blocked" in normalized_summary
    assert "not tradeable" in normalized_summary
    assert "research-only" in normalized_summary
    assert snapshot.non_authorization_notice
    assert snapshot_allows_order(snapshot) is False


def test_derivatives_snapshot_from_pipeline() -> None:
    pipeline = build_derivatives_regime_pipeline(
        results_csv_path=DERIVATIVES_RESULTS_CSV,
        candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        summary_md_path=DERIVATIVES_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(100.0),
    )
    snapshot = build_pipeline_snapshot(pipeline)

    assert snapshot.lane == "derivatives_regime"
    assert snapshot.final_status in {"NO_TRADE_BLOCKED", "WATCH_ONLY_BLOCKED"}
    assert snapshot.blocked is True
    assert snapshot.paper_order_allowed is False
    assert snapshot.live_order_allowed is False
    assert snapshot.max_risk_usd == 1.00
    normalized_summary = snapshot.operator_summary.lower()
    assert "blocked" in normalized_summary
    assert "not tradeable" in normalized_summary
    assert "research-only" in normalized_summary
    assert snapshot.non_authorization_notice
    assert snapshot_allows_order(snapshot) is False


def test_snapshot_output_is_deterministic() -> None:
    pipeline = build_derivatives_regime_pipeline(
        results_csv_path=DERIVATIVES_RESULTS_CSV,
        candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        summary_md_path=DERIVATIVES_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(100.0),
    )
    first = build_pipeline_snapshot(pipeline)
    second = build_pipeline_snapshot(pipeline)
    assert first == second


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

    wallet_pipeline = build_wallet_flow_pipeline(
        signal_summary_md_path=wallet_signal_summary,
        rejection_diagnostics_csv_path=wallet_rejection_csv,
        rejection_summary_md_path=wallet_rejection_summary,
        risk_config=default_tiny_account_risk_config(50.0),
        signal_id="test-wallet",
    )
    derivatives_pipeline = build_derivatives_regime_pipeline(
        results_csv_path=derivatives_results,
        candidates_json_path=derivatives_candidates,
        summary_md_path=derivatives_summary,
        risk_config=default_tiny_account_risk_config(100.0),
        signal_id="test-derivatives",
    )

    wallet_snapshot = build_pipeline_snapshot(wallet_pipeline)
    derivatives_snapshot = build_pipeline_snapshot(derivatives_pipeline)

    assert wallet_snapshot.paper_order_allowed is False
    assert derivatives_snapshot.paper_order_allowed is False

    after_snapshot = {
        file_path.relative_to(tmp_path).as_posix(): file_path.read_bytes()
        for file_path in sorted(tmp_path.rglob("*"))
        if file_path.is_file()
    }
    assert after_snapshot == before_snapshot
