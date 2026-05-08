from __future__ import annotations

import csv
from pathlib import Path

from joint_research.signalcourt.decision import (
    ACTION_LIVE_ENTER,
    ACTION_LIVE_REVIEW_REQUIRED,
    ACTION_NO_TRADE,
    ACTION_PAPER_ENTER,
    ACTION_PAPER_EXIT,
    ACTION_WATCH_ONLY,
    EXECUTION_MODE_NONE,
    build_trade_decision,
    decision_allows_execution,
)
from joint_research.signalcourt.passport import (
    build_derivatives_regime_passport,
    build_wallet_flow_passport,
)
from joint_research.signalcourt.verdict import (
    build_research_court_verdict,
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


def test_wallet_flow_trade_decision_from_committed_artifacts() -> None:
    passport = build_wallet_flow_passport(
        signal_summary_md_path=WALLET_FLOW_SIGNAL_SUMMARY_MD,
        rejection_diagnostics_csv_path=WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV,
        rejection_summary_md_path=WALLET_FLOW_REJECTION_SUMMARY_MD,
    )
    verdict = build_research_court_verdict(passport)
    decision = build_trade_decision(verdict)

    assert decision.action == ACTION_NO_TRADE
    assert decision.allowed is False
    assert decision.execution_mode == EXECUTION_MODE_NONE
    assert decision_allows_execution(decision) is False
    assert decision.non_authorization_notice
    assert decision.blockers


def test_derivatives_trade_decision_from_committed_artifacts() -> None:
    passport = build_derivatives_regime_passport(
        results_csv_path=DERIVATIVES_RESULTS_CSV,
        candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        summary_md_path=DERIVATIVES_SUMMARY_MD,
    )
    verdict = build_research_court_verdict(passport)
    decision = build_trade_decision(verdict)

    assert decision.action in {ACTION_NO_TRADE, ACTION_WATCH_ONLY}
    assert decision.allowed is False
    assert decision.execution_mode == EXECUTION_MODE_NONE
    assert decision_allows_execution(decision) is False
    assert decision.non_authorization_notice
    assert decision.blockers


def test_current_lanes_do_not_emit_execution_actions() -> None:
    wallet_decision = build_trade_decision(
        build_research_court_verdict(
            build_wallet_flow_passport(
                signal_summary_md_path=WALLET_FLOW_SIGNAL_SUMMARY_MD,
                rejection_diagnostics_csv_path=WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV,
                rejection_summary_md_path=WALLET_FLOW_REJECTION_SUMMARY_MD,
            )
        )
    )
    derivatives_decision = build_trade_decision(
        build_research_court_verdict(
            build_derivatives_regime_passport(
                results_csv_path=DERIVATIVES_RESULTS_CSV,
                candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
                summary_md_path=DERIVATIVES_SUMMARY_MD,
            )
        )
    )

    forbidden = {
        ACTION_PAPER_ENTER,
        ACTION_PAPER_EXIT,
        ACTION_LIVE_REVIEW_REQUIRED,
        ACTION_LIVE_ENTER,
    }
    assert wallet_decision.action not in forbidden
    assert derivatives_decision.action not in forbidden


def test_decision_is_deterministic() -> None:
    passport = build_derivatives_regime_passport(
        results_csv_path=DERIVATIVES_RESULTS_CSV,
        candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        summary_md_path=DERIVATIVES_SUMMARY_MD,
    )
    verdict = build_research_court_verdict(passport)
    decision_a = build_trade_decision(verdict)
    decision_b = build_trade_decision(verdict)
    assert decision_a == decision_b


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

    wallet_passport = build_wallet_flow_passport(
        signal_summary_md_path=wallet_signal_summary,
        rejection_diagnostics_csv_path=wallet_rejection_csv,
        rejection_summary_md_path=wallet_rejection_summary,
        signal_id="test-wallet",
    )
    derivatives_passport = build_derivatives_regime_passport(
        results_csv_path=derivatives_results,
        candidates_json_path=derivatives_candidates,
        summary_md_path=derivatives_summary,
        signal_id="test-derivatives",
    )
    _ = build_trade_decision(build_research_court_verdict(wallet_passport))
    _ = build_trade_decision(build_research_court_verdict(derivatives_passport))

    after_snapshot = {
        file_path.relative_to(tmp_path).as_posix(): file_path.read_bytes()
        for file_path in sorted(tmp_path.rglob("*"))
        if file_path.is_file()
    }
    assert after_snapshot == before_snapshot
