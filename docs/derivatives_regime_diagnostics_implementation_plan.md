# Derivatives-Regime Diagnostics Implementation Plan

Status: DOCS-ONLY / PLANNING-ONLY (NON-EXECUTING)

## 1. Current posture

Derivatives-regime remains an exploratory, non-tradeable research lane. The diagnostics chain is currently documentation-complete through Phase 4.68 and is ready for a future read-only implementation phase.

## 2. Source artifacts to read

Future implementation should read only committed artifacts:

- `artifacts/research/derivatives_regime/derivatives_regime_results.csv`
- `artifacts/research/derivatives_regime/derivatives_regime_candidates.json`
- `artifacts/research/derivatives_regime/derivatives_regime_summary.md`

Reference docs for behavior and schema:

- `docs/derivatives_regime_artifact_review.md` (Phase 4.63 evidence snapshot)
- `docs/derivatives_regime_evidence_strengthening_plan.md` (Phase 4.64 plan)
- `docs/derivatives_regime_diagnostics_spec.md` (Phase 4.66 diagnostics contract)

## 3. Proposed diagnostics outputs

Future read-only implementation should produce a diagnostics bundle under a dedicated diagnostics output directory, including:

- `sample_sufficiency_by_segment.csv`
- `train_test_mismatch_by_segment.csv`
- `improvement_distribution_by_segment.csv`
- `weak_candidate_concentration.csv`
- `failure_reason_rank.csv`
- `derivatives_regime_diagnostics_report.md`

These outputs are diagnostics artifacts only and must not modify existing research artifacts.

## 4. Proposed module/test files for future implementation

Suggested future implementation files:

- `src/joint_research/research/derivatives_regime_diagnostics.py`
  - load committed derivatives-regime artifacts
  - compute diagnostics tables
  - render Markdown summary
  - write diagnostics outputs

- `tests/test_research_derivatives_regime_diagnostics.py`
  - validate schema headers
  - validate deterministic counts/percentages
  - validate non-authorization/report language

- optional CLI surface (future phase only):
  - `tests/test_cli_derivatives_regime_diagnostics.py`
  - any CLI wiring should remain local/read-only and non-executing

## 5. Exact read-only behavior

Future implementation must:

- read from committed derivatives-regime artifacts only
- perform local aggregations/statistics only
- write diagnostics outputs only
- avoid ingestion calls
- avoid research rerun logic
- avoid threshold or candidate-grade mutation
- avoid execution/trading code paths

Future implementation must not:

- refresh/overwrite existing derivatives-regime research artifacts
- call external trading or execution systems
- promote candidates

## 6. Data fields/schema expected for future diagnostics CSV

The future implementation should enforce the following minimum CSV schema:

1. `sample_sufficiency_by_segment.csv`
   - `asset, horizon_hours, segment_type, segment_value, combined_regime, sample_count, coverage_bucket`

2. `train_test_mismatch_by_segment.csv`
   - `asset, horizon_hours, segment_type, segment_value, combined_regime, rows, mismatch_rows, mismatch_rate`

3. `improvement_distribution_by_segment.csv`
   - `asset, horizon_hours, segment_type, grade, rows, median_test_improvement_over_baseline, p25_improvement, p75_improvement`

4. `weak_candidate_concentration.csv`
   - `asset, horizon_hours, segment_type, segment_value, filter_reason, weak_rows, weak_share`

5. `failure_reason_rank.csv`
   - `filter_reason, rows, share_of_total`

## 7. Markdown report sections expected for future diagnostics summary

`derivatives_regime_diagnostics_report.md` should include:

- status line: `EXPLORATORY ONLY - NOT TRADEABLE`
- input artifact list with exact file paths
- sample sufficiency analysis by asset/segment/regime
- train/test mismatch concentration analysis
- baseline improvement distribution analysis
- weak candidate concentration analysis
- top failure reasons with ranked counts and shares
- concise interpretation of what is promising vs blocked
- explicit non-authorization language

## 8. Validation strategy

Future implementation validation should include:

- unit tests for CSV schema headers and required columns
- reconciliation tests that compare report counts against source artifact totals
- deterministic output checks for ordering and rounding policy
- non-authorization language assertions in Markdown output
- smoke test for read-only execution path that confirms no ingestion/research/trading code is invoked

## 9. Acceptance criteria for the future implementation phase

- all proposed diagnostics CSV files are generated with required columns
- diagnostics Markdown report includes all required sections
- row counts and percentage shares reconcile to source artifacts
- outputs are deterministic for unchanged inputs
- implementation is read-only with no ingestion/research rerun behavior
- no thresholds, candidate grades, or tradeability status are changed

## 10. Explicit non-authorization language

This plan does not authorize ingestion, artifact refresh, rerunning research, diagnostics artifact creation in this phase, paper trading, live trading, threshold loosening, or candidate promotion.
