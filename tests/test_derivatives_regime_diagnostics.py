from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from joint_research.research.derivatives_regime_diagnostics import (
    DerivativesRegimeDiagnosticsInputPaths,
    compute_derivatives_regime_diagnostics,
    run_derivatives_regime_diagnostics,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = REPO_ROOT / "artifacts/research/derivatives_regime"


def _write_results_csv(
    path: Path,
    rows: list[dict[str, str]],
    *,
    fieldnames: list[str],
) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_candidates_json(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(json.dumps(rows), encoding="utf-8")


def _minimal_results_rows() -> list[dict[str, str]]:
    return [
        {
            "grade": "WEAK",
            "filter_reason": "passed",
            "asset": "BTC",
            "segment_type": "funding_intensity",
            "segment_value": "normal",
            "combined_regime": "",
            "test_improvement_over_baseline": "0.1",
        },
        {
            "grade": "REJECTED",
            "filter_reason": "insufficient_samples",
            "asset": "ETH",
            "segment_type": "funding_direction",
            "segment_value": "positive",
            "combined_regime": "",
            "test_improvement_over_baseline": "-0.1",
        },
    ]


def test_missing_required_field_failure(tmp_path: Path) -> None:
    results_path = tmp_path / "results.csv"
    candidates_path = tmp_path / "candidates.json"

    _write_results_csv(
        results_path,
        [{"filter_reason": "passed"}],
        fieldnames=["filter_reason"],
    )
    _write_candidates_json(candidates_path, [{"grade": "WEAK"}])

    with pytest.raises(ValueError, match="missing required fields: grade"):
        run_derivatives_regime_diagnostics(
            results_csv_path=results_path,
            candidates_json_path=candidates_path,
        )


def test_grade_count_computation(tmp_path: Path) -> None:
    results_path = tmp_path / "results.csv"
    candidates_path = tmp_path / "candidates.json"

    rows = _minimal_results_rows() + [
        {
            "grade": "WATCHLIST",
            "filter_reason": "passed",
            "asset": "BTC",
            "segment_type": "combined_regime",
            "segment_value": "positive|normal|premium",
            "combined_regime": "positive|normal|premium",
            "test_improvement_over_baseline": "0.2",
        },
        {
            "grade": "SIMULATION_READY",
            "filter_reason": "passed",
            "asset": "BTC",
            "segment_type": "combined_regime",
            "segment_value": "positive|high|premium",
            "combined_regime": "positive|high|premium",
            "test_improvement_over_baseline": "0.3",
        },
    ]
    _write_results_csv(
        results_path,
        rows,
        fieldnames=list(rows[0].keys()),
    )
    _write_candidates_json(candidates_path, [{"grade": "WEAK"}])

    diagnostics = run_derivatives_regime_diagnostics(
        results_csv_path=results_path,
        candidates_json_path=candidates_path,
    )

    assert diagnostics.total_result_rows == 4
    assert diagnostics.grade_counts == {
        "WEAK": 1,
        "REJECTED": 1,
        "WATCHLIST": 1,
        "SIMULATION_READY": 1,
    }
    assert diagnostics.simulation_ready_count == 1
    assert diagnostics.watchlist_count == 1


def test_failure_reason_count_computation(tmp_path: Path) -> None:
    results_path = tmp_path / "results.csv"
    candidates_path = tmp_path / "candidates.json"
    rows = _minimal_results_rows() + [
        {
            "grade": "REJECTED",
            "filter_reason": "train_test_direction_mismatch",
            "asset": "BTC",
            "segment_type": "combined_regime",
            "segment_value": "negative|low|discount",
            "combined_regime": "negative|low|discount",
            "test_improvement_over_baseline": "0.0",
        }
    ]
    _write_results_csv(
        results_path,
        rows,
        fieldnames=list(rows[0].keys()),
    )
    _write_candidates_json(candidates_path, [{"grade": "WEAK"}])

    diagnostics = run_derivatives_regime_diagnostics(
        results_csv_path=results_path,
        candidates_json_path=candidates_path,
    )

    assert diagnostics.failure_reason_counts == {
        "PASSED": 1,
        "INSUFFICIENT_SAMPLES": 1,
        "TRAIN_TEST_DIRECTION_MISMATCH": 1,
    }
    assert diagnostics.top_blocker_names[:2] == [
        "INSUFFICIENT_SAMPLES",
        "TRAIN_TEST_DIRECTION_MISMATCH",
    ]


def test_candidate_grade_count_computation(tmp_path: Path) -> None:
    results_path = tmp_path / "results.csv"
    candidates_path = tmp_path / "candidates.json"

    rows = _minimal_results_rows()
    _write_results_csv(
        results_path,
        rows,
        fieldnames=list(rows[0].keys()),
    )
    _write_candidates_json(
        candidates_path,
        [
            {"grade": "WEAK", "asset": "BTC", "segment_type": "funding_intensity", "segment_value": "normal"},
            {"status": "WATCHLIST", "asset": "ETH", "segment_type": "funding_direction", "segment_value": "positive"},
            {"grade": "rejected", "asset": "ETH", "segment_type": "combined_regime", "segment_value": "x"},
        ],
    )

    diagnostics = run_derivatives_regime_diagnostics(
        results_csv_path=results_path,
        candidates_json_path=candidates_path,
    )

    assert diagnostics.candidate_grade_counts == {
        "WEAK": 1,
        "WATCHLIST": 1,
        "REJECTED": 1,
    }
    assert diagnostics.weak_candidate_count == 1


def test_missing_optional_fields_degrade_gracefully(tmp_path: Path) -> None:
    results_path = tmp_path / "results.csv"
    candidates_path = tmp_path / "candidates.json"

    _write_results_csv(
        results_path,
        [
            {"grade": "REJECTED", "filter_reason": "insufficient_samples"},
            {"grade": "WEAK", "filter_reason": "passed"},
        ],
        fieldnames=["grade", "filter_reason"],
    )
    _write_candidates_json(candidates_path, [{"grade": "WEAK"}])

    diagnostics = run_derivatives_regime_diagnostics(
        results_csv_path=results_path,
        candidates_json_path=candidates_path,
    )

    assert diagnostics.total_result_rows == 2
    assert diagnostics.asset_row_counts is None
    assert diagnostics.segment_regime_row_counts is None
    assert diagnostics.sample_sufficiency_failure_concentration is None
    assert diagnostics.direction_mismatch_concentration is None
    assert diagnostics.baseline_improvement_distribution is None
    assert diagnostics.diagnostics_availability["asset_row_counts"].available is False
    assert diagnostics.diagnostics_availability["baseline_improvement_distribution"].available is False


def test_current_committed_artifacts_can_be_read_successfully() -> None:
    diagnostics = run_derivatives_regime_diagnostics(
        results_csv_path=ARTIFACT_DIR / "derivatives_regime_results.csv",
        candidates_json_path=ARTIFACT_DIR / "derivatives_regime_candidates.json",
        summary_md_path=ARTIFACT_DIR / "derivatives_regime_summary.md",
    )

    assert diagnostics.total_result_rows > 0
    assert diagnostics.candidate_grade_counts


def test_current_committed_artifact_grade_counts_preserved() -> None:
    diagnostics = run_derivatives_regime_diagnostics(
        results_csv_path=ARTIFACT_DIR / "derivatives_regime_results.csv",
        candidates_json_path=ARTIFACT_DIR / "derivatives_regime_candidates.json",
    )

    assert diagnostics.grade_counts.get("SIMULATION_READY", 0) == 0
    assert diagnostics.grade_counts.get("WATCHLIST", 0) == 0
    assert diagnostics.grade_counts.get("WEAK", 0) == 158
    assert diagnostics.grade_counts.get("REJECTED", 0) == 423


def test_trade_decision_blocked_for_current_artifacts() -> None:
    diagnostics = run_derivatives_regime_diagnostics(
        results_csv_path=ARTIFACT_DIR / "derivatives_regime_results.csv",
        candidates_json_path=ARTIFACT_DIR / "derivatives_regime_candidates.json",
        summary_md_path=ARTIFACT_DIR / "derivatives_regime_summary.md",
    )
    assert diagnostics.trade_decision_blocked is True


def test_no_output_files_are_written(tmp_path: Path) -> None:
    results_path = tmp_path / "results.csv"
    candidates_path = tmp_path / "candidates.json"
    summary_path = tmp_path / "summary.md"
    rows = _minimal_results_rows()
    _write_results_csv(
        results_path,
        rows,
        fieldnames=list(rows[0].keys()),
    )
    _write_candidates_json(candidates_path, [{"grade": "WEAK"}])
    summary_path.write_text("EXPLORATORY ONLY - NOT TRADEABLE\nNo live trading.", encoding="utf-8")

    before_snapshot = {
        file_path.relative_to(tmp_path).as_posix(): file_path.read_bytes()
        for file_path in sorted(tmp_path.rglob("*"))
        if file_path.is_file()
    }

    compute_derivatives_regime_diagnostics(
        paths=DerivativesRegimeDiagnosticsInputPaths(
            results_csv_path=results_path,
            candidates_json_path=candidates_path,
            summary_md_path=summary_path,
        )
    )

    after_snapshot = {
        file_path.relative_to(tmp_path).as_posix(): file_path.read_bytes()
        for file_path in sorted(tmp_path.rglob("*"))
        if file_path.is_file()
    }

    assert after_snapshot == before_snapshot
