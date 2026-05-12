from __future__ import annotations

import csv
from pathlib import Path

from joint_research.signalcourt.dashboard_model import build_dashboard_model
from joint_research.signalcourt.dashboard_renderer import render_dashboard_summary
from joint_research.signalcourt.decision import (
    ACTION_LIVE_ENTER,
    ACTION_LIVE_REVIEW_REQUIRED,
    ACTION_NO_TRADE,
    ACTION_PAPER_ENTER,
    ACTION_PAPER_EXIT,
    ACTION_WATCH_ONLY,
    build_trade_decision,
)
from joint_research.signalcourt.paper_decision import (
    PAPER_ACTION_ENTER,
    PAPER_ACTION_EXIT,
    PAPER_ACTION_NO_TRADE,
    PAPER_ACTION_WATCH_ONLY,
    build_paper_decision_result,
)
from joint_research.signalcourt.paper_journal import build_paper_journal_entry
from joint_research.signalcourt.passport import build_signal_passport
from joint_research.signalcourt.pipeline import (
    build_derivatives_regime_pipeline,
    build_wallet_flow_pipeline,
    pipeline_allows_order,
)
from joint_research.signalcourt.readiness import (
    build_derivatives_regime_readiness,
    build_wallet_flow_readiness,
)
from joint_research.signalcourt.risk_gate import default_tiny_account_risk_config, evaluate_risk_gate
from joint_research.signalcourt.snapshot import build_pipeline_snapshot
from joint_research.signalcourt.trace import build_trace_from_pipeline_result, trace_allows_order
from joint_research.signalcourt.verdict import (
    VERDICT_ACTIVE_RESEARCH_WEAK,
    VERDICT_BLOCKED_PENDING_DIAGNOSTICS,
    VERDICT_CLOSED_EXPLORATORY_ONLY,
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


def _build_wallet_lane() -> dict[str, object]:
    readiness = build_wallet_flow_readiness(
        signal_summary_md_path=WALLET_FLOW_SIGNAL_SUMMARY_MD,
        rejection_diagnostics_csv_path=WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV,
        rejection_summary_md_path=WALLET_FLOW_REJECTION_SUMMARY_MD,
    )
    passport = build_signal_passport(readiness)
    verdict = build_research_court_verdict(passport)
    decision = build_trade_decision(verdict)
    paper_decision = build_paper_decision_result(decision)
    risk_gate = evaluate_risk_gate(paper_decision, default_tiny_account_risk_config(50.0))
    journal = build_paper_journal_entry(
        readiness,
        passport,
        verdict,
        decision,
        paper_decision,
        risk_gate,
    )
    pipeline = build_wallet_flow_pipeline(
        signal_summary_md_path=WALLET_FLOW_SIGNAL_SUMMARY_MD,
        rejection_diagnostics_csv_path=WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV,
        rejection_summary_md_path=WALLET_FLOW_REJECTION_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(50.0),
    )
    snapshot = build_pipeline_snapshot(pipeline)
    trace = build_trace_from_pipeline_result(pipeline)
    return {
        "readiness": readiness,
        "passport": passport,
        "verdict": verdict,
        "decision": decision,
        "paper_decision": paper_decision,
        "risk_gate": risk_gate,
        "journal": journal,
        "pipeline": pipeline,
        "snapshot": snapshot,
        "trace": trace,
    }


def _build_derivatives_lane() -> dict[str, object]:
    readiness = build_derivatives_regime_readiness(
        results_csv_path=DERIVATIVES_RESULTS_CSV,
        candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        summary_md_path=DERIVATIVES_SUMMARY_MD,
    )
    passport = build_signal_passport(readiness)
    verdict = build_research_court_verdict(passport)
    decision = build_trade_decision(verdict)
    paper_decision = build_paper_decision_result(decision)
    risk_gate = evaluate_risk_gate(paper_decision, default_tiny_account_risk_config(100.0))
    journal = build_paper_journal_entry(
        readiness,
        passport,
        verdict,
        decision,
        paper_decision,
        risk_gate,
    )
    pipeline = build_derivatives_regime_pipeline(
        results_csv_path=DERIVATIVES_RESULTS_CSV,
        candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        summary_md_path=DERIVATIVES_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(100.0),
    )
    snapshot = build_pipeline_snapshot(pipeline)
    trace = build_trace_from_pipeline_result(pipeline)
    return {
        "readiness": readiness,
        "passport": passport,
        "verdict": verdict,
        "decision": decision,
        "paper_decision": paper_decision,
        "risk_gate": risk_gate,
        "journal": journal,
        "pipeline": pipeline,
        "snapshot": snapshot,
        "trace": trace,
    }


def test_wallet_flow_golden_case_remains_blocked() -> None:
    lane = _build_wallet_lane()
    readiness = lane["readiness"]
    verdict = lane["verdict"]
    decision = lane["decision"]
    paper_decision = lane["paper_decision"]
    risk_gate = lane["risk_gate"]
    journal = lane["journal"]
    pipeline = lane["pipeline"]
    trace = lane["trace"]

    assert readiness.research_only is True
    assert readiness.tradeable is False
    assert readiness.promotion_blocked is True
    assert readiness.trade_decision_blocked is True

    assert verdict.verdict == VERDICT_CLOSED_EXPLORATORY_ONLY
    assert decision.action == ACTION_NO_TRADE
    assert paper_decision.paper_action == PAPER_ACTION_NO_TRADE
    assert risk_gate.risk_allowed is False
    assert risk_gate.paper_order_allowed is False
    assert risk_gate.live_order_allowed is False
    assert journal.final_status == "NO_TRADE_BLOCKED"
    assert trace_allows_order(trace) is False
    assert pipeline_allows_order(pipeline) is False


def test_derivatives_golden_case_remains_blocked() -> None:
    lane = _build_derivatives_lane()
    readiness = lane["readiness"]
    verdict = lane["verdict"]
    decision = lane["decision"]
    paper_decision = lane["paper_decision"]
    risk_gate = lane["risk_gate"]
    journal = lane["journal"]
    pipeline = lane["pipeline"]
    trace = lane["trace"]

    assert readiness.research_only is True
    assert readiness.tradeable is False
    assert readiness.promotion_blocked is True
    assert readiness.trade_decision_blocked is True

    assert verdict.verdict in {
        VERDICT_ACTIVE_RESEARCH_WEAK,
        VERDICT_BLOCKED_PENDING_DIAGNOSTICS,
    }
    assert decision.action in {ACTION_NO_TRADE, ACTION_WATCH_ONLY}
    assert paper_decision.paper_action in {PAPER_ACTION_NO_TRADE, PAPER_ACTION_WATCH_ONLY}
    assert risk_gate.risk_allowed is False
    assert risk_gate.paper_order_allowed is False
    assert risk_gate.live_order_allowed is False
    assert journal.final_status in {"NO_TRADE_BLOCKED", "WATCH_ONLY_BLOCKED"}
    assert trace_allows_order(trace) is False
    assert pipeline_allows_order(pipeline) is False


def test_dashboard_golden_case_remains_blocked() -> None:
    wallet_lane = _build_wallet_lane()
    derivatives_lane = _build_derivatives_lane()

    dashboard = build_dashboard_model(
        [wallet_lane["snapshot"], derivatives_lane["snapshot"]]
    )
    rendered = render_dashboard_summary(dashboard).lower()

    assert dashboard.any_order_allowed is False
    assert dashboard.paper_orders_allowed_count == 0
    assert dashboard.live_orders_allowed_count == 0
    assert dashboard.blocked_lanes_count == 2
    assert dashboard.global_status == "BLOCKED_RESEARCH_ONLY_NO_EXECUTION"
    assert "no live trading" in rendered
    assert "no executable paper orders" in rendered


def test_no_current_lane_emits_executable_actions_or_allows_orders() -> None:
    wallet_lane = _build_wallet_lane()
    derivatives_lane = _build_derivatives_lane()

    decisions = [wallet_lane["decision"], derivatives_lane["decision"]]
    paper_decisions = [wallet_lane["paper_decision"], derivatives_lane["paper_decision"]]
    pipelines = [wallet_lane["pipeline"], derivatives_lane["pipeline"]]
    traces = [wallet_lane["trace"], derivatives_lane["trace"]]

    forbidden_trade_actions = {
        ACTION_PAPER_ENTER,
        ACTION_PAPER_EXIT,
        ACTION_LIVE_REVIEW_REQUIRED,
        ACTION_LIVE_ENTER,
    }
    forbidden_paper_actions = {PAPER_ACTION_ENTER, PAPER_ACTION_EXIT}

    for decision in decisions:
        assert decision.action not in forbidden_trade_actions
    for paper_decision in paper_decisions:
        assert paper_decision.paper_action not in forbidden_paper_actions
    for pipeline in pipelines:
        assert pipeline_allows_order(pipeline) is False
    for trace in traces:
        assert trace_allows_order(trace) is False


def test_non_authorization_and_blocked_language_exists_across_chain() -> None:
    wallet_lane = _build_wallet_lane()
    derivatives_lane = _build_derivatives_lane()

    dashboard = build_dashboard_model(
        [wallet_lane["snapshot"], derivatives_lane["snapshot"]]
    )
    rendered = render_dashboard_summary(dashboard).lower()

    for lane in (wallet_lane, derivatives_lane):
        assert lane["readiness"].non_authorization_notice
        assert lane["passport"].non_authorization_notice
        assert lane["verdict"].non_authorization_notice
        assert lane["decision"].non_authorization_notice
        assert lane["risk_gate"].non_authorization_notice
        assert lane["journal"].non_authorization_notice
        assert lane["snapshot"].non_authorization_notice
        assert lane["trace"].non_authorization_notice
        assert lane["trace"].warnings
        assert any("blocked" in warning.lower() for warning in lane["trace"].warnings)

    assert dashboard.non_authorization_notice
    assert "blocked" in rendered or "research-only" in rendered


def test_golden_evaluations_do_not_write_output_files(tmp_path: Path) -> None:
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
        "## Top Blockers\n- weak_strength_or_stability: 5\n",
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
        signal_id="golden-wallet",
    )
    derivatives_pipeline = build_derivatives_regime_pipeline(
        results_csv_path=derivatives_results,
        candidates_json_path=derivatives_candidates,
        summary_md_path=derivatives_summary,
        risk_config=default_tiny_account_risk_config(100.0),
        signal_id="golden-derivatives",
    )
    wallet_trace = build_trace_from_pipeline_result(wallet_pipeline)
    derivatives_trace = build_trace_from_pipeline_result(derivatives_pipeline)
    dashboard = build_dashboard_model(
        [build_pipeline_snapshot(wallet_pipeline), build_pipeline_snapshot(derivatives_pipeline)]
    )
    rendered = render_dashboard_summary(dashboard)

    assert wallet_trace.blocked is True
    assert derivatives_trace.blocked is True
    assert "SignalCourt Trader Dashboard Summary" in rendered

    after_snapshot = {
        file_path.relative_to(tmp_path).as_posix(): file_path.read_bytes()
        for file_path in sorted(tmp_path.rglob("*"))
        if file_path.is_file()
    }
    assert after_snapshot == before_snapshot
