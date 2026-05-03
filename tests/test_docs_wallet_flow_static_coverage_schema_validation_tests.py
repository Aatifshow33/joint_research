import pytest


def test_wallet_flow_static_coverage_schema_validation_tests_doc_exists():
    """Verify the static coverage schema validation tests doc exists."""
    import pathlib
    doc_path = pathlib.Path("/workspaces/joint_research/docs/wallet_flow_static_coverage_schema_validation_tests.md")
    assert doc_path.exists(), "Doc file does not exist"
    assert doc_path.is_file(), "Doc path is not a file"


def test_doc_contains_title():
    """Verify doc contains the correct title."""
    with open("/workspaces/joint_research/docs/wallet_flow_static_coverage_schema_validation_tests.md") as f:
        text = f.read()
    assert "# Wallet-flow Static Coverage Schema Validation Tests" in text


def test_doc_contains_exploratory_only_status():
    """Verify doc declares EXPLORATORY ONLY - NOT TRADEABLE."""
    with open("/workspaces/joint_research/docs/wallet_flow_static_coverage_schema_validation_tests.md") as f:
        text = f.read()
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in text


def test_doc_contains_codespaces_repo_path():
    """Verify doc contains Codespaces repo path."""
    with open("/workspaces/joint_research/docs/wallet_flow_static_coverage_schema_validation_tests.md") as f:
        text = f.read()
    assert "/workspaces/joint_research" in text


def test_doc_contains_mac_repo_path():
    """Verify doc contains Mac repo path reference."""
    with open("/workspaces/joint_research/docs/wallet_flow_static_coverage_schema_validation_tests.md") as f:
        text = f.read()
    assert "/Users/muhammadaatif/joint_research" in text


def test_doc_contains_checkpoint():
    """Verify doc contains the phase 4.47 checkpoint."""
    with open("/workspaces/joint_research/docs/wallet_flow_static_coverage_schema_validation_tests.md") as f:
        text = f.read()
    assert "67a81cf" in text
    assert "phase 4.47" in text


def test_doc_contains_no_promotion_statement():
    """Verify doc states does not promote candidates."""
    with open("/workspaces/joint_research/docs/wallet_flow_static_coverage_schema_validation_tests.md") as f:
        text = f.read()
    assert "does not promote wallet-flow candidates" in text


def test_doc_contains_no_threshold_change_statement():
    """Verify doc states does not change thresholds."""
    with open("/workspaces/joint_research/docs/wallet_flow_static_coverage_schema_validation_tests.md") as f:
        text = f.read()
    assert "does not change thresholds" in text


def test_doc_contains_no_approval_statement():
    """Verify doc states no approval for ingestion, execution, etc."""
    with open("/workspaces/joint_research/docs/wallet_flow_static_coverage_schema_validation_tests.md") as f:
        text = f.read()
    assert "does not approve ingestion, execution, live trading, adapters, manifests, orders, or database mutation" in text


def test_doc_contains_why_section():
    """Verify doc contains 'Why this phase comes after the artifact specification' section."""
    with open("/workspaces/joint_research/docs/wallet_flow_static_coverage_schema_validation_tests.md") as f:
        text = f.read()
    assert "## Why this phase comes after the artifact specification" in text
    assert "Phase 4.47 defined expected static diagnostic artifact files and schemas" in text
    assert "This phase defines how those schemas should be validated" in text
    assert "Validation expectations should be local-only and deterministic" in text
    assert "The latest known result still had zero candidates beyond rejected" in text
    assert "This phase does not create artifacts, write files, run ingestion, or rerun research" in text


def test_doc_contains_latest_known_outcome_section():
    """Verify doc contains latest known outcome snapshot section."""
    with open("/workspaces/joint_research/docs/wallet_flow_static_coverage_schema_validation_tests.md") as f:
        text = f.read()
    assert "## Latest known outcome snapshot" in text
    assert "SIMULATION_READY" in text
    assert "WATCHLIST" in text
    assert "WEAK" in text
    assert "REJECTED" in text
    assert "| 0 |" in text  # All counters are 0 except REJECTED
    assert "| 1049 |" in text  # REJECTED count


