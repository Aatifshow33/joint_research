from __future__ import annotations

from pathlib import Path

CLOSEOUT_PATH = Path("docs/wallet_flow_post_freeze_research_closeout_note.md")


def test_wallet_flow_post_freeze_research_closeout_note_content() -> None:
    assert CLOSEOUT_PATH.exists(), "post-freeze research closeout note file must exist"

    text = CLOSEOUT_PATH.read_text(encoding="utf-8")
    lower_text = text.lower()

    assert "# Wallet-flow Post-Freeze Research Closeout Note" in text
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in text
    assert "/workspaces/joint_research" in text
    assert "/Users/muhammadaatif/joint_research" in text
    assert "66a32dc phase 4.44: add wallet-flow diagnostics frozen-index checklist" in text

    assert "This post-freeze research closeout note does not promote wallet-flow candidates." in text
    assert "This post-freeze research closeout note does not change thresholds." in text
    assert "This post-freeze research closeout note does not approve ingestion, execution, live trading, adapters, manifests, orders, or database mutation." in text

    assert "## Why this closeout comes now" in text
    assert "## Latest known outcome snapshot" in text
    assert "## Known rejection bottlenecks" in text
    assert "## Diagnostic package summary" in text
    assert "## Closeout decision" in text
    assert "## Next real research work" in text
    assert "## Stop rules after closeout" in text
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
    assert "Documentation cannot fix data coverage or weak edge." in text
    assert "The next work must inspect coverage and evidence quality before any promotion discussion." in text

    summary_rows = [
        "| wallet_flow_research_effectiveness_audit.md | Establishes that wallet-flow usefulness remains unproven. |",
        "| wallet_flow_master_research_summary.md | Provides the master context for disabled-chain safety status and research outcome. |",
        "| wallet_flow_final_freeze_checklist.md | Separates the disabled-chain documentation freeze from research usefulness. |",
        "| wallet_flow_coverage_quality_diagnostics.md | Defines how coverage must be inspected before trusting results. |",
        "| wallet_flow_rejection_bottleneck_breakdown.md | Defines how failed candidates should be analyzed. |",
        "| wallet_flow_standalone_vs_supporting_feature.md | Prevents premature standalone promotion by requiring comparison modes. |",
        "| wallet_flow_minimum_evidence_definition.md | Defines the evidence gate before any future promotion-review RFC. |",
        "| wallet_flow_research_diagnostic_package_index.md | Organizes the post-freeze diagnostic documents. |",
        "| wallet_flow_research_diagnostics_frozen_index_checklist.md | Verifies the index is organized and non-tradeable. |",
        "| wallet_flow_post_freeze_research_closeout_note.md | Closes the documentation expansion loop. |",
    ]
    for item in summary_rows:
        assert item in text

    decision_items = [
        "The wallet-flow documentation expansion loop should stop after this note.",
        "Wallet-flow remains exploratory only.",
        "Wallet-flow remains not tradeable.",
        "No candidates are promoted.",
        "No thresholds are changed.",
        "No ingestion, execution, live trading, adapters, manifests, orders, or database mutation are approved.",
        "Future work should focus on data coverage, rejection diagnostics, and rerunning research after coverage improves.",
    ]
    for item in decision_items:
        assert item in text

    next_work_rows = [
        "| Coverage audit | Identify why insufficient_unique_flow_hours remains high | Diagnostic only; no ingestion approval. |",
        "| Historical data plan | Define what coverage is missing before reruns | Plan only; no network execution. |",
        "| Wallet-class analysis | Inspect whether useful wallets/classes are too sparse | Research only; no promotion. |",
        "| Market-level analysis | Identify markets with usable versus unusable flow coverage | Research only; no threshold changes. |",
        "| Cost-buffer review | Understand why improvement_below_cost_buffer dominates | Diagnostic only; no threshold changes. |",
        "| Win-rate review | Understand why weak_win_rate remains high | Diagnostic only; no candidate promotion. |",
        "| Rerun readiness checklist | Define conditions before any future research rerun | Checklist only; no execution. |",
        "| Promotion-review RFC | Only if future evidence clears minimum-evidence requirements | Separate future scope and approval. |",
    ]
    for item in next_work_rows:
        assert item in text

    stop_rules = [
        "Do not add more approval docs unless a new research result exists.",
        "Do not start promotion review from the current evidence.",
        "Do not loosen thresholds to create candidates.",
        "Do not run real ingestion from this closeout.",
        "Do not execute adapters or manifests from this closeout.",
        "Do not place orders or mutate databases from this closeout.",
        "Do not call wallet-flow tradeable from this closeout.",
        "Move next to data/coverage diagnostics only.",
    ]
    for item in stop_rules:
        assert item in text

    assert "The next phase should leave the documentation loop." in text
    assert "The next phase should start a data/coverage diagnostic plan for wallet-flow." in text
    assert "The phase should remain exploratory and must not run ingestion." in text
    assert "The phase should inspect what is missing before any rerun." in text

    operator_checks = [
        "Run git status -sb before the phase.",
        "Confirm the repo path is /workspaces/joint_research in Codespaces.",
        "Confirm no accidental poetry.lock, __pycache__, egg-info, or environment files are staged.",
        "Confirm no thresholds are changed.",
        "Confirm no candidates are promoted.",
        "Confirm no ingestion, execution, adapters, manifests, orders, or database mutation are approved.",
        "Confirm the documentation loop stops after this closeout.",
    ]
    for item in operator_checks:
        assert item in text

    assert (
        "This post-freeze research closeout note closes the wallet-flow diagnostic documentation loop; it does not make wallet-flow tradeable."
        in text
    )

    forbidden_phrases = [
        "live trading is enabled",
        "wallet-flow is tradeable",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in lower_text
