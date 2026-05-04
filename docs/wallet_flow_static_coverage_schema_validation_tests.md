# Wallet-flow Static Coverage Schema Validation Tests

**Status:** EXPLORATORY ONLY - NOT TRADEABLE

**Codespaces repo path:**
```
/workspaces/joint_research
```

**Local Mac repo path reference:**
```
/Users/muhammadaatif/joint_research
```

**Current checkpoint:**
```
67a81cf phase 4.47: add wallet-flow static coverage diagnostic artifact spec
```

## Purpose

This phase defines local-only validation expectations for the static coverage diagnostic artifact schemas that were specified in Phase 4.47. Rather than implementing artifact writers or generating actual diagnostic outputs, this phase establishes how future tests should validate artifact headers, keys, and safety boundaries in a deterministic, local-only manner before any writer implementation runs. This ensures diagnostic artifacts remain reviewable, safe, and explicitly non-tradeable when they are eventually created.

This static coverage schema validation test plan does not promote wallet-flow candidates.

This static coverage schema validation test plan does not change thresholds.

This static coverage schema validation test plan does not approve ingestion, execution, live trading, adapters, manifests, orders, or database mutation.

## Why this phase comes after the artifact specification

- Phase 4.47 defined expected static diagnostic artifact files and schemas.
- This phase defines how those schemas should be validated before future writer implementation.
- Validation expectations should be local-only and deterministic.
- The latest known result still had zero candidates beyond rejected.
- This phase does not create artifacts, write files, run ingestion, or rerun research.

## Latest known outcome snapshot

At the time of Phase 4.47 specification:

| Candidate status | Count |
|---|---|
| SIMULATION_READY | 0 |
| WATCHLIST | 0 |
| WEAK | 0 |
| REJECTED | 1049 |

No wallet-flow candidate survived beyond REJECTED.

## Known rejection bottlenecks

The research identified three primary rejection bottlenecks preventing candidates from advancing:

| Bottleneck | Count |
|---|---|
| improvement_below_cost_buffer | 5426 |
| insufficient_unique_flow_hours | 4993 |
| weak_win_rate | 4904 |

Schema validation cannot resolve these bottlenecks directly. Validation only makes future diagnostic artifacts reviewable and safe by enforcing expected headers, required keys, and non-tradeable claims. Addressing rejection bottlenecks requires new candidate generation, rerun scope, or threshold changes—none of which occur in this phase.

## Static schema validation inventory

| Artifact | Validation target | Required schema checks | Boundary check |
|---|---|---|---|
| market_coverage.csv | Header and stable columns | market_id, market_slug, unique_flow_hours, total_flow_rows, coverage_bucket, first_flow_ts, last_flow_ts | Diagnostic only. |
| wallet_class_coverage.csv | Header and stable columns | wallet_class, wallet_count, unique_flow_hours, total_flow_rows, concentration_share, coverage_bucket | No wallet promotion. |
| horizon_coverage.csv | Header and stable columns | horizon_hours, market_count, unique_flow_hours, coverage_bucket, sparse_segment_count | No rerun approval. |
| missingness_summary.csv | Header and stable columns | field_name, null_count, null_rate, affected_markets, affected_wallet_classes | No ingestion approval. |
| concentration_diagnostics.csv | Header and stable columns | dimension, entity_id, entity_label, flow_share, rank, concentration_bucket | No live execution. |
| recency_distribution.csv | Header and stable columns | dimension, entity_id, first_flow_ts, last_flow_ts, age_hours, recency_bucket | No tradeability claim. |
| cost_buffer_diagnostics.csv | Header and stable columns | coverage_bucket, horizon_hours, candidate_count, improvement_below_cost_buffer_count, median_edge_after_cost | No threshold loosening. |
| win_rate_by_coverage.csv | Header and stable columns | coverage_bucket, horizon_hours, candidate_count, weak_win_rate_count, median_win_rate | No candidate promotion. |
| rerun_readiness_checklist.md | Required markdown keys/status | coverage_reviewed, bottlenecks_explained, missingness_reviewed, concentration_reviewed, rerun_scope_required | No automatic rerun. |
| operator_notes.md | Required markdown keys/status | summary, unresolved_gaps, recommended_next_step, safety_boundary | Exploratory only. |

## Local-only validation rules

Validation tests in future phases must follow these rules:

- Validation must run without network access.
- Validation must not call ingestion code.
- Validation must not create or modify databases.
- Validation must not execute adapters or manifests.
- Validation must not place orders.
- Validation must not require secrets or environment variables.
- Validation must only inspect static expected schema definitions or local fixture content.
- Validation must be deterministic for the same local input.
- Validation must fail if required CSV headers are missing.
- Validation must fail if markdown diagnostic artifacts omit `EXPLORATORY ONLY - NOT TRADEABLE`.
- Validation must fail if markdown diagnostic artifacts claim tradeability or active live trading status.
- Validation must fail if artifacts include obvious secret field names such as `api_key`, `secret_key`, `auth_token`, `private_key`, or `password`.

## Future fixture expectations

Future implementation tests may use tiny local fixtures only, with these constraints:

- Fixtures should be committed under tests/fixtures only if needed.
- Fixtures must contain synthetic or sanitized rows only.
- Fixtures must not contain real secrets, API keys, auth tokens, private keys, or environment values.
- Fixtures must not require network access.
- Fixtures must not imply wallet-flow is tradeable.
- Fixtures must not include real order placement data.
- Fixtures must not include database mutation instructions.
- Fixtures should cover valid headers, missing headers, unsafe markdown claims, and secret-like field names.

## Non-goals

This phase deliberately excludes:

- Do not implement artifact writers in this phase.
- Do not create coverage diagnostic artifacts in this phase.
- Do not add CLI commands in this phase.
- Do not run wallet-flow ingestion in this phase.
- Do not rerun wallet-flow research in this phase.
- Do not change scoring, thresholds, or candidate classification.
- Do not promote any wallet, market, or candidate.
- Do not connect adapters or manifests.
- Do not approve live trading or orders.
- Do not mutate databases.

## Recommended next phase

The next phase may add a local-only schema contract module or test helper if needed. It should not write diagnostic artifacts yet. It should not run ingestion or rerun research. It should remain exploratory and non-tradeable.

## Operator checklist

When applying this phase:

- [ ] Run `git status -sb` before the phase.
- [ ] Confirm the repo path is `/workspaces/joint_research` in Codespaces.
- [ ] Confirm no accidental `poetry.lock`, `__pycache__`, `*.egg-info`, or environment files are staged.
- [ ] Confirm no thresholds are changed.
- [ ] Confirm no candidates are promoted.
- [ ] Confirm no ingestion, execution, adapters, manifests, orders, or database mutation are approved.
- [ ] Confirm this phase defines validation expectations only and does not create artifacts.

## Phase 4.49 schema contract module

Phase 4.49 added the schema contract module at `src/joint_research/wallet_flow_coverage_schema_contract.py` with tests at `tests/test_wallet_flow_coverage_schema_contract.py`. This module provides static schema contracts only, including `CoverageArtifactSchema`, `COVERAGE_ARTIFACT_SCHEMAS`, `get_coverage_artifact_schema`, and `list_coverage_artifact_names`.

The module does not write artifacts. It does not generate diagnostic CSV or markdown files. It does not run ingestion. It does not rerun research. It does not approve execution. It does not promote candidates. It does not make wallet-flow tradeable.

**Status:** EXPLORATORY ONLY - NOT TRADEABLE

---

**This static coverage schema validation test plan defines local-only validation expectations for future diagnostic schemas; it does not make wallet-flow tradeable.**
