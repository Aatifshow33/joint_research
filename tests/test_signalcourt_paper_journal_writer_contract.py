from __future__ import annotations

import json
from pathlib import Path

import pytest

from joint_research.signalcourt.paper_journal_writer import write_paper_journal_entry
from joint_research.signalcourt.pipeline import (
    build_derivatives_regime_pipeline,
    build_wallet_flow_pipeline,
)
from joint_research.signalcourt.risk_gate import default_tiny_account_risk_config
from joint_research.signalcourt.trace import build_trace_from_pipeline_result


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

EXPECTED_TRACE_STEPS = {
    "readiness",
    "passport",
    "verdict",
    "trade_decision",
    "paper_decision",
    "risk_gate",
    "paper_journal",
}


def _build_wallet_pipeline_and_trace():
    pipeline = build_wallet_flow_pipeline(
        signal_summary_md_path=WALLET_FLOW_SIGNAL_SUMMARY_MD,
        rejection_diagnostics_csv_path=WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV,
        rejection_summary_md_path=WALLET_FLOW_REJECTION_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(50.0),
    )
    trace = build_trace_from_pipeline_result(pipeline)
    return pipeline, trace


def _build_derivatives_pipeline_and_trace():
    pipeline = build_derivatives_regime_pipeline(
        results_csv_path=DERIVATIVES_RESULTS_CSV,
        candidates_json_path=DERIVATIVES_CANDIDATES_JSON,
        summary_md_path=DERIVATIVES_SUMMARY_MD,
        risk_config=default_tiny_account_risk_config(100.0),
    )
    trace = build_trace_from_pipeline_result(pipeline)
    return pipeline, trace


def test_writer_jsonl_contract_contains_required_safety_fields(tmp_path: Path) -> None:
    pipeline, trace = _build_wallet_pipeline_and_trace()
    result = write_paper_journal_entry(
        pipeline.journal_entry,
        trace,
        tmp_path / "contract_wallet",
        run_id="contract_wallet",
    )

    assert result.output_path.parent == (tmp_path / "contract_wallet").resolve()
    assert list(tmp_path.rglob("*.jsonl")) == [result.output_path]

    lines = result.output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])

    required_top_level = {
        "run_id",
        "trace_id",
        "lane",
        "signal_id",
        "final_status",
        "blocked",
        "paper_order_allowed",
        "live_order_allowed",
        "non_authorization_notice",
        "trace_summary",
        "writer_safety_metadata",
        "paper_journal_entry",
    }
    assert required_top_level.issubset(payload.keys())
    assert payload["run_id"] == "contract_wallet"
    assert payload["blocked"] is True
    assert payload["paper_order_allowed"] is False
    assert payload["live_order_allowed"] is False
    assert payload["non_authorization_notice"]
    assert payload["final_status"] == "NO_TRADE_BLOCKED"

    safety = payload["writer_safety_metadata"]
    assert safety["execution_enabled"] is False
    assert safety["network_calls_enabled"] is False
    assert safety["exchange_calls_enabled"] is False
    assert safety["artifact_mutation_enabled"] is False

    trace_summary = payload["trace_summary"]
    assert trace_summary["blocked"] is True
    assert trace_summary["paper_order_allowed"] is False
    assert trace_summary["live_order_allowed"] is False
    assert EXPECTED_TRACE_STEPS.issubset(set(trace_summary["step_names"]))

    assert result.safety_metadata["journal_scope"] == "explicit_output_dir_only"
    assert result.safety_metadata["execution_enabled"] == "false"
    assert result.safety_metadata["network_calls_enabled"] == "false"
    assert result.safety_metadata["exchange_calls_enabled"] == "false"
    assert result.safety_metadata["artifact_mutation_enabled"] == "false"


@pytest.mark.parametrize("lane_name", ["wallet", "derivatives"])
def test_writer_jsonl_contract_has_no_executable_or_broker_exchange_payload(
    tmp_path: Path,
    lane_name: str,
) -> None:
    if lane_name == "wallet":
        pipeline, trace = _build_wallet_pipeline_and_trace()
    else:
        pipeline, trace = _build_derivatives_pipeline_and_trace()

    result = write_paper_journal_entry(
        pipeline.journal_entry,
        trace,
        tmp_path / f"contract_{lane_name}",
        run_id=f"contract_{lane_name}",
    )
    payload = json.loads(result.output_path.read_text(encoding="utf-8").splitlines()[0])

    assert payload["blocked"] is True
    assert payload["paper_order_allowed"] is False
    assert payload["live_order_allowed"] is False
    assert payload["final_status"] in {"NO_TRADE_BLOCKED", "WATCH_ONLY_BLOCKED"}

    entry = payload["paper_journal_entry"]
    assert entry["paper_order_allowed"] is False
    assert entry["live_order_allowed"] is False
    assert entry["final_status"] in {"NO_TRADE_BLOCKED", "WATCH_ONLY_BLOCKED"}
    assert entry["trade_action"] in {"NO_TRADE", "WATCH_ONLY"}
    assert entry["paper_action"] in {"PAPER_NO_TRADE", "PAPER_WATCH_ONLY"}

    payload_text = json.dumps(payload, sort_keys=True).lower()
    forbidden_terms = [
        "live_enter",
        "paper_enter",
        "paper_exit",
        "live_review_required",
        "order_placement",
        "place_order",
        "submit_order",
        "broker_api",
        "exchange_api",
    ]
    for forbidden in forbidden_terms:
        assert forbidden not in payload_text
