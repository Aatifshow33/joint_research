from __future__ import annotations

from pathlib import Path

CHECKLIST_PATH = Path("docs/wallet_flow_research_diagnostics_frozen_index_checklist.md")


def test_wallet_flow_research_diagnostics_frozen_index_checklist_content() -> None:
    assert CHECKLIST_PATH.exists(), "frozen-index checklist file must exist"

    text = CHECKLIST_PATH.read_text(encoding="utf-8")
    lower_text = text.lower()

    assert "# Wallet-flow Research Diagnostics Frozen-Index Checklist" in text
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in text
    assert "/workspaces/joint_research" in text
    assert "/Users/muhammadaatif/joint_research" in text
    assert "60242da phase 4.43: add wallet-flow research diagnostic package index" in text

    assert "This frozen-index checklist does not promote wallet-flow candidates." in text
    assert "This frozen-index checklist does not change thresholds." in text
    assert "This frozen-index checklist does not approve ingestion, execution, live trading, adapters, manifests, orders, or database mutation." in text

    assert "## Why this checklist comes next" in text
    assert "## Latest known outcome snapshot" in text
    assert "## Known rejection bottlenecks" in text
    assert "## Frozen-index checklist" in text
    assert "## Freeze decision rules" in text
    assert "## Operator verification commands" in text
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
    assert "These bottlenecks remain unresolved." in text
    assert "This checklist does not resolve research evidence." in text
    assert "No checklist item can override failed evidence." in text

    checklist_rows = [
        "| Diagnostic package index exists | wallet_flow_research_diagnostic_package_index.md is present | PASS only if present. |",
        "| Research effectiveness audit exists | wallet_flow_research_effectiveness_audit.md is present | PASS only if present. |",
        "| Master research summary exists | wallet_flow_master_research_summary.md is present | PASS only if present. |",
        "| Final freeze checklist exists | wallet_flow_final_freeze_checklist.md is present | PASS only if present. |",
        "| Coverage quality diagnostic exists | wallet_flow_coverage_quality_diagnostics.md is present | PASS only if present. |",
        "| Rejection bottleneck breakdown exists | wallet_flow_rejection_bottleneck_breakdown.md is present | PASS only if present. |",
        "| Standalone versus supporting feature doc exists | wallet_flow_standalone_vs_supporting_feature.md is present | PASS only if present. |",
        "| Minimum evidence definition exists | wallet_flow_minimum_evidence_definition.md is present | PASS only if present. |",
        "| Non-tradeability is explicit | Every diagnostic doc must keep wallet-flow exploratory only | PASS only if explicit. |",
        "| No promotion language exists | No diagnostic doc may promote candidates | PASS only if absent. |",
        "| No threshold-change language exists | No diagnostic doc may change thresholds | PASS only if absent. |",
        "| No execution approval exists | No diagnostic doc may approve ingestion, execution, adapters, manifests, orders, or database mutation | PASS only if absent. |",
    ]
    for item in checklist_rows:
        assert item in text

    decision_rules = [
        "If any required diagnostic document is missing, do not freeze the diagnostic index.",
        "If any diagnostic document lacks non-tradeability language, do not freeze the diagnostic index.",
        "If any diagnostic document promotes candidates, do not freeze the diagnostic index.",
        "If any diagnostic document changes thresholds, do not freeze the diagnostic index.",
        "If any diagnostic document approves execution or database mutation, do not freeze the diagnostic index.",
        "If all checklist items pass, the diagnostic package can be treated as organized for navigation only.",
        "A frozen index does not mean wallet-flow is useful, approved, or tradeable.",
    ]
    for item in decision_rules:
        assert item in text

    assert "cd /workspaces/joint_research" in text
    assert "git status -sb" in text
    assert "python3 -m pytest \\" in text
    assert r'find . -maxdepth 2 \( -name "poetry.lock" -o -name "*.egg-info" -o -name "__pycache__" \) -print' in text

    assert "The next phase should be a wallet-flow post-freeze research closeout note." in text
    assert "The closeout note should summarize the diagnostic package and state that the next real research step is data/coverage work, not more approval docs." in text
    assert "All outputs must remain exploratory and non-tradeable." in text

    operator_checks = [
        "Run git status -sb before the phase.",
        "Confirm the repo path is /workspaces/joint_research in Codespaces.",
        "Confirm no accidental poetry.lock, __pycache__, egg-info, or environment files are staged.",
        "Confirm no thresholds are changed.",
        "Confirm no candidates are promoted.",
        "Confirm no ingestion, execution, adapters, manifests, orders, or database mutation are approved.",
    ]
    for item in operator_checks:
        assert item in text

    assert (
        "This frozen-index checklist verifies diagnostic-package organization only; it does not make wallet-flow tradeable."
        in text
    )

    forbidden_phrases = [
        "live trading is enabled",
        "wallet-flow is tradeable",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in lower_text
