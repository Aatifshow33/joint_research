from __future__ import annotations

import csv
from pathlib import Path

from joint_research.signalcourt.decision import build_trade_decision
from joint_research.signalcourt.paper_decision import build_paper_decision_result
from joint_research.signalcourt.passport import (
    build_derivatives_regime_passport,
    build_wallet_flow_passport,
)
from joint_research.signalcourt.readiness import build_derivatives_regime_readiness
from joint_research.signalcourt.risk_gate import (
    default_tiny_account_risk_config,
    evaluate_risk_gate,
    risk_gate_allows_order,
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


def test_default_tiny_account_risk_config_calculations() -> None:
    cfg_50 = default_tiny_account_risk_config(50.0)
    cfg_100 = default_tiny_account_risk_config(100.0)

    assert cfg_50.max_risk_per_trade_pct == 1.0
    assert cfg_50.max_daily_loss_pct == 2.0
    assert cfg_50.max_weekly_loss_pct == 5.0
    assert cfg_50.max_open_positions == 1
    assert cfg_50.allow_leverage is False
    assert cfg_50.allow_shorting is False
    assert cfg_50.allow_live_trading is False
    assert cfg_50.max_position_notional_usd <= 5.0

    assert cfg_100.max_position_notional_usd <= 10.0


def test_wallet_flow_risk_gate_pipeline_blocked() -> None:
    passport = build_wallet_flow_passport(
        signal_summary_md_path=WALLET_FLOW_SIGNAL_SUMMARY_MD,
        rejection_diagnostics_csv_path=WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV,
        rejection_summary_md_path=WALLET_FLOW_REJECTION_SUMMARY_MD,
    )
    verdict = build_research_court_verdict(passport)
    decision = build_trade_decision(verdict)
    paper_result = build_paper_decision_result(decision)
    risk_result = evaluate_risk_gate(paper_result, default_tiny_account_risk_config(50.0))

    assert risk_result.max_risk_usd == 0.50
    assert risk_result.max_daily_loss_usd == 1.00
    assert risk_result.max_weekly_loss_usd == 2.50
    assert risk_result.risk_allowed is False
    assert risk_result.paper_order_allowed is False
    assert risk_result.live_order_allowed is False
    assert risk_result.blocked is True
    assert risk_result.block_reasons
    assert risk_gate_allows_order(risk_result) is False
    assert risk_result.non_authorization_notice


def test_derivatives_regime_risk_gate_pipeline_blocked() -> None:
    # Start from readiness explicitly to satisfy full pipeline requirement.
    readiness = build_derivatives_regime_readiness(
        results_csv_path=DERIVATIVES_RESULTS_CSV,
        candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        summary_md_path=DERIVATIVES_SUMMARY_MD,
    )
    passport = build_derivatives_regime_passport(
        results_csv_path=DERIVATIVES_RESULTS_CSV,
        candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        summary_md_path=DERIVATIVES_SUMMARY_MD,
        signal_id=readiness.signal_id,
    )
    verdict = build_research_court_verdict(passport)
    decision = build_trade_decision(verdict)
    paper_result = build_paper_decision_result(decision)
    risk_result = evaluate_risk_gate(paper_result, default_tiny_account_risk_config(100.0))

    assert risk_result.max_risk_usd == 1.00
    assert risk_result.max_daily_loss_usd == 2.00
    assert risk_result.max_weekly_loss_usd == 5.00
    assert risk_result.risk_allowed is False
    assert risk_result.paper_order_allowed is False
    assert risk_result.live_order_allowed is False
    assert risk_result.blocked is True
    assert risk_result.block_reasons
    assert risk_gate_allows_order(risk_result) is False
    assert risk_result.non_authorization_notice


def test_risk_gate_output_is_deterministic() -> None:
    passport = build_derivatives_regime_passport(
        results_csv_path=DERIVATIVES_RESULTS_CSV,
        candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        summary_md_path=DERIVATIVES_SUMMARY_MD,
    )
    verdict = build_research_court_verdict(passport)
    decision = build_trade_decision(verdict)
    paper_result = build_paper_decision_result(decision)
    config = default_tiny_account_risk_config(100.0)

    first = evaluate_risk_gate(paper_result, config)
    second = evaluate_risk_gate(paper_result, config)
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

    wallet_result = evaluate_risk_gate(
        build_paper_decision_result(
            build_trade_decision(
                build_research_court_verdict(
                    build_wallet_flow_passport(
                        signal_summary_md_path=wallet_signal_summary,
                        rejection_diagnostics_csv_path=wallet_rejection_csv,
                        rejection_summary_md_path=wallet_rejection_summary,
                        signal_id="test-wallet",
                    )
                )
            )
        ),
        default_tiny_account_risk_config(50.0),
    )
    derivatives_result = evaluate_risk_gate(
        build_paper_decision_result(
            build_trade_decision(
                build_research_court_verdict(
                    build_derivatives_regime_passport(
                        results_csv_path=derivatives_results,
                        candidates_json_path=derivatives_candidates,
                        summary_md_path=derivatives_summary,
                        signal_id="test-derivatives",
                    )
                )
            )
        ),
        default_tiny_account_risk_config(100.0),
    )

    assert wallet_result.paper_order_allowed is False
    assert derivatives_result.paper_order_allowed is False

    after_snapshot = {
        file_path.relative_to(tmp_path).as_posix(): file_path.read_bytes()
        for file_path in sorted(tmp_path.rglob("*"))
        if file_path.is_file()
    }
    assert after_snapshot == before_snapshot
