from __future__ import annotations

import csv
from pathlib import Path

from joint_research.signalcourt.decision import build_trade_decision
from joint_research.signalcourt.paper_decision import build_paper_decision_result
from joint_research.signalcourt.paper_journal import (
    build_paper_journal_entry,
    journal_entry_allows_order,
)
from joint_research.signalcourt.passport import build_signal_passport
from joint_research.signalcourt.readiness import (
    build_derivatives_regime_readiness,
    build_wallet_flow_readiness,
)
from joint_research.signalcourt.risk_gate import (
    default_tiny_account_risk_config,
    evaluate_risk_gate,
)
from joint_research.signalcourt.verdict import build_research_court_verdict


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


def test_wallet_flow_full_pipeline_journal_entry() -> None:
    readiness = build_wallet_flow_readiness(
        signal_summary_md_path=WALLET_FLOW_SIGNAL_SUMMARY_MD,
        rejection_diagnostics_csv_path=WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV,
        rejection_summary_md_path=WALLET_FLOW_REJECTION_SUMMARY_MD,
    )
    passport = build_signal_passport(readiness)
    verdict = build_research_court_verdict(passport)
    trade_decision = build_trade_decision(verdict)
    paper_decision = build_paper_decision_result(trade_decision)
    risk_gate_result = evaluate_risk_gate(
        paper_decision,
        default_tiny_account_risk_config(50.0),
    )
    entry = build_paper_journal_entry(
        readiness,
        passport,
        verdict,
        trade_decision,
        paper_decision,
        risk_gate_result,
    )

    assert entry.final_status == "NO_TRADE_BLOCKED"
    assert entry.blocked is True
    assert entry.paper_order_allowed is False
    assert entry.live_order_allowed is False
    assert entry.block_reasons
    assert entry.non_authorization_notice
    assert entry.max_risk_usd == 0.50
    assert journal_entry_allows_order(entry) is False
    assert any(step.startswith("readiness:") for step in entry.decision_trace)
    assert any(step.startswith("passport:") for step in entry.decision_trace)
    assert any(step.startswith("verdict:") for step in entry.decision_trace)
    assert any(step.startswith("trade_decision:") for step in entry.decision_trace)
    assert any(step.startswith("paper_decision:") for step in entry.decision_trace)
    assert any(step.startswith("risk_gate:") for step in entry.decision_trace)


def test_derivatives_full_pipeline_journal_entry() -> None:
    readiness = build_derivatives_regime_readiness(
        results_csv_path=DERIVATIVES_RESULTS_CSV,
        candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        summary_md_path=DERIVATIVES_SUMMARY_MD,
    )
    passport = build_signal_passport(readiness)
    verdict = build_research_court_verdict(passport)
    trade_decision = build_trade_decision(verdict)
    paper_decision = build_paper_decision_result(trade_decision)
    risk_gate_result = evaluate_risk_gate(
        paper_decision,
        default_tiny_account_risk_config(100.0),
    )
    entry = build_paper_journal_entry(
        readiness,
        passport,
        verdict,
        trade_decision,
        paper_decision,
        risk_gate_result,
    )

    assert entry.final_status in {"NO_TRADE_BLOCKED", "WATCH_ONLY_BLOCKED"}
    assert entry.blocked is True
    assert entry.paper_order_allowed is False
    assert entry.live_order_allowed is False
    assert entry.block_reasons
    assert entry.non_authorization_notice
    assert entry.max_risk_usd == 1.00
    assert journal_entry_allows_order(entry) is False
    assert entry.source_artifacts


def test_journal_output_is_deterministic() -> None:
    readiness = build_derivatives_regime_readiness(
        results_csv_path=DERIVATIVES_RESULTS_CSV,
        candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        summary_md_path=DERIVATIVES_SUMMARY_MD,
    )
    passport = build_signal_passport(readiness)
    verdict = build_research_court_verdict(passport)
    trade_decision = build_trade_decision(verdict)
    paper_decision = build_paper_decision_result(trade_decision)
    risk_gate_result = evaluate_risk_gate(
        paper_decision,
        default_tiny_account_risk_config(100.0),
    )

    first = build_paper_journal_entry(
        readiness,
        passport,
        verdict,
        trade_decision,
        paper_decision,
        risk_gate_result,
    )
    second = build_paper_journal_entry(
        readiness,
        passport,
        verdict,
        trade_decision,
        paper_decision,
        risk_gate_result,
    )
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

    wallet_readiness = build_wallet_flow_readiness(
        signal_summary_md_path=wallet_signal_summary,
        rejection_diagnostics_csv_path=wallet_rejection_csv,
        rejection_summary_md_path=wallet_rejection_summary,
        signal_id="test-wallet",
    )
    wallet_passport = build_signal_passport(wallet_readiness)
    wallet_verdict = build_research_court_verdict(wallet_passport)
    wallet_trade_decision = build_trade_decision(wallet_verdict)
    wallet_paper_decision = build_paper_decision_result(wallet_trade_decision)
    wallet_risk = evaluate_risk_gate(wallet_paper_decision, default_tiny_account_risk_config(50.0))
    wallet_entry = build_paper_journal_entry(
        wallet_readiness,
        wallet_passport,
        wallet_verdict,
        wallet_trade_decision,
        wallet_paper_decision,
        wallet_risk,
    )

    derivatives_readiness = build_derivatives_regime_readiness(
        results_csv_path=derivatives_results,
        candidates_json_path=derivatives_candidates,
        summary_md_path=derivatives_summary,
        signal_id="test-derivatives",
    )
    derivatives_passport = build_signal_passport(derivatives_readiness)
    derivatives_verdict = build_research_court_verdict(derivatives_passport)
    derivatives_trade_decision = build_trade_decision(derivatives_verdict)
    derivatives_paper_decision = build_paper_decision_result(derivatives_trade_decision)
    derivatives_risk = evaluate_risk_gate(
        derivatives_paper_decision,
        default_tiny_account_risk_config(100.0),
    )
    derivatives_entry = build_paper_journal_entry(
        derivatives_readiness,
        derivatives_passport,
        derivatives_verdict,
        derivatives_trade_decision,
        derivatives_paper_decision,
        derivatives_risk,
    )

    assert wallet_entry.paper_order_allowed is False
    assert derivatives_entry.paper_order_allowed is False

    after_snapshot = {
        file_path.relative_to(tmp_path).as_posix(): file_path.read_bytes()
        for file_path in sorted(tmp_path.rglob("*"))
        if file_path.is_file()
    }
    assert after_snapshot == before_snapshot
