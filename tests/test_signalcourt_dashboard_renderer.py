from __future__ import annotations

import csv
from pathlib import Path

from joint_research.signalcourt.dashboard_model import build_current_signalcourt_dashboard_model
from joint_research.signalcourt.dashboard_renderer import (
    render_current_signalcourt_dashboard_summary,
    render_dashboard_summary,
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


def test_render_dashboard_summary_from_current_model() -> None:
    model = build_current_signalcourt_dashboard_model(
        wallet_signal_summary_md_path=WALLET_FLOW_SIGNAL_SUMMARY_MD,
        wallet_rejection_diagnostics_csv_path=WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV,
        wallet_rejection_summary_md_path=WALLET_FLOW_REJECTION_SUMMARY_MD,
        derivatives_results_csv_path=DERIVATIVES_RESULTS_CSV,
        derivatives_candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        derivatives_summary_md_path=DERIVATIVES_SUMMARY_MD,
    )
    summary = render_dashboard_summary(model)
    lowered = summary.lower()

    assert "signalcourt trader" in lowered
    assert "wallet-flow" in lowered
    assert "derivatives-regime" in lowered
    assert "no live trading" in lowered
    assert "no executable paper orders" in lowered
    assert "blocked" in lowered
    assert "not tradeable" in lowered
    assert "non-authorization notice" in lowered


def test_render_current_dashboard_summary_helper() -> None:
    summary = render_current_signalcourt_dashboard_summary(
        wallet_signal_summary_md_path=WALLET_FLOW_SIGNAL_SUMMARY_MD,
        wallet_rejection_diagnostics_csv_path=WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV,
        wallet_rejection_summary_md_path=WALLET_FLOW_REJECTION_SUMMARY_MD,
        derivatives_results_csv_path=DERIVATIVES_RESULTS_CSV,
        derivatives_candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        derivatives_summary_md_path=DERIVATIVES_SUMMARY_MD,
    )
    assert "SignalCourt Trader Dashboard Summary" in summary
    assert "Wallet-Flow (wallet_flow_signal)" in summary
    assert "Derivatives-Regime (derivatives_regime)" in summary


def test_renderer_output_is_deterministic() -> None:
    model = build_current_signalcourt_dashboard_model(
        wallet_signal_summary_md_path=WALLET_FLOW_SIGNAL_SUMMARY_MD,
        wallet_rejection_diagnostics_csv_path=WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV,
        wallet_rejection_summary_md_path=WALLET_FLOW_REJECTION_SUMMARY_MD,
        derivatives_results_csv_path=DERIVATIVES_RESULTS_CSV,
        derivatives_candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        derivatives_summary_md_path=DERIVATIVES_SUMMARY_MD,
    )
    first = render_dashboard_summary(model)
    second = render_dashboard_summary(model)
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

    summary = render_current_signalcourt_dashboard_summary(
        wallet_signal_summary_md_path=wallet_signal_summary,
        wallet_rejection_diagnostics_csv_path=wallet_rejection_csv,
        wallet_rejection_summary_md_path=wallet_rejection_summary,
        derivatives_results_csv_path=derivatives_results,
        derivatives_candidates_json_path=derivatives_candidates,
        derivatives_summary_md_path=derivatives_summary,
    )
    assert "SignalCourt Trader Dashboard Summary" in summary

    after_snapshot = {
        file_path.relative_to(tmp_path).as_posix(): file_path.read_bytes()
        for file_path in sorted(tmp_path.rglob("*"))
        if file_path.is_file()
    }
    assert after_snapshot == before_snapshot
