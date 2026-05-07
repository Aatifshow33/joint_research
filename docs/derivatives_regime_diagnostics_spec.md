# Derivatives-Regime Diagnostics Spec

Status: DOCS-ONLY / SPEC-ONLY (NON-EXECUTING)

## Purpose

Define the next read-only diagnostics artifact/report for derivatives-regime evidence strengthening. This spec documents what future diagnostics should explain, which minimum schemas must be enforced, and how implementation acceptance should be judged without enabling execution or promotion.

## Inputs (committed artifacts only)

- `artifacts/research/derivatives_regime/derivatives_regime_results.csv`
- `artifacts/research/derivatives_regime/derivatives_regime_candidates.json`
- `artifacts/research/derivatives_regime/derivatives_regime_summary.md`
- `docs/derivatives_regime_artifact_review.md` (Phase 4.63 evidence snapshot)

## Evidence baseline from Phase 4.63

- Segment rows tested: 581
- SIMULATION_READY: 0
- WATCHLIST: 0
- WEAK: 158
- REJECTED: 423
- Candidate rows: 20
- Candidate grades: WEAK only
- Main blockers:
  - sample sufficiency gaps
  - train/test direction mismatch
  - insufficient strength/stability for promotion

## Required diagnostics coverage

### 1) Sample sufficiency by asset/segment/regime

Future diagnostics report must break out sample support by:

- `asset`
- `horizon_hours`
- `segment_type`
- `segment_value` (or `combined_regime` when applicable)
- `sample_count`
- coverage bucket (for example: `low_support`, `medium_support`, `high_support`)

It must identify where insufficient sample depth is concentrated.

### 2) Train/test direction mismatch by asset/segment/regime

Future diagnostics report must quantify mismatch concentration by:

- `asset`
- `horizon_hours`
- `segment_type`
- `segment_value` (or `combined_regime`)
- `train_test_direction_match` rate or mismatch count

It must rank the highest mismatch-prone groups.

### 3) Baseline improvement distribution

Future diagnostics report must summarize distribution of `test_improvement_over_baseline` by:

- `asset`
- `horizon_hours`
- `segment_type`
- grade bucket

It must separate marginal improvements from stronger improvements and flag where improvement is not stable.

### 4) Weak candidate concentration

Future diagnostics report must map WEAK concentration across:

- `asset`
- `horizon_hours`
- `segment_type`
- `filter_reason`

It must identify whether WEAK outcomes cluster in specific regime families.

### 5) Top failure reasons

Future diagnostics report must provide ranked failure reasons from committed results, including at least:

- `insufficient_samples`
- `train_test_direction_mismatch`
- `no_improvement_over_baseline`

It must include counts and percentage share of total rows for each reason.

## Minimum schema contract for future diagnostics artifacts

### Required diagnostics CSV files

1. `sample_sufficiency_by_segment.csv`
   Required columns:
   `asset, horizon_hours, segment_type, segment_value, combined_regime, sample_count, coverage_bucket`

2. `train_test_mismatch_by_segment.csv`
   Required columns:
   `asset, horizon_hours, segment_type, segment_value, combined_regime, rows, mismatch_rows, mismatch_rate`

3. `improvement_distribution_by_segment.csv`
   Required columns:
   `asset, horizon_hours, segment_type, grade, rows, median_test_improvement_over_baseline, p25_improvement, p75_improvement`

4. `weak_candidate_concentration.csv`
   Required columns:
   `asset, horizon_hours, segment_type, segment_value, filter_reason, weak_rows, weak_share`

5. `failure_reason_rank.csv`
   Required columns:
   `filter_reason, rows, share_of_total`

### Required diagnostics Markdown report

`derivatives_regime_diagnostics_report.md` must include:

- Status line: `EXPLORATORY ONLY - NOT TRADEABLE`
- Input artifact list with exact paths
- Section for each required diagnostics coverage area (1-5 above)
- Explicit statement that results are research-only and non-promotional
- Explicit statement that no trading authorization is implied

## Acceptance criteria for future implementation phase

- All required diagnostics CSV files are produced with required headers and non-empty data rows when input artifacts are non-empty.
- The diagnostics Markdown report includes all required sections and non-authorization language.
- Counts and percentages reconcile against committed input artifacts within deterministic tolerance (exact integer counts; deterministic rounding policy for percentages).
- Diagnostics output remains read-only, with no artifact refresh or research rerun behavior.
- Diagnostics output does not alter existing grades, thresholds, candidate statuses, or tradeability posture.

## Explicit non-authorization statement

This spec does not authorize ingestion, artifact refresh, rerunning research, paper trading, live trading, threshold loosening, or candidate promotion.

## Recommended next implementation phase

Implement a read-only `derivatives_regime_diagnostics_report` phase that consumes existing committed derivatives-regime artifacts, emits the defined diagnostics CSV/Markdown outputs, and preserves exploratory-only, non-tradeable policy boundaries.
