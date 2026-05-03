# Wallet-flow Static Coverage Diagnostic Artifact Specification

Status: EXPLORATORY ONLY - NOT TRADEABLE

Codespaces repo path:
/workspaces/joint_research

Local Mac repo path reference:
/Users/muhammadaatif/joint_research

Current checkpoint:
91f4bf0 phase 4.46: add wallet-flow coverage diagnostic plan

This specification defines static diagnostic artifact shapes after the coverage diagnostic plan. It describes expected output files and schemas before any implementation, without generating artifacts or rerunning research.

This static coverage diagnostic artifact specification does not promote wallet-flow candidates.

This static coverage diagnostic artifact specification does not change thresholds.

This static coverage diagnostic artifact specification does not approve ingestion, execution, live trading, adapters, manifests, orders, or database mutation.

## Why this phase comes after the coverage diagnostic plan

- Phase 4.46 defined the coverage diagnostic plan.
- This phase defines expected artifact files and schemas before any implementation.
- Static schemas make future diagnostics reviewable before code writes outputs.
- The latest known result still had zero candidates beyond rejected.
- This specification does not generate artifacts or rerun research.

## Latest known outcome snapshot

- SIMULATION_READY: 0
- WATCHLIST: 0
- WEAK: 0
- REJECTED: 1049
- No wallet-flow candidate survived beyond REJECTED.

## Known rejection bottlenecks

- improvement_below_cost_buffer: 5426
- insufficient_unique_flow_hours: 4993
- weak_win_rate: 4904
- insufficient_unique_flow_hours motivates the coverage artifact set.
- cost-buffer and win-rate failures must be interpreted by coverage segment.

## Expected artifact directory

Future artifacts should be written under:
artifacts/research/wallet_flow_coverage_diagnostics/

This phase does not create that directory or write any artifacts.

## Static diagnostic artifact inventory

| Artifact | Format | Purpose | Required columns or keys | Boundary |
|----------|--------|---------|--------------------------|----------|
| market_coverage.csv | CSV | Summarize market-level usable flow history | market_id, market_slug, unique_flow_hours, total_flow_rows, coverage_bucket, first_flow_ts, last_flow_ts | Diagnostic only. |
| wallet_class_coverage.csv | CSV | Summarize wallet and wallet-class observation depth | wallet_class, wallet_count, unique_flow_hours, total_flow_rows, concentration_share, coverage_bucket | No wallet promotion. |
| horizon_coverage.csv | CSV | Compare coverage across prediction horizons | horizon_hours, market_count, unique_flow_hours, coverage_bucket, sparse_segment_count | No rerun approval. |
| missingness_summary.csv | CSV | Identify nulls, gaps, and empty flow buckets | field_name, null_count, null_rate, affected_markets, affected_wallet_classes | No ingestion approval. |
| concentration_diagnostics.csv | CSV | Detect whether flow is dominated by few wallets or markets | dimension, entity_id, entity_label, flow_share, rank, concentration_bucket | No live execution. |
| recency_distribution.csv | CSV | Measure stale versus recent flow coverage | dimension, entity_id, first_flow_ts, last_flow_ts, age_hours, recency_bucket | No tradeability claim. |
| cost_buffer_diagnostics.csv | CSV | Review edge versus cost buffer by coverage segment | coverage_bucket, horizon_hours, candidate_count, improvement_below_cost_buffer_count, median_edge_after_cost | No threshold loosening. |
| win_rate_by_coverage.csv | CSV | Review weak win rate by coverage segment | coverage_bucket, horizon_hours, candidate_count, weak_win_rate_count, median_win_rate | No candidate promotion. |
| rerun_readiness_checklist.md | Markdown | Decide whether a future rerun would test new evidence | coverage_reviewed, bottlenecks_explained, missingness_reviewed, concentration_reviewed, rerun_scope_required | No automatic rerun. |
| operator_notes.md | Markdown | Capture human-readable interpretation and caveats | summary, unresolved_gaps, recommended_next_step, safety_boundary | Exploratory only. |

## Required schema rules

- Every CSV artifact must include a header row.
- Every CSV artifact must be deterministic for the same input data.
- Every CSV artifact must sort rows by stable identifiers or explicit ranking fields.
- Timestamps must use UTC ISO-8601 text when present.
- Coverage buckets must be documented and must not change promotion thresholds.
- Counts must be integer-compatible.
- Rates and shares must be numeric and clearly named.
- Markdown artifacts must include a status line that says EXPLORATORY ONLY - NOT TRADEABLE.
- Markdown artifacts must state that they do not approve ingestion, execution, live trading, orders, or database mutation.
- Artifacts must not include secrets, API keys, auth tokens, private keys, or environment values.

## Non-goals

- Do not implement artifact writers in this phase.
- Do not create artifacts in this phase.
- Do not run wallet-flow ingestion in this phase.
- Do not rerun wallet-flow research in this phase.
- Do not change scoring, thresholds, or candidate classification.
- Do not promote any wallet, market, or candidate.
- Do not connect adapters or manifests.
- Do not approve live trading or orders.
- Do not mutate databases.

## Review checklist for future implementation

- [ ] Artifact directory is created only by a later implementation phase.
- [ ] Writers are deterministic and local-only.
- [ ] No network calls are added.
- [ ] No ingestion is triggered.
- [ ] No research rerun is triggered automatically.
- [ ] No thresholds are changed.
- [ ] No candidates are promoted.
- [ ] No secrets or environment values are written.
- [ ] Validation tests cover required columns or keys.
- [ ] Operator notes preserve the exploratory-only status.

## Recommended next phase

- The next phase should define local-only validation tests for these static schemas.
- It should still avoid writing artifacts.
- It should not run ingestion or rerun research.
- It should remain exploratory and non-tradeable.

## Operator checklist

- [ ] Run git status -sb before the phase.
- [ ] Confirm the repo path is /workspaces/joint_research in Codespaces.
- [ ] Confirm no accidental poetry.lock, __pycache__, egg-info, or environment files are staged.
- [ ] Confirm no thresholds are changed.
- [ ] Confirm no candidates are promoted.
- [ ] Confirm no ingestion, execution, adapters, manifests, orders, or database mutation are approved.
- [ ] Confirm this phase defines schemas only and does not create artifacts.

This static coverage diagnostic artifact specification defines future diagnostic artifact shapes only; it does not make wallet-flow tradeable.