def test_doc_contains_rejection_bottlenecks_section():
    """Verify doc contains known rejection bottlenecks section."""
    with open("/workspaces/joint_research/docs/wallet_flow_static_coverage_schema_validation_tests.md") as f:
        text = f.read()
    assert "## Known rejection bottlenecks" in text
    assert "improvement_below_cost_buffer" in text
    assert "5426" in text
    assert "insufficient_unique_flow_hours" in text
    assert "4993" in text
    assert "weak_win_rate" in text
    assert "4904" in text
    assert "Schema validation cannot resolve these bottlenecks" in text
    assert "Validation only makes future diagnostic artifacts reviewable and safe" in text


def test_doc_contains_static_schema_validation_inventory():
    """Verify doc contains static schema validation inventory table with all rows."""
    with open("/workspaces/joint_research/docs/wallet_flow_static_coverage_schema_validation_tests.md") as f:
        text = f.read()
    assert "## Static schema validation inventory" in text
    
    # Check all 10 artifact rows
    artifacts = [
        "market_coverage.csv",
        "wallet_class_coverage.csv",
        "horizon_coverage.csv",
        "missingness_summary.csv",
        "concentration_diagnostics.csv",
        "recency_distribution.csv",
        "cost_buffer_diagnostics.csv",
        "win_rate_by_coverage.csv",
        "rerun_readiness_checklist.md",
        "operator_notes.md",
    ]
    for artifact in artifacts:
        assert artifact in text, f"Artifact {artifact} not in table"
    
    # Check specific validation targets and boundaries
    assert "Header and stable columns" in text
    assert "Diagnostic only" in text
    assert "No wallet promotion" in text
    assert "No rerun approval" in text
    assert "No ingestion approval" in text
    assert "No live execution" in text
    assert "No tradeability claim" in text
    assert "No threshold loosening" in text
    assert "No candidate promotion" in text
    assert "No automatic rerun" in text
    assert "Exploratory only" in text


def test_doc_contains_local_only_validation_rules():
    """Verify doc contains local-only validation rules section."""
    with open("/workspaces/joint_research/docs/wallet_flow_static_coverage_schema_validation_tests.md") as f:
        text = f.read()
    assert "## Local-only validation rules" in text
    
    # Check all 12 rules
    assert "Validation must run without network access" in text
    assert "Validation must not call ingestion code" in text
    assert "Validation must not create or modify databases" in text
    assert "Validation must not execute adapters or manifests" in text
    assert "Validation must not place orders" in text
    assert "Validation must not require secrets or environment variables" in text
    assert "Validation must only inspect static expected schema definitions or local fixture content" in text
    assert "Validation must be deterministic for the same local input" in text
    assert "Validation must fail if required CSV headers are missing" in text
    assert "Validation must fail if markdown diagnostic artifacts omit" in text
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in text
    assert "Validation must fail if markdown diagnostic artifacts claim tradeability or active live trading status" in text
    assert "Validation must fail if artifacts include obvious secret field names" in text
    assert "api_key" in text
    assert "secret_key" in text
    assert "auth_token" in text
    assert "private_key" in text
    assert "password" in text


def test_doc_contains_future_fixture_expectations():
    """Verify doc contains future fixture expectations section."""
    with open("/workspaces/joint_research/docs/wallet_flow_static_coverage_schema_validation_tests.md") as f:
        text = f.read()
    assert "## Future fixture expectations" in text
    
    # Check all fixture expectations
    assert "Fixtures should be committed under tests/fixtures only if needed" in text
    assert "Fixtures must contain synthetic or sanitized rows only" in text
    assert "Fixtures must not contain real secrets, API keys, auth tokens, private keys, or environment values" in text
    assert "Fixtures must not require network access" in text
    assert "Fixtures must not imply wallet-flow is tradeable" in text
    assert "Fixtures must not include real order placement data" in text
    assert "Fixtures must not include database mutation instructions" in text
    assert "Fixtures should cover valid headers, missing headers, unsafe markdown claims, and secret-like field names" in text


