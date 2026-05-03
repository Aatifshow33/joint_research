from __future__ import annotations

from pathlib import Path


SUMMARY_PATH = Path("docs/wallet_flow_master_research_summary.md")


def test_wallet_flow_master_research_summary_content() -> None:
    assert SUMMARY_PATH.exists(), "summary file must exist"

    text = SUMMARY_PATH.read_text(encoding="utf-8")
    lower_text = text.lower()

    assert "# Wallet-flow Master Research Summary" in text
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in text
    assert "/workspaces/joint_research" in text
    assert "/Users/muhammadaatif/joint_research" in text
    assert "fad272f phase 4.36: add wallet-flow research effectiveness audit" in text

    assert "This summary does not promote wallet-flow candidates." in text
    assert "This summary does not change thresholds." in text
    assert "This summary does not approve ingestion, execution, live trading, adapters, manifests, orders, or database mutation." in text

    assert "## Executive summary" in text
    executive_points = [
        "The disabled-chain safety/governance package is near-finish.",
        "Wallet-flow research usefulness remains unproven.",
        "Current known results show zero candidates beyond rejected.",
        "The main research blockers are cost-buffer failure, insufficient unique flow hours, and weak win rate.",
        "Next useful work should focus on coverage quality and rejection diagnostics, not more disabled-chain documentation.",
    ]
    for point in executive_points:
        assert point in text

    assert "## Latest known outcome snapshot" in text
    for line in [
        "SIMULATION_READY: 0",
        "WATCHLIST: 0",
        "WEAK: 0",
        "REJECTED: 1049",
        "No wallet-flow candidate survived beyond REJECTED.",
    ]:
        assert line in text

    assert "## Rejection bottleneck snapshot" in text
    for line in [
        "improvement_below_cost_buffer: 5426",
        "insufficient_unique_flow_hours: 4993",
        "weak_win_rate: 4904",
    ]:
        assert line in text

    explanations = [
        "improvement_below_cost_buffer means the measured signal did not clear estimated cost/friction buffer.",
        "insufficient_unique_flow_hours means the signal did not have enough distinct flow observations to trust.",
        "weak_win_rate means forward outcomes were not consistently favorable.",
    ]
    for explanation in explanations:
        assert explanation in text

    assert "## Current package status" in text
    table_rows = [
        "| Safety/governance | Near-finish | Disabled-chain boundaries, approval layers, and policy guard are strong. |",
        "| Documentation | Near-finish | Docs root pointer, manifest, index, audit pack, release notes, operator README, and Codespaces note exist. |",
        "| Research signal quality | Not proven | Candidate survival remains zero beyond rejected. |",
        "| Data coverage | Weakness | Insufficient unique flow hours is a major blocker. |",
        "| Promotion readiness | Not ready | No promotion should happen until evidence improves. |",
        "| Live execution readiness | Intentionally blocked | Live execution remains out of scope and disabled by policy. |",
    ]
    for row in table_rows:
        assert row in text

    assert "## Documentation map" in text
    docs = [
        "docs/README.md",
        "docs/wallet_flow_disabled_chain_docs_manifest.md",
        "docs/wallet_flow_disabled_chain_index.md",
        "docs/wallet_flow_disabled_chain_operator_readme.md",
        "docs/wallet_flow_disabled_chain_release_notes.md",
        "docs/wallet_flow_disabled_chain_audit_pack.md",
        "docs/wallet_flow_disabled_chain_codespaces_note.md",
        "docs/wallet_flow_research_effectiveness_audit.md",
    ]
    for doc in docs:
        assert doc in text

    assert "## What to stop doing for now" in text
    stop_items = [
        "Stop adding more disabled-chain documentation unless it removes duplication or improves discoverability.",
        "Stop discussing threshold loosening before coverage and bottleneck evidence improves.",
        "Stop treating wallet-flow as promotion-ready.",
        "Stop mixing disabled-chain packaging work with future execution roadmap work.",
    ]
    for item in stop_items:
        assert item in text

    assert "## What to improve next" in text
    improve_items = [
        "1. Build coverage quality metrics by market, wallet class, and horizon.",
        "2. Build rejection-bottleneck breakdowns by market, wallet class, and horizon.",
        "3. Rank least-bad rejected candidates for diagnostic review only.",
        "4. Compare wallet-flow as a standalone signal versus a supporting feature.",
        "5. Define minimum evidence needed before any future promotion review.",
        "6. Keep all outputs exploratory and non-tradeable.",
    ]
    for item in improve_items:
        assert item in text

    assert "## Decision frame" in text
    decision_items = [
        "Freeze disabled-chain packaging after final consolidation unless new discoverability gaps appear.",
        "Continue wallet-flow research only if coverage diagnostics show a plausible path to better evidence.",
        "Keep future live execution in a separate RFC and separate project path.",
        "Treat current wallet-flow results as weak until candidate survival improves.",
    ]
    for item in decision_items:
        assert item in text

    assert "## Operator checklist" in text
    checklist = [
        "Run git status -sb before every phase.",
        "Confirm the repo path is /workspaces/joint_research in Codespaces.",
        "Confirm no accidental poetry.lock or environment files are staged.",
        "Confirm wallet-flow remains exploratory only.",
        "Confirm no thresholds are changed.",
        "Confirm no candidates are promoted.",
        "Confirm no ingestion, execution, adapters, manifests, orders, or database mutation are approved.",
    ]
    for item in checklist:
        assert item in text

    assert (
        "This master research summary helps operators understand wallet-flow research status and next priorities; "
        "it does not make wallet-flow tradeable."
    ) in text

    forbidden_phrases = [
        "live trading is enabled",
        "wallet-flow is tradeable",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in lower_text
