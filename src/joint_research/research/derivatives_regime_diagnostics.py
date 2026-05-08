"""Read-only diagnostics for committed derivatives-regime research artifacts."""

from __future__ import annotations

import csv
import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

GRADE_SIMULATION_READY = "SIMULATION_READY"
GRADE_WATCHLIST = "WATCHLIST"
GRADE_WEAK = "WEAK"

REQUIRED_RESULTS_FIELDS = {"grade", "filter_reason"}
DEFAULT_TOP_BLOCKERS = 3
SUMMARY_BLOCK_MARKERS = (
    "exploratory only - not tradeable",
    "no live trading",
    "not tradeable",
    "paper simulation only",
    "no execution",
)


@dataclass(frozen=True)
class DerivativesRegimeDiagnosticsInputPaths:
    results_csv_path: Path
    candidates_json_path: Path
    summary_md_path: Path | None = None


@dataclass(frozen=True)
class DiagnosticAvailability:
    available: bool
    reason_unavailable: str | None = None


@dataclass(frozen=True)
class NumericDistribution:
    count: int
    min_value: float
    p25: float
    median: float
    p75: float
    max_value: float
    negative_count: int
    zero_count: int
    positive_count: int


@dataclass(frozen=True)
class ConcentrationRow:
    dimensions: dict[str, str]
    count: int
    share_of_subset: float


@dataclass(frozen=True)
class DerivativesRegimeDiagnostics:
    total_result_rows: int
    grade_counts: dict[str, int]
    failure_reason_counts: dict[str, int]
    candidate_grade_counts: dict[str, int]
    weak_candidate_count: int
    simulation_ready_count: int
    watchlist_count: int
    top_blocker_names: list[str]
    promotion_blocked: bool
    trade_decision_blocked: bool
    asset_row_counts: dict[str, int] | None
    segment_regime_row_counts: dict[str, int] | None
    sample_sufficiency_failure_concentration: list[ConcentrationRow] | None
    direction_mismatch_concentration: list[ConcentrationRow] | None
    baseline_improvement_distribution: NumericDistribution | None
    weak_candidate_concentration: list[ConcentrationRow] | None
    diagnostics_availability: dict[str, DiagnosticAvailability]


def run_derivatives_regime_diagnostics(
    *,
    results_csv_path: Path,
    candidates_json_path: Path,
    summary_md_path: Path | None = None,
    top_blocker_limit: int = DEFAULT_TOP_BLOCKERS,
) -> DerivativesRegimeDiagnostics:
    """Compute read-only diagnostics from committed derivatives-regime artifacts."""
    paths = DerivativesRegimeDiagnosticsInputPaths(
        results_csv_path=results_csv_path,
        candidates_json_path=candidates_json_path,
        summary_md_path=summary_md_path,
    )
    return compute_derivatives_regime_diagnostics(paths=paths, top_blocker_limit=top_blocker_limit)


def compute_derivatives_regime_diagnostics(
    *,
    paths: DerivativesRegimeDiagnosticsInputPaths,
    top_blocker_limit: int = DEFAULT_TOP_BLOCKERS,
) -> DerivativesRegimeDiagnostics:
    if top_blocker_limit <= 0:
        raise ValueError("top_blocker_limit must be positive")

    results_rows, result_fields = _load_results_rows(paths.results_csv_path)
    missing_fields = sorted(REQUIRED_RESULTS_FIELDS - set(result_fields))
    if missing_fields:
        raise ValueError(
            "results CSV missing required fields: " + ", ".join(missing_fields)
        )

    candidate_rows = _load_candidate_rows(paths.candidates_json_path)
    summary_text = _load_optional_summary(paths.summary_md_path)

    grade_counts = _count_labeled_rows(results_rows, grade_field="grade", status_field=None)
    failure_reason_counts = _count_reasons(results_rows, field_name="filter_reason")
    candidate_grade_counts = _count_labeled_rows(
        candidate_rows,
        grade_field="grade",
        status_field="status",
    )

    simulation_ready_count = grade_counts.get(GRADE_SIMULATION_READY, 0)
    watchlist_count = grade_counts.get(GRADE_WATCHLIST, 0)
    weak_candidate_count = candidate_grade_counts.get(GRADE_WEAK, 0)

    top_blocker_names = _top_blockers(
        failure_reason_counts=failure_reason_counts,
        limit=top_blocker_limit,
    )

    promotion_blocked = simulation_ready_count == 0 and watchlist_count == 0
    trade_decision_blocked = promotion_blocked or simulation_ready_count == 0
    if summary_text:
        normalized = _normalize_label(summary_text)
        if any(marker in normalized for marker in SUMMARY_BLOCK_MARKERS):
            trade_decision_blocked = True

    (
        asset_row_counts,
        asset_row_counts_availability,
    ) = _compute_asset_row_counts(results_rows, result_fields)
    (
        segment_regime_row_counts,
        segment_regime_row_counts_availability,
    ) = _compute_segment_regime_row_counts(results_rows, result_fields)
    (
        sample_sufficiency_failure_concentration,
        sample_sufficiency_availability,
    ) = _compute_reason_concentration(
        results_rows,
        result_fields,
        reason_field="filter_reason",
        target_reason="insufficient_samples",
    )
    (
        direction_mismatch_concentration,
        direction_mismatch_availability,
    ) = _compute_reason_concentration(
        results_rows,
        result_fields,
        reason_field="filter_reason",
        target_reason="train_test_direction_mismatch",
    )
    (
        baseline_improvement_distribution,
        baseline_improvement_availability,
    ) = _compute_numeric_distribution(
        rows=results_rows,
        fields=result_fields,
        field_name="test_improvement_over_baseline",
    )
    (
        weak_candidate_concentration,
        weak_candidate_availability,
    ) = _compute_weak_candidate_concentration(candidate_rows)

    diagnostics_availability = {
        "asset_row_counts": asset_row_counts_availability,
        "segment_regime_row_counts": segment_regime_row_counts_availability,
        "sample_sufficiency_failure_concentration": sample_sufficiency_availability,
        "direction_mismatch_concentration": direction_mismatch_availability,
        "baseline_improvement_distribution": baseline_improvement_availability,
        "weak_candidate_concentration": weak_candidate_availability,
    }

    return DerivativesRegimeDiagnostics(
        total_result_rows=len(results_rows),
        grade_counts=dict(grade_counts),
        failure_reason_counts=dict(failure_reason_counts),
        candidate_grade_counts=dict(candidate_grade_counts),
        weak_candidate_count=weak_candidate_count,
        simulation_ready_count=simulation_ready_count,
        watchlist_count=watchlist_count,
        top_blocker_names=top_blocker_names,
        promotion_blocked=promotion_blocked,
        trade_decision_blocked=trade_decision_blocked,
        asset_row_counts=asset_row_counts,
        segment_regime_row_counts=segment_regime_row_counts,
        sample_sufficiency_failure_concentration=sample_sufficiency_failure_concentration,
        direction_mismatch_concentration=direction_mismatch_concentration,
        baseline_improvement_distribution=baseline_improvement_distribution,
        weak_candidate_concentration=weak_candidate_concentration,
        diagnostics_availability=diagnostics_availability,
    )


