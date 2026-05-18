from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from joint_research.signalcourt.decision_preview import (
    ACTION_NO_TRADE,
    ACTION_WATCH_ONLY,
    SignalCourtDecisionPreview,
    build_decision_preview,
)
from joint_research.signalcourt.pipeline import (
    build_derivatives_regime_pipeline,
    build_wallet_flow_pipeline,
    pipeline_allows_order,
)
from joint_research.signalcourt.risk_gate import default_tiny_account_risk_config


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


def test_wallet_flow_blocked_lane_maps_to_no_trade() -> None:
    pipeline = _build_wallet_pipeline()
    preview = build_decision_preview(pipeline, run_id="preview_wallet")

    assert preview.decision_action == ACTION_NO_TRADE
    assert preview.paper_eligible is False
    assert preview.live_eligible is False
    assert preview.final_status == "NO_TRADE_BLOCKED"
    assert preview.verdict == "CLOSED_EXPLORATORY_ONLY"


def test_derivatives_watch_only_lane_maps_to_watch_only() -> None:
    pipeline = _build_derivatives_pipeline()
    preview = build_decision_preview(pipeline, run_id="preview_derivatives")

    assert preview.decision_action == ACTION_WATCH_ONLY
    assert preview.paper_eligible is False
    assert preview.live_eligible is False
    assert preview.final_status in {"WATCH_ONLY_BLOCKED", "NO_TRADE_BLOCKED"}
    assert preview.verdict in {"ACTIVE_RESEARCH_WEAK", "BLOCKED_PENDING_DIAGNOSTICS"}


def test_blocked_lanes_are_not_paper_or_live_eligible() -> None:
    wallet_preview = build_decision_preview(_build_wallet_pipeline())
    derivatives_preview = build_decision_preview(_build_derivatives_pipeline())

    for preview in (wallet_preview, derivatives_preview):
        assert preview.paper_eligible is False
        assert preview.live_eligible is False


def test_preview_includes_blocked_reasons_and_required_next_gates() -> None:
    preview = build_decision_preview(_build_derivatives_pipeline())
    assert preview.blocked_reasons
    assert preview.required_next_gates
    assert any("Resolve blocker:" in gate for gate in preview.required_next_gates)
    assert any("golden evaluations" in gate.lower() for gate in preview.required_next_gates)


def test_preview_includes_non_authorization_notice() -> None:
    preview = build_decision_preview(_build_wallet_pipeline())
    assert preview.non_authorization_notice
    lowered = preview.non_authorization_notice.lower()
    assert "does not authorize" in lowered or "non-executing" in lowered


def test_preview_does_not_include_order_placement_payloads() -> None:
    preview = build_decision_preview(_build_derivatives_pipeline())
    payload_text = json.dumps(asdict(preview), sort_keys=True).lower()
    forbidden_terms = [
        "place_order",
        "submit_order",
        "broker_api",
        "exchange_api",
        "live_enter",
        "paper_enter",
    ]
    for forbidden in forbidden_terms:
        assert forbidden not in payload_text


def test_preview_is_deterministic() -> None:
    first = build_decision_preview(_build_derivatives_pipeline(), run_id="deterministic")
    second = build_decision_preview(_build_derivatives_pipeline(), run_id="deterministic")
    assert first == second


def test_golden_blocked_no_execution_behavior_unchanged() -> None:
    wallet_pipeline = _build_wallet_pipeline()
    derivatives_pipeline = _build_derivatives_pipeline()

    wallet_preview = build_decision_preview(wallet_pipeline)
    derivatives_preview = build_decision_preview(derivatives_pipeline)

    assert pipeline_allows_order(wallet_pipeline) is False
    assert pipeline_allows_order(derivatives_pipeline) is False
    assert wallet_preview.paper_eligible is False
    assert wallet_preview.live_eligible is False
    assert derivatives_preview.paper_eligible is False
    assert derivatives_preview.live_eligible is False


def test_preview_accepts_journal_style_evidence_object() -> None:
    pipeline = _build_wallet_pipeline()
    preview = build_decision_preview(
        pipeline.journal_entry,
        run_id="journal_evidence",
    )
    assert isinstance(preview, SignalCourtDecisionPreview)
    assert preview.lane == pipeline.journal_entry.lane
    assert preview.verdict == pipeline.journal_entry.verdict
