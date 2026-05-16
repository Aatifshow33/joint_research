from __future__ import annotations

import copy
import json
from dataclasses import asdict
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
WALLET_FLOW_SIGNAL_RESULTS_CSV = WALLET_FLOW_ARTIFACT_DIR / "wallet_flow_signal_results.csv"
WALLET_FLOW_SIGNAL_SUMMARY_MD = WALLET_FLOW_ARTIFACT_DIR / "wallet_flow_signal_summary.md"
WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV = (
    WALLET_FLOW_ARTIFACT_DIR / "wallet_flow_rejection_diagnostics.csv"
)
WALLET_FLOW_REJECTION_SUMMARY_MD = WALLET_FLOW_ARTIFACT_DIR / "wallet_flow_rejection_summary.md"

PROTECTED_ARTIFACTS = [
    DERIVATIVES_RESULTS_CSV,
    DERIVATIVES_CANDIDATES_JSON,
    DERIVATIVES_SUMMARY_MD,
    WALLET_FLOW_SIGNAL_RESULTS_CSV,
    WALLET_FLOW_SIGNAL_SUMMARY_MD,
    WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV,
    WALLET_FLOW_REJECTION_SUMMARY_MD,
]


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


def test_writer_creates_jsonl_inside_explicit_output_dir_and_is_deterministic(tmp_path: Path) -> None:
    pipeline, trace = _build_wallet_pipeline_and_trace()
    entry = pipeline.journal_entry
    output_dir = tmp_path / "journals"

    result_first = write_paper_journal_entry(entry, trace, output_dir, run_id="run_001")
    assert result_first.output_path.parent == output_dir.resolve()
    assert result_first.output_path.exists()
    assert result_first.output_path.name == "signalcourt_paper_journal_run_001.jsonl"
    assert result_first.records_written == 1
    assert result_first.blocked is True
    assert result_first.paper_order_allowed is False
    assert result_first.live_order_allowed is False
    assert result_first.non_authorization_notice

    first_bytes = result_first.output_path.read_bytes()
    result_second = write_paper_journal_entry(entry, trace, output_dir, run_id="run_001")
    second_bytes = result_second.output_path.read_bytes()
    assert result_first == result_second
    assert second_bytes.startswith(first_bytes)
    assert len(second_bytes) > len(first_bytes)

    lines = result_first.output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first_payload = json.loads(lines[0])
    second_payload = json.loads(lines[1])
    assert first_payload == second_payload
    payload = first_payload
    assert payload["non_authorization_notice"]
    assert payload["blocked"] is True
    assert payload["paper_order_allowed"] is False
    assert payload["live_order_allowed"] is False
    assert payload["trace_id"] == trace.trace_id
    assert payload["writer_safety_metadata"]["execution_enabled"] is False


def test_writer_preserves_blocked_status_for_wallet_and_derivatives(tmp_path: Path) -> None:
    wallet_pipeline, wallet_trace = _build_wallet_pipeline_and_trace()
    derivatives_pipeline, derivatives_trace = _build_derivatives_pipeline_and_trace()

    wallet_result = write_paper_journal_entry(
        wallet_pipeline.journal_entry,
        wallet_trace,
        tmp_path / "wallet",
        run_id="wallet_run",
    )
    derivatives_result = write_paper_journal_entry(
        derivatives_pipeline.journal_entry,
        derivatives_trace,
        tmp_path / "derivatives",
        run_id="derivatives_run",
    )

    wallet_payload = json.loads(wallet_result.output_path.read_text(encoding="utf-8").splitlines()[0])
    derivatives_payload = json.loads(
        derivatives_result.output_path.read_text(encoding="utf-8").splitlines()[0]
    )

    assert wallet_payload["final_status"] == "NO_TRADE_BLOCKED"
    assert wallet_payload["blocked"] is True
    assert wallet_payload["paper_order_allowed"] is False
    assert wallet_payload["live_order_allowed"] is False

    assert derivatives_payload["final_status"] in {"WATCH_ONLY_BLOCKED", "NO_TRADE_BLOCKED"}
    assert derivatives_payload["blocked"] is True
    assert derivatives_payload["paper_order_allowed"] is False
    assert derivatives_payload["live_order_allowed"] is False


@pytest.mark.parametrize("bad_run_id", ["../escape", "..", "nested/path", "bad\\path"])
def test_writer_rejects_path_traversal_run_id(tmp_path: Path, bad_run_id: str) -> None:
    pipeline, trace = _build_wallet_pipeline_and_trace()
    with pytest.raises(ValueError, match="run_id"):
        write_paper_journal_entry(pipeline.journal_entry, trace, tmp_path, run_id=bad_run_id)


def test_writer_rejects_missing_output_dir_and_does_not_mutate_inputs(tmp_path: Path) -> None:
    pipeline, trace = _build_wallet_pipeline_and_trace()
    entry = pipeline.journal_entry

    entry_before = copy.deepcopy(asdict(entry))
    trace_before = copy.deepcopy(asdict(trace))

    with pytest.raises(ValueError, match="output_dir"):
        write_paper_journal_entry(entry, trace, None)  # type: ignore[arg-type]

    _ = write_paper_journal_entry(entry, trace, tmp_path / "safe_out", run_id="safe_run")

    assert asdict(entry) == entry_before
    assert asdict(trace) == trace_before


def test_writer_does_not_modify_protected_artifacts(tmp_path: Path) -> None:
    before_artifacts = {path: path.read_bytes() for path in PROTECTED_ARTIFACTS}

    wallet_pipeline, wallet_trace = _build_wallet_pipeline_and_trace()
    derivatives_pipeline, derivatives_trace = _build_derivatives_pipeline_and_trace()

    _ = write_paper_journal_entry(
        wallet_pipeline.journal_entry,
        wallet_trace,
        tmp_path / "wallet_output",
        run_id="wallet_protected",
    )
    _ = write_paper_journal_entry(
        derivatives_pipeline.journal_entry,
        derivatives_trace,
        tmp_path / "derivatives_output",
        run_id="derivatives_protected",
    )

    after_artifacts = {path: path.read_bytes() for path in PROTECTED_ARTIFACTS}
    assert after_artifacts == before_artifacts