def _load_results_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    return rows, fieldnames


def _load_candidate_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows: list[Any]
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = []
        for key in ("rows", "candidates", "results"):
            candidate_rows = payload.get(key)
            if isinstance(candidate_rows, list):
                rows = candidate_rows
                break
        if not rows:
            keys = ", ".join(sorted(payload.keys()))
            raise ValueError(
                "candidates JSON object must include a rows/candidates/results list; "
                f"found keys: [{keys}]"
            )
    else:
        raise ValueError(
            f"candidates JSON payload must be list or object, got {type(payload).__name__}"
        )

    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(
                f"candidate row {index} must be an object, got {type(row).__name__}"
            )
    return [dict(row) for row in rows]


def _load_optional_summary(path: Path | None) -> str | None:
    if path is None:
        return None
    return path.read_text(encoding="utf-8")


def _normalize_label(value: str) -> str:
    return value.strip().upper()


def _count_labeled_rows(
    rows: list[dict[str, Any]],
    *,
    grade_field: str,
    status_field: str | None,
) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        grade = _normalize_label(str(row.get(grade_field, "")))
        status = _normalize_label(str(row.get(status_field, ""))) if status_field else ""
        label = grade or status
        if label:
            counts[label] += 1
    return counts


def _count_reasons(rows: list[dict[str, Any]], *, field_name: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        reason = _normalize_label(str(row.get(field_name, "")))
        if reason:
            counts[reason] += 1
    return counts


def _top_blockers(*, failure_reason_counts: Counter[str], limit: int) -> list[str]:
    ranked: list[tuple[str, int]] = [
        (reason, count)
        for reason, count in failure_reason_counts.items()
        if reason and reason != "PASSED"
    ]
    ranked.sort(key=lambda item: (-item[1], item[0]))
    return [reason for reason, _count in ranked[:limit]]


def _compute_asset_row_counts(
    rows: list[dict[str, str]],
    fields: list[str],
) -> tuple[dict[str, int] | None, DiagnosticAvailability]:
    if "asset" not in fields:
        return None, DiagnosticAvailability(available=False, reason_unavailable="missing asset field")

    counts: Counter[str] = Counter()
    for row in rows:
        label = _normalize_dimension(row.get("asset"))
        counts[label] += 1
    return dict(counts), DiagnosticAvailability(available=True)


def _compute_segment_regime_row_counts(
    rows: list[dict[str, str]],
    fields: list[str],
) -> tuple[dict[str, int] | None, DiagnosticAvailability]:
    required_any = {"segment_type", "segment_value", "combined_regime"}
    if not any(field in fields for field in required_any):
        return (
            None,
            DiagnosticAvailability(
                available=False,
                reason_unavailable="missing segment/regime fields",
            ),
        )

    counts: Counter[str] = Counter()
    for row in rows:
        segment_type = _normalize_dimension(row.get("segment_type"))
        segment_value = _normalize_dimension(row.get("segment_value"))
        combined_regime = _normalize_dimension(row.get("combined_regime"))
        label = f"{segment_type}|{segment_value}|{combined_regime}"
        counts[label] += 1
    return dict(counts), DiagnosticAvailability(available=True)


def _compute_reason_concentration(
    rows: list[dict[str, str]],
    fields: list[str],
    *,
    reason_field: str,
    target_reason: str,
) -> tuple[list[ConcentrationRow] | None, DiagnosticAvailability]:
    required_dimensions = ["asset", "segment_type", "segment_value", "combined_regime"]
    available_dimensions = [field for field in required_dimensions if field in fields]
    if reason_field not in fields or not available_dimensions:
        return (
            None,
            DiagnosticAvailability(
                available=False,
                reason_unavailable="missing reason or grouping fields",
            ),
        )

    reason_label = _normalize_label(target_reason)
    subset = [row for row in rows if _normalize_label(str(row.get(reason_field, ""))) == reason_label]
    if not subset:
        return [], DiagnosticAvailability(available=True)

    grouped: Counter[tuple[str, ...]] = Counter()
    for row in subset:
        key = tuple(_normalize_dimension(row.get(field)) for field in available_dimensions)
        grouped[key] += 1

    total = len(subset)
    ranked: list[ConcentrationRow] = []
    for key_tuple, count in sorted(grouped.items(), key=lambda item: (-item[1], item[0])):
        dimensions = {
            available_dimensions[index]: value
            for index, value in enumerate(key_tuple)
        }
        ranked.append(
            ConcentrationRow(
                dimensions=dimensions,
                count=count,
                share_of_subset=count / total,
            )
        )
    return ranked, DiagnosticAvailability(available=True)


def _compute_numeric_distribution(
    *,
    rows: list[dict[str, str]],
    fields: list[str],
    field_name: str,
) -> tuple[NumericDistribution | None, DiagnosticAvailability]:
    if field_name not in fields:
        return (
            None,
            DiagnosticAvailability(
                available=False,
                reason_unavailable=f"missing {field_name} field",
            ),
        )

    values: list[float] = []
    for row in rows:
        numeric_value = _parse_optional_float(row.get(field_name))
        if numeric_value is not None and math.isfinite(numeric_value):
            values.append(numeric_value)

    if not values:
        return (
            None,
            DiagnosticAvailability(
                available=False,
                reason_unavailable=f"no parseable finite values in {field_name}",
            ),
        )

    values.sort()
    distribution = NumericDistribution(
        count=len(values),
        min_value=values[0],
        p25=_quantile(values, 0.25),
        median=_quantile(values, 0.50),
        p75=_quantile(values, 0.75),
        max_value=values[-1],
        negative_count=sum(1 for value in values if value < 0.0),
        zero_count=sum(1 for value in values if value == 0.0),
        positive_count=sum(1 for value in values if value > 0.0),
    )
    return distribution, DiagnosticAvailability(available=True)


def _compute_weak_candidate_concentration(
    rows: list[dict[str, Any]],
) -> tuple[list[ConcentrationRow] | None, DiagnosticAvailability]:
    dimensions = ["asset", "segment_type", "segment_value", "combined_regime"]
    available_dimensions = [dimension for dimension in dimensions if any(dimension in row for row in rows)]
    if not available_dimensions:
        return (
            None,
            DiagnosticAvailability(
                available=False,
                reason_unavailable="missing candidate asset/segment/regime fields",
            ),
        )

    weak_rows = [row for row in rows if _candidate_grade_label(row) == GRADE_WEAK]
    if not weak_rows:
        return [], DiagnosticAvailability(available=True)

    grouped: Counter[tuple[str, ...]] = Counter()
    for row in weak_rows:
        key = tuple(_normalize_dimension(row.get(dimension)) for dimension in available_dimensions)
        grouped[key] += 1

    total = len(weak_rows)
    ranked: list[ConcentrationRow] = []
    for key_tuple, count in sorted(grouped.items(), key=lambda item: (-item[1], item[0])):
        dimension_map = {
            available_dimensions[index]: value
            for index, value in enumerate(key_tuple)
        }
        ranked.append(
            ConcentrationRow(
                dimensions=dimension_map,
                count=count,
                share_of_subset=count / total,
            )
        )
    return ranked, DiagnosticAvailability(available=True)


def _candidate_grade_label(row: dict[str, Any]) -> str:
    grade = _normalize_label(str(row.get("grade", "")))
    status = _normalize_label(str(row.get("status", "")))
    return grade or status


def _normalize_dimension(raw_value: Any) -> str:
    if raw_value is None:
        return "UNKNOWN"
    text = str(raw_value).strip()
    if not text:
        return "UNKNOWN"
    return text.upper()


def _parse_optional_float(raw_value: str | None) -> float | None:
    if raw_value is None:
        return None
    value = raw_value.strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _quantile(values: list[float], probability: float) -> float:
    if not values:
        raise ValueError("values must be non-empty")
    if probability <= 0.0:
        return values[0]
    if probability >= 1.0:
        return values[-1]
    position = (len(values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    weight = position - lower
    return values[lower] * (1.0 - weight) + values[upper] * weight
