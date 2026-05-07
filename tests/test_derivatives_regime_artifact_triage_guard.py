from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ARTIFACT_DIR = Path("artifacts/research/derivatives_regime")
RESULTS_CSV = ARTIFACT_DIR / "derivatives_regime_results.csv"
SUMMARY_MD = ARTIFACT_DIR / "derivatives_regime_summary.md"
CANDIDATES_JSON = ARTIFACT_DIR / "derivatives_regime_candidates.json"

TRACKED_GRADES = ("SIMULATION_READY", "WATCHLIST", "WEAK", "REJECTED")


def _load_results_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    return rows, fieldnames


def _load_candidate_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        if isinstance(payload.get("rows"), list):
            rows = payload["rows"]
        elif isinstance(payload.get("candidates"), list):
            rows = payload["candidates"]
        elif isinstance(payload.get("results"), list):
            rows = payload["results"]
        else:
            keys = ", ".join(sorted(payload.keys()))
            raise AssertionError(
                "Unexpected candidates JSON structure: expected list payload or "
                f"rows/candidates/results list in object; found keys [{keys}]"
            )
    else:
        raise AssertionError(
            "Unexpected candidates JSON payload type: "
            f"{type(payload).__name__}; expected list or object"
        )

    for index, row in enumerate(rows, start=1):
        assert isinstance(row, dict), f"Candidate row {index} must be an object, got {type(row).__name__}"
    return rows


def _count_labeled_rows(rows: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        grade = str(row.get("grade", "")).strip()
        status = str(row.get("status", "")).strip()
        label = grade or status
        if label:
            counts[label] += 1
    return counts


def _extract_summary_counts(summary_text: str) -> dict[str, int]:
    pattern = re.compile(r"^\s*-\s*(SIMULATION_READY|WATCHLIST|WEAK|REJECTED):\s*(\d+)\s*$", re.MULTILINE)
    matches = pattern.findall(summary_text)
    return {label: int(value) for label, value in matches}


def test_derivatives_regime_artifact_triage_guard() -> None:
    assert ARTIFACT_DIR.exists(), f"Missing derivatives-regime artifact directory: {ARTIFACT_DIR}"
    assert ARTIFACT_DIR.is_dir(), f"Derivatives-regime artifact path is not a directory: {ARTIFACT_DIR}"

    required_artifacts = [RESULTS_CSV, SUMMARY_MD, CANDIDATES_JSON]
    missing = [str(path) for path in required_artifacts if not path.exists()]
    assert not missing, "Missing required derivatives-regime artifacts: " + ", ".join(missing)

    results_rows, result_fields = _load_results_rows(RESULTS_CSV)
    assert results_rows, f"{RESULTS_CSV} must contain at least one results row"

    required_result_fields = {
        "rank",
        "asset",
        "symbol",
        "horizon_hours",
        "segment_type",
        "segment_value",
        "grade",
        "filter_reason",
    }
    missing_result_fields = sorted(required_result_fields - set(result_fields))
    assert not missing_result_fields, (
        "Unexpected derivatives-regime results schema; missing required columns: "
        + ", ".join(missing_result_fields)
    )

    missing_grade_rows = [
        str(index)
        for index, row in enumerate(results_rows, start=1)
        if not str(row.get("grade", "")).strip()
    ]
    assert not missing_grade_rows, (
        "derivatives_regime_results.csv rows missing grade values at rows: "
        + ", ".join(missing_grade_rows[:20])
    )

    candidates_rows = _load_candidate_rows(CANDIDATES_JSON)
    assert candidates_rows, f"{CANDIDATES_JSON} must contain at least one candidate row"

    for index, row in enumerate(candidates_rows, start=1):
        has_grade = bool(str(row.get("grade", "")).strip())
        has_status = bool(str(row.get("status", "")).strip())
        assert has_grade or has_status, (
            f"Candidate row {index} must include a non-empty grade or status field"
        )

    results_counts = _count_labeled_rows(results_rows)
    candidate_counts = _count_labeled_rows(candidates_rows)
    tracked_grade_counts = {
        grade: results_counts.get(grade, 0) for grade in TRACKED_GRADES if grade in results_counts or grade in candidate_counts
    }
    assert tracked_grade_counts, (
        "No tracked grades found in derivatives-regime artifacts. "
        "Expected at least one of SIMULATION_READY, WATCHLIST, WEAK, REJECTED."
    )

    summary_text = SUMMARY_MD.read_text(encoding="utf-8")
    normalized_summary = summary_text.lower().replace("_", " ")

    summary_counts = _extract_summary_counts(summary_text)
    for grade, summary_count in summary_counts.items():
        results_count = results_counts.get(grade, 0)
        assert summary_count == results_count, (
            f"Summary {grade} count ({summary_count}) does not match results CSV count ({results_count})"
        )

    # Guard language should remain research-only and non-tradeable.
    assert "exploratory only - not tradeable" in normalized_summary, (
        "Summary must keep research-only guard language: EXPLORATORY ONLY - NOT TRADEABLE"
    )
    assert (
        "paper simulation only" in normalized_summary
        or "not tradeable" in normalized_summary
    ), "Summary must keep SIMULATION_READY as non-tradeable/research-only when discussed"
    assert "no live trading" in normalized_summary, "Summary must not authorize live trading"

    if results_counts.get("SIMULATION_READY", 0) > 0 or results_counts.get("WATCHLIST", 0) > 0:
        assert (
            "paper simulation only" in normalized_summary
        ), "SIMULATION_READY/WATCHLIST rows may be counted, but summary must keep them paper-simulation-only"
        assert (
            "no execution path" in normalized_summary or "no execution" in normalized_summary
        ), "SIMULATION_READY/WATCHLIST rows may be counted, but summary must not authorize execution"

    forbidden_promotion_phrases = [
        "live trading is enabled",
        "approved for live trading",
        "candidate promotion approved",
        "thresholds loosened",
    ]
    for phrase in forbidden_promotion_phrases:
        assert phrase not in normalized_summary, (
            f"Summary contains promotion/execution language that should not appear: {phrase}"
        )
