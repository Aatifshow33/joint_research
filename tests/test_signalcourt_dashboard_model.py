from __future__ import annotations

import csv
from pathlib import Path

from joint_research.signalcourt.dashboard_model import (
    build_current_signalcourt_dashboard_model,
    build_dashboard_model,
)
from joint_research.signalcourt.pipeline import (
    build_derivatives_regime_pipeline,
    build_wallet_flow_pipeline,
)
from joint_research.signalcourt.risk_gate import default_tiny_account_risk_config
from joint_research.signalcourt.snapshot import build_pipeline_snapshot


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


def test_build_dashboard_model_from_snapshots() -> None:
    wallet_pipeline = build_wallet_flow_pipeline(
        signal_summary_md_path=WALLET_FLOW_SIGNAL_SUMMARY_MD,
        rejection_diagnostics_csv_path=WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV,
        rejection_summary_md_path=WALLET_FLOW_REJECTION_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(50.0),
    )
    derivatives_pipeline = build_derivatives_regime_pipeline(
        results_csv_path=DERIVATIVES_RESULTS_CSV,
        candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        summary_md_path=DERIVATIVES_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(100.0),
    )
    snapshots = [build_pipeline_snapshot(wallet_pipeline), build_pipeline_snapshot(derivatives_pipeline)]
    model = build_dashboard_model(snapshots)

    assert len(model.lanes) == 2
    lanes = {lane.lane: lane for lane in model.lanes}
    assert "wallet_flow_signal" in lanes
    assert "derivatives_regime" in lanes
    assert model.global_status == "BLOCKED_RESEARCH_ONLY_NO_EXECUTION"
    assert model.any_order_allowed is False
    assert model.paper_orders_allowed_count == 0
    assert model.live_orders_allowed_count == 0
    assert model.blocked_lanes_count == 2
    assert model.warnings
    combined_warnings = " ".join(model.warnings).lower()
    assert "no live trading" in combined_warnings
    assert "research-only" in combined_warnings
    assert "blocked" in combined_warnings
    assert "live execution" not in model.next_best_action.lower()
    assert model.non_authorization_notice
    assert lanes["wallet_flow_signal"].blocked is True
    assert lanes["derivatives_regime"].blocked is True
    assert lanes["wallet_flow_signal"].paper_order_allowed is False
    assert lanes["derivatives_regime"].paper_order_allowed is False


def test_build_current_dashboard_model_convenience() -> None:
    model = build_current_signalcourt_dashboard_model(
        wallet_signal_summary_md_path=WALLET_FLOW_SIGNAL_SUMMARY_MD,
        wallet_rejection_diagnostics_csv_path=WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV,
        wallet_rejection_summary_md_path=WALLET_FLOW_REJECTION_SUMMARY_MD,
        derivatives_results_csv_path=DERIVATIVES_RESULTS_CSV,
        derivatives_candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        derivatives_summary_md_path=DERIVATIVES_SUMMARY_MD,
    )
    assert len(model.lanes) == 2
    assert model.any_order_allowed is False
    assert model.paper_orders_allowed_count == 0
    assert model.live_orders_allowed_count == 0
    assert model.blocked_lanes_count == 2


def test_dashboard_model_is_deterministic() -> None:
    wallet_pipeline = build_wallet_flow_pipeline(
        signal_summary_md_path=WALLET_FLOW_SIGNAL_SUMMARY_MD,
        rejection_diagnostics_csv_path=WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV,
        rejection_summary_md_path=WALLET_FLOW_REJECTION_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(50.0),
    )
    derivatives_pipeline = build_derivatives_regime_pipeline(
        results_csv_path=DERIVATIVES_RESULTS_CSV,
        candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        summary_md_path=DERIVATIVES_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(100.0),
    )
    snapshots = [build_pipeline_snapshot(wallet_pipeline), build_pipeline_snapshot(derivatives_pipeline)]
    first = build_dashboard_model(snapshots)
    second = build_dashboard_model(snapshots)
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

    model = build_current_signalcourt_dashboard_model(
        wallet_signal_summary_md_path=wallet_signal_summary,
        wallet_rejection_diagnostics_csv_path=wallet_rejection_csv,
        wallet_rejection_summary_md_path=wallet_rejection_summary,
        derivatives_results_csv_path=derivatives_results,
        derivatives_candidates_json_path=derivatives_candidates,
        derivatives_summary_md_path=derivatives_summary,
    )
    assert model.any_order_allowed is False
    assert model.paper_orders_allowed_count == 0

    after_snapshot = {
        file_path.relative_to(tmp_path).as_posix(): file_path.read_bytes()
        for file_path in sorted(tmp_path.rglob("*"))
        if file_path.is_file()
    }
    assert after_snapshot == before_snapshot
