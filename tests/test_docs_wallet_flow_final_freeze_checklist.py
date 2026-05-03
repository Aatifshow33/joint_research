from __future__ import annotations

from pathlib import Path

CHECKLIST_PATH = Path("docs/wallet_flow_final_freeze_checklist.md")


def test_wallet_flow_final_freeze_checklist_content() -> None:
    assert CHECKLIST_PATH.exists(), "final freeze checklist file must exist"

    text = CHECKLIST_PATH.read_text(encoding="utf-8")
    lower_text = text.lower()

    assert "# Wallet-flow Final Freeze Checklist" in text
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in text
    assert "/workspaces/joint_research" in text
    assert "/Users/muhammadaatif/joint_research" in text
    assert "865efc0 phase 4.37: add wallet-flow master research summary" in text

    assert "This freeze checklist does not promote wallet-flow candidates." in text
    assert "This freeze checklist does not change thresholds." in text
    assert "This freeze checklist does not approve ingestion, execution, live trading, adapters, manifests, orders, or database mutation." in text

    assert "## Freeze recommendation" in text
    assert "## Package inventory" in text
    assert "## Final freeze checklist" in text
    assert "## Freeze / do-not-freeze decision table" in text
    assert "## After freeze, next allowed work" in text
    assert "## Freeze boundaries" in text
    assert "## Operator final check" in text

    package_paths = [
        "docs/README.md",
        "docs/wallet_flow_disabled_chain_docs_manifest.md",
        "docs/wallet_flow_disabled_chain_index.md",
        "docs/wallet_flow_disabled_chain_operator_readme.md",
        "docs/wallet_flow_disabled_chain_release_notes.md",
        "docs/wallet_flow_disabled_chain_audit_pack.md",
        "docs/wallet_flow_disabled_chain_codespaces_note.md",
        "docs/wallet_flow_research_effectiveness_audit.md",
        "docs/wallet_flow_master_research_summary.md",
    ]
    for path in package_paths:
        assert path in text

    checklist_items = [
        "Confirm docs/README.md points operators to the disabled-chain docs package.",
        "Confirm docs/wallet_flow_disabled_chain_docs_manifest.md lists the disabled-chain docs.",
        "Confirm docs/wallet_flow_master_research_summary.md is the single starting point for wallet-flow research status.",
        "Confirm docs/wallet_flow_research_effectiveness_audit.md explains research usefulness is not proven yet.",
        "Confirm the latest known outcome still shows zero candidates beyond rejected.",
        "Confirm bottlenecks are documented as cost-buffer failure, insufficient unique flow hours, and weak win rate.",
        "Confirm wallet-flow candidate promotion remains stopped.",
        "Confirm threshold loosening remains stopped.",
        "Confirm ingestion, execution, adapters, manifests, orders, and database mutation remain unapproved.",
        "Confirm future live execution work is separated into a future RFC before any implementation.",
    ]
    for item in checklist_items:
        assert item in text

    decision_table_headers = [
        "| Check area | Freeze if | Do not freeze if |",
        "| Documentation map | All operator docs are discoverable from README, manifest, or master summary.",
        "| Safety boundary | All docs say exploratory only and not tradeable.",
        "| Research status | Master summary clearly says usefulness is unproven and candidate survival is zero beyond rejected.",
        "| Bottlenecks | Cost-buffer, unique-flow-hours, and win-rate failures are documented.",
        "| Future roadmap | Future live execution is separated into an RFC.",
        "| Repo hygiene | Operators are reminded to check status and avoid accidental files.",
    ]
    for item in decision_table_headers:
        assert item in text

    next_allowed_items = [
        "1. Coverage quality metrics by market, wallet class, and horizon.",
        "2. Rejection-bottleneck breakdowns by market, wallet class, and horizon.",
        "3. Least-bad rejected candidate diagnostics for review only.",
        "4. Standalone versus supporting-feature signal comparison.",
        "5. Minimum evidence definition for any future promotion review.",
        "6. Separate future-execution RFC only if policy changes.",
    ]
    for item in next_allowed_items:
        assert item in text

    boundaries = [
        "Freeze does not mean wallet-flow is useful.",
        "Freeze does not mean wallet-flow becomes tradeable.",
        "Freeze does not mean live execution is allowed.",
        "Freeze does not mean thresholds can be loosened.",
        "Freeze does not mean candidates can be promoted.",
        "Freeze only means the current disabled-chain and research-summary documentation package is complete enough to stop expanding.",
    ]
    for item in boundaries:
        assert item in text

    operator_checks = [
        "Run git status -sb before the final freeze commit.",
        "Confirm the repo path is /workspaces/joint_research in Codespaces.",
        "Confirm no accidental poetry.lock, __pycache__, egg-info, or environment files are staged.",
        "Confirm validation tests pass.",
        "Confirm only docs/wallet_flow_final_freeze_checklist.md and tests/test_docs_wallet_flow_final_freeze_checklist.py are staged for this phase.",
    ]
    for item in operator_checks:
        assert item in text

    assert (
        "This final freeze checklist helps decide whether to stop expanding the wallet-flow disabled documentation package; it does not make wallet-flow tradeable."
        in text
    )

    forbidden_phrases = [
        "live trading is enabled",
        "wallet-flow is tradeable",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in lower_text
