from __future__ import annotations

from pathlib import Path

SPEC_PATH = Path("docs/wallet_flow_static_coverage_diagnostic_artifact_spec.md")


def test_wallet_flow_static_coverage_diagnostic_artifact_spec_content() -> None:
    assert SPEC_PATH.exists(), "static coverage diagnostic artifact spec file must exist"

    text = SPEC_PATH.read_text(encoding="utf-8")
    lower_text = text.lower()

    assert "# Wallet-flow Static Coverage Diagnostic Artifact Specification" in text
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in text
    assert "/workspaces/joint_research" in text
    assert "/Users/muhammadaatif/joint_research" in text
    assert "91f4bf0 phase 4.46: add wallet-flow coverage diagnostic plan" in text

    assert "This static coverage diagnostic artifact specification does not promote wallet-flow candidates." in text
    assert "This static coverage diagnostic artifact specification does not change thresholds." in text
    assert "This static coverage diagnostic artifact specification does not approve ingestion, execution, live trading, adapters, manifests, orders, or database mutation." in text

    assert "## Why this phase comes after the coverage diagnostic plan" in text
    assert "## Latest known outcome snapshot" in text
    assert "## Known rejection bottlenecks" in text
    assert "## Expected artifact directory" in text
    assert "## Static diagnostic artifact inventory" in text
    assert "## Required schema rules" in text
    assert "## Non-goals" in text
    assert "## Review checklist for future implementation" in text
    assert "## Recommended next phase" in text
    assert "## Operator checklist" in text

    assert "SIMULATION_READY: 0" in text
    assert "WATCHLIST: 0" in text
    assert "WEAK: 0" in text
    assert "REJECTED: 1049" in text
    assert "No wallet-flow candidate survived beyond REJECTED." in text

    assert "improvement_below_cost_buffer: 5426" in text
    assert "insufficient_unique_flow_hours: 4993" in text
    assert "weak_win_rate: 4904" in text
    assert "insufficient_unique_flow_hours motivates the coverage artifact set." in text
    assert "cost-buffer and win-rate failures must be interpreted by coverage segment." in text

    assert "artifacts/research/wallet_flow_coverage_diagnostics/" in text
    assert "This phase does not create that directory or write any artifacts." in text

    inventory_rows = [
        "| market_coverage.csv | CSV | Summarize market-level usable flow history | market_id, market_slug, unique_flow_hours, total_flow_rows, coverage_bucket, first_flow_ts, last_flow_ts | Diagnostic only. |",
        "| wallet_class_coverage.csv | CSV | Summarize wallet and wallet-class observation depth | wallet_class, wallet_count, unique_flow_hours, total_flow_rows, concentration_share, coverage_bucket | No wallet promotion. |",
        "| horizon_coverage.csv | CSV | Compare coverage across prediction horizons | horizon_hours, market_count, unique_flow_hours, coverage_bucket, sparse_segment_count | No rerun approval. |",
        "| missingness_summary.csv | CSV | Identify nulls, gaps, and empty flow buckets | field_name, null_count, null_rate, affected_markets, affected_wallet_classes | No ingestion approval. |",
        "| concentration_diagnostics.csv | CSV | Detect whether flow is dominated by few wallets or markets | dimension, entity_id, entity_label, flow_share, rank, concentration_bucket | No live execution. |",
        "| recency_distribution.csv | CSV | Measure stale versus recent flow coverage | dimension, entity_id, first_flow_ts, last_flow_ts, age_hours, recency_bucket | No tradeability claim. |",
        "| cost_buffer_diagnostics.csv | CSV | Review edge versus cost buffer by coverage segment | coverage_bucket, horizon_hours, candidate_count, improvement_below_cost_buffer_count, median_edge_after_cost | No threshold loosening. |",
        "| win_rate_by_coverage.csv | CSV | Review weak win rate by coverage segment | coverage_bucket, horizon_hours, candidate_count, weak_win_rate_count, median_win_rate | No candidate promotion. |",
        "| rerun_readiness_checklist.md | Markdown | Decide whether a future rerun would test new evidence | coverage_reviewed, bottlenecks_explained, missingness_reviewed, concentration_reviewed, rerun_scope_required | No automatic rerun. |",
        "| operator_notes.md | Markdown | Capture human-readable interpretation and caveats | summary, unresolved_gaps, recommended_next_step, safety_boundary | Exploratory only. |",
    ]
    for item in inventory_rows:
        assert item in text

    schema_rules = [
        "Every CSV artifact must include a header row.",
        "Every CSV artifact must be deterministic for the same input data.",
        "Every CSV artifact must sort rows by stable identifiers or explicit ranking fields.",
        "Timestamps must use UTC ISO-8601 text when present.",
        "Coverage buckets must be documented and must not change promotion thresholds.",
        "Counts must be integer-compatible.",
        "Rates and shares must be numeric and clearly named.",
        "Markdown artifacts must include a status line that says EXPLORATORY ONLY - NOT TRADEABLE.",
        "Markdown artifacts must state that they do not approve ingestion, execution, live trading, orders, or database mutation.",
        "Artifacts must not include secrets, API keys, auth tokens, private keys, or environment values.",
    ]
    for item in schema_rules:
        assert item in text

    non_goals = [
        "Do not implement artifact writers in this phase.",
        "Do not create artifacts in this phase.",
        "Do not run wallet-flow ingestion in this phase.",
        "Do not rerun wallet-flow research in this phase.",
        "Do not change scoring, thresholds, or candidate classification.",
        "Do not promote any wallet, market, or candidate.",
        "Do not connect adapters or manifests.",
        "Do not approve live trading or orders.",
        "Do not mutate databases.",
    ]
    for item in non_goals:
        assert item in text

    review_checklist = [
        "Artifact directory is created only by a later implementation phase.",
        "Writers are deterministic and local-only.",
        "No network calls are added.",
        "No ingestion is triggered.",
        "No research rerun is triggered automatically.",
        "No thresholds are changed.",
        "No candidates are promoted.",
        "No secrets or environment values are written.",
        "Validation tests cover required columns or keys.",
        "Operator notes preserve the exploratory-only status.",
    ]
    for item in review_checklist:
        assert item in text

    assert "The next phase should define local-only validation tests for these static schemas." in text
    assert "It should still avoid writing artifacts." in text
    assert "It should not run ingestion or rerun research." in text
    assert "It should remain exploratory and non-tradeable." in text

    operator_checks = [
        "Run git status -sb before the phase.",
        "Confirm the repo path is /workspaces/joint_research in Codespaces.",
        "Confirm no accidental poetry.lock, __pycache__, egg-info, or environment files are staged.",
        "Confirm no thresholds are changed.",
        "Confirm no candidates are promoted.",
        "Confirm no ingestion, execution, adapters, manifests, orders, or database mutation are approved.",
        "Confirm this phase defines schemas only and does not create artifacts.",
    ]
    for item in operator_checks:
        assert item in text

    assert (
        "This static coverage diagnostic artifact specification defines future diagnostic artifact shapes only; it does not make wallet-flow tradeable."
        in text
    )

    forbidden_phrases = [
        "live trading is enabled",
        "wallet-flow is tradeable",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in lower_text