def test_doc_contains_non_goals_section():
    """Verify doc contains non-goals section."""
    with open("/workspaces/joint_research/docs/wallet_flow_static_coverage_schema_validation_tests.md") as f:
        text = f.read()
    assert "## Non-goals" in text
    
    # Check all non-goals
    assert "Do not implement artifact writers in this phase" in text
    assert "Do not create coverage diagnostic artifacts in this phase" in text
    assert "Do not add CLI commands in this phase" in text
    assert "Do not run wallet-flow ingestion in this phase" in text
    assert "Do not rerun wallet-flow research in this phase" in text
    assert "Do not change scoring, thresholds, or candidate classification" in text
    assert "Do not promote any wallet, market, or candidate" in text
    assert "Do not connect adapters or manifests" in text
    assert "Do not approve live trading or orders" in text
    assert "Do not mutate databases" in text


def test_doc_contains_recommended_next_phase():
    """Verify doc contains recommended next phase section."""
    with open("/workspaces/joint_research/docs/wallet_flow_static_coverage_schema_validation_tests.md") as f:
        text = f.read()
    assert "## Recommended next phase" in text
    assert "The next phase may add a local-only schema contract module or test helper if needed" in text
    assert "It should not write diagnostic artifacts yet" in text
    assert "It should not run ingestion or rerun research" in text
    assert "It should remain exploratory and non-tradeable" in text


def test_doc_contains_operator_checklist():
    """Verify doc contains operator checklist section."""
    with open("/workspaces/joint_research/docs/wallet_flow_static_coverage_schema_validation_tests.md") as f:
        text = f.read()
    assert "## Operator checklist" in text
    
    # Check all 7 checklist items
    assert "Run `git status -sb` before the phase" in text
    assert "Confirm the repo path is `/workspaces/joint_research` in Codespaces" in text
    assert "Confirm no accidental `poetry.lock`, `__pycache__`, `*.egg-info`, or environment files are staged" in text
    assert "Confirm no thresholds are changed" in text
    assert "Confirm no candidates are promoted" in text
    assert "Confirm no ingestion, execution, adapters, manifests, orders, or database mutation are approved" in text
    assert "Confirm this phase defines validation expectations only and does not create artifacts" in text


def test_doc_contains_final_safety_statement():
    """Verify doc contains final safety statement."""
    with open("/workspaces/joint_research/docs/wallet_flow_static_coverage_schema_validation_tests.md") as f:
        text = f.read()
    assert "This static coverage schema validation test plan defines local-only validation expectations for future diagnostic schemas; it does not make wallet-flow tradeable" in text


def test_doc_does_not_claim_live_trading_enabled():
    """Verify doc does not claim live trading is enabled."""
    with open("/workspaces/joint_research/docs/wallet_flow_static_coverage_schema_validation_tests.md") as f:
        text = f.read()
    assert "live trading is enabled" not in text


def test_doc_does_not_claim_wallet_flow_tradeable():
    """Verify doc does not claim wallet-flow is tradeable (except in context of what to prevent)."""
    with open("/workspaces/joint_research/docs/wallet_flow_static_coverage_schema_validation_tests.md") as f:
        text = f.read()
    # Should have "does not make wallet-flow tradeable" but not standalone "wallet-flow is tradeable" without negation context
    # The phrase appears in "does not make wallet-flow tradeable" and "Fixtures must not imply wallet-flow is tradeable"
    # which are both in negative/restriction context, so these are OK.
    lines = text.split('\n')
    for line in lines:
        if 'wallet-flow is tradeable' in line:
            # Must be in one of the approved contexts
            assert 'does not make wallet-flow tradeable' in line or 'must not imply wallet-flow is tradeable' in line or 'claim' in line.lower() or 'validation must fail if' in line.lower()
