from __future__ import annotations

from pathlib import Path

INDEX_PATH = Path("docs/wallet_flow_research_diagnostic_package_index.md")


def test_wallet_flow_research_diagnostic_package_index_content() -> None:
    assert INDEX_PATH.exists(), "research diagnostic package index file must exist"

    text = INDEX_PATH.read_text(encoding="utf-8")
    lower_text = text.lower()

    assert "# Wallet-flow Research Diagnostic Package Index" in text
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in text
    assert "/workspaces/joint_research" in text
    assert "/Users/muhammadaatif/joint_research" in text
    assert "aab25c3 phase 4.42: add wallet-flow minimum evidence definition" in text

    assert "This research diagnostic package index does not promote wallet-flow candidates." in text
    assert "This research diagnostic package index does not change thresholds." in text
    assert "This research diagnostic package index does not approve ingestion, execution, live trading, adapters, manifests, orders, or database mutation." in text

    assert "## Why this index comes next" in text
    assert "## Latest known outcome snapshot" in text
    assert "## Known rejection bottlenecks" in text
    assert "## Diagnostic package inventory" in text
    assert "## Recommended read order" in text
    assert "## Operator use rules" in text
    assert "## Package completeness check" in text
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
    assert "This diagnostic index does not resolve the bottlenecks by itself." in text
    assert "No bottleneck can be bypassed by documentation alone." in text

    inventory_rows = [
        "| wallet_flow_research_effectiveness_audit.md | Assesses whether wallet-flow research is useful after the disabled-chain freeze | Establishes that usefulness is still unproven. |",
        "| wallet_flow_master_research_summary.md | Consolidates disabled-chain status, outcome snapshot, bottlenecks, and priorities | Provides the master context for later diagnostics. |",
        "| wallet_flow_final_freeze_checklist.md | Defines whether the disabled-chain documentation package can stop expanding | Separates safety/package freeze from research usefulness. |",
        "| wallet_flow_coverage_quality_diagnostics.md | Defines how to inspect coverage quality before trusting research results | Identifies coverage as a required diagnostic layer. |",
        "| wallet_flow_rejection_bottleneck_breakdown.md | Defines how to break down why candidates remain rejected | Focuses review on the actual rejection causes. |",
        "| wallet_flow_standalone_vs_supporting_feature.md | Defines how to compare wallet-flow alone versus as a feature for stronger signals | Prevents premature standalone promotion. |",
        "| wallet_flow_minimum_evidence_definition.md | Defines minimum evidence required before any future promotion review | Creates a gate before any promotion-review RFC. |",
        "| wallet_flow_research_diagnostic_package_index.md | Organizes the diagnostic package | Provides operator navigation only. |",
    ]
    for item in inventory_rows:
        assert item in text

    read_order = [
        "1. wallet_flow_master_research_summary.md",
        "2. wallet_flow_research_effectiveness_audit.md",
        "3. wallet_flow_final_freeze_checklist.md",
        "4. wallet_flow_coverage_quality_diagnostics.md",
        "5. wallet_flow_rejection_bottleneck_breakdown.md",
        "6. wallet_flow_standalone_vs_supporting_feature.md",
        "7. wallet_flow_minimum_evidence_definition.md",
        "8. wallet_flow_research_diagnostic_package_index.md",
    ]
    for item in read_order:
        assert item in text

    use_rules = [
        "Use this index to navigate diagnostic docs.",
        "Do not use this index as approval to promote candidates.",
        "Do not use this index as approval to loosen thresholds.",
        "Do not use this index as approval to run ingestion.",
        "Do not use this index as approval to execute adapters or manifests.",
        "Do not use this index as approval for orders, database mutation, or live trading.",
        "If diagnostics conflict, use the most conservative interpretation.",
        "If evidence is missing, keep wallet-flow rejected.",
    ]
    for item in use_rules:
        assert item in text

    completeness_rows = [
        "| Disabled-chain freeze docs exist | Required before research diagnostics are treated as organized. |",
        "| Research usefulness audit exists | Required before claiming the diagnostic package is complete. |",
        "| Coverage quality diagnostic exists | Required before interpreting wallet-flow evidence. |",
        "| Rejection bottleneck breakdown exists | Required before discussing future improvements. |",
        "| Standalone-versus-supporting-feature comparison exists | Required before discussing wallet-flow as context. |",
        "| Minimum evidence definition exists | Required before any future promotion-review RFC. |",
        "| No candidate promotion is included | Required. |",
        "| No threshold change is included | Required. |",
        "| No execution approval is included | Required. |",
    ]
    for item in completeness_rows:
        assert item in text

    assert "The next phase should be a wallet-flow research diagnostics frozen-index checklist." in text
    assert "The checklist should verify the diagnostic package is organized and non-tradeable." in text
    assert "All outputs must remain exploratory and non-tradeable." in text

    operator_checklist = [
        "Run git status -sb before the phase.",
        "Confirm the repo path is /workspaces/joint_research in Codespaces.",
        "Confirm no accidental poetry.lock, __pycache__, egg-info, or environment files are staged.",
        "Confirm no thresholds are changed.",
        "Confirm no candidates are promoted.",
        "Confirm no ingestion, execution, adapters, manifests, orders, or database mutation are approved.",
    ]
    for item in operator_checklist:
        assert item in text

    assert (
        "This research diagnostic package index organizes wallet-flow diagnostic documents; it does not make wallet-flow tradeable."
        in text
    )

    forbidden_phrases = [
        "live trading is enabled",
        "wallet-flow is tradeable",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in lower_text
