from __future__ import annotations

from pathlib import Path

import pytest

from joint_research.signalcourt.decision import (
    ACTION_LIVE_ENTER,
    ACTION_LIVE_REVIEW_REQUIRED,
    ACTION_PAPER_ENTER,
    ACTION_PAPER_EXIT,
)
from joint_research.signalcourt.paper_journal_writer import write_paper_journal_entry
from joint_research.signalcourt.pipeline import (
    build_derivatives_regime_pipeline,
    build_wallet_flow_pipeline,
    pipeline_allows_order,
)
from joint_research.signalcourt.risk_gate import default_tiny_account_risk_config
from joint_research.signalcourt.trace import build_trace_from_pipeline_result, trace_allows_order
from joint_research.signalcourt.verdict import (
    VERDICT_ACTIVE_RESEARCH_WEAK,
    VERDICT_BLOCKED_PENDING_DIAGNOSTICS,
    VERDICT_CLOSED_EXPLORATORY_ONLY,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src" / "joint_research"

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

SIGNALCOURT_JOURNAL_ARTIFACT_DIR = REPO_ROOT / "artifacts" / "signalcourt" / "paper_journal"


def _build_wallet_pipeline():
    return build_wallet_flow_pipeline(
        signal_summary_md_path=WALLET_FLOW_SIGNAL_SUMMARY_MD,
        rejection_diagnostics_csv_path=WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV,
        rejection_summary_md_path=WALLET_FLOW_REJECTION_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(50.0),
    )


def _build_derivatives_pipeline():
    return build_derivatives_regime_pipeline(
        results_csv_path=DERIVATIVES_RESULTS_CSV,
        candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        summary_md_path=DERIVATIVES_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(100.0),
    )


def test_writer_is_not_wired_into_default_pipeline_or_cli_paths() -> None:
    pipeline_source = (SRC_ROOT / "signalcourt" / "pipeline.py").read_text(encoding="utf-8")
    cli_source = (SRC_ROOT / "cli.py").read_text(encoding="utf-8")

    assert "paper_journal_writer" not in pipeline_source
    assert "write_paper_journal_entry" not in pipeline_source
    assert "paper_journal_writer" not in cli_source
    assert "write_paper_journal_entry" not in cli_source


def test_default_pipeline_does_not_write_signalcourt_journal_artifacts() -> None:
    before = (
        {
            path.relative_to(SIGNALCOURT_JOURNAL_ARTIFACT_DIR).as_posix(): path.read_bytes()
            for path in sorted(SIGNALCOURT_JOURNAL_ARTIFACT_DIR.rglob("*"))
            if path.is_file()
        }
        if SIGNALCOURT_JOURNAL_ARTIFACT_DIR.exists()
        else {}
    )

    wallet_pipeline = _build_wallet_pipeline()
    derivatives_pipeline = _build_derivatives_pipeline()
    _ = build_trace_from_pipeline_result(wallet_pipeline)
    _ = build_trace_from_pipeline_result(derivatives_pipeline)

    after = (
        {
            path.relative_to(SIGNALCOURT_JOURNAL_ARTIFACT_DIR).as_posix(): path.read_bytes()
            for path in sorted(SIGNALCOURT_JOURNAL_ARTIFACT_DIR.rglob("*"))
            if path.is_file()
        }
        if SIGNALCOURT_JOURNAL_ARTIFACT_DIR.exists()
        else {}
    )
    assert after == before


def test_writer_still_requires_explicit_output_dir() -> None:
    wallet_pipeline = _build_wallet_pipeline()
    wallet_trace = build_trace_from_pipeline_result(wallet_pipeline)
    with pytest.raises(ValueError, match="output_dir"):
        write_paper_journal_entry(wallet_pipeline.journal_entry, wallet_trace, None)  # type: ignore[arg-type]


def test_current_lanes_remain_blocked_and_non_executable() -> None:
    wallet_pipeline = _build_wallet_pipeline()
    derivatives_pipeline = _build_derivatives_pipeline()
    wallet_trace = build_trace_from_pipeline_result(wallet_pipeline)
    derivatives_trace = build_trace_from_pipeline_result(derivatives_pipeline)

    assert wallet_pipeline.readiness.research_only is True
    assert wallet_pipeline.readiness.tradeable is False
    assert wallet_pipeline.readiness.promotion_blocked is True
    assert wallet_pipeline.readiness.trade_decision_blocked is True
    assert wallet_pipeline.verdict.verdict == VERDICT_CLOSED_EXPLORATORY_ONLY
    assert wallet_pipeline.final_status == "NO_TRADE_BLOCKED"
    assert pipeline_allows_order(wallet_pipeline) is False
    assert trace_allows_order(wallet_trace) is False

    assert derivatives_pipeline.readiness.research_only is True
    assert derivatives_pipeline.readiness.tradeable is False
    assert derivatives_pipeline.readiness.promotion_blocked is True
    assert derivatives_pipeline.readiness.trade_decision_blocked is True
    assert derivatives_pipeline.verdict.verdict in {
        VERDICT_ACTIVE_RESEARCH_WEAK,
        VERDICT_BLOCKED_PENDING_DIAGNOSTICS,
    }
    assert derivatives_pipeline.final_status in {"WATCH_ONLY_BLOCKED", "NO_TRADE_BLOCKED"}
    assert pipeline_allows_order(derivatives_pipeline) is False
    assert trace_allows_order(derivatives_trace) is False

    for decision in (wallet_pipeline.trade_decision, derivatives_pipeline.trade_decision):
        assert decision.action not in {
            ACTION_PAPER_ENTER,
            ACTION_PAPER_EXIT,
            ACTION_LIVE_REVIEW_REQUIRED,
            ACTION_LIVE_ENTER,
        }
    for paper_decision in (
        wallet_pipeline.paper_decision,
        derivatives_pipeline.paper_decision,
    ):
        assert paper_decision.paper_action not in {"PAPER_ENTER", "PAPER_EXIT"}
    for risk_gate in (wallet_pipeline.risk_gate, derivatives_pipeline.risk_gate):
        assert risk_gate.paper_order_allowed is False
        assert risk_gate.live_order_allowed is False
