from __future__ import annotations

from pathlib import Path


MANIFEST_PATH = Path("docs/wallet_flow_disabled_chain_docs_manifest.md")


def test_wallet_flow_disabled_chain_docs_manifest_content() -> None:
    assert MANIFEST_PATH.exists(), "manifest file must exist"

    text = MANIFEST_PATH.read_text()
    lower_text = text.lower()

    # Title and status
    assert "# Wallet-flow Disabled Chain Docs Manifest" in text
    assert "Status: EXPLORATORY ONLY - NOT TRADEABLE" in text

    # Repo paths
    assert "/workspaces/joint_research" in text
    assert "/Users/muhammadaatif/joint_research" in text

    # Checkpoint
    assert "eeea51e phase 4.33: add wallet-flow Codespaces operator note" in text

    # All five manifest doc paths
    required_docs = [
        "docs/wallet_flow_disabled_chain_operator_readme.md",
        "docs/wallet_flow_disabled_chain_release_notes.md",
        "docs/wallet_flow_disabled_chain_index.md",
        "docs/wallet_flow_disabled_chain_audit_pack.md",
        "docs/wallet_flow_disabled_chain_codespaces_note.md",
        "docs/wallet_flow_schema_contract_closeout_note.md",
    ]
    for doc in required_docs:
        assert doc in text

    # Required read order section
    assert "## Required read order" in text
    assert "1. docs/wallet_flow_disabled_chain_index.md" in text
    assert "2. docs/wallet_flow_disabled_chain_operator_readme.md" in text
    assert "3. docs/wallet_flow_disabled_chain_release_notes.md" in text
    assert "4. docs/wallet_flow_disabled_chain_audit_pack.md" in text
    assert "5. docs/wallet_flow_disabled_chain_codespaces_note.md" in text
    assert "6. docs/wallet_flow_schema_contract_closeout_note.md" in text

    # Phase 4.52 closeout pointer chain coverage
    closeout_required_strings = [
        "Phase 4.52",
        "schema contract closeout note",
        "Phase 4.49",
        "Phase 4.50",
        "Phase 4.51",
        "src/joint_research/wallet_flow_coverage_schema_contract.py",
        "CoverageArtifactSchema",
        "COVERAGE_ARTIFACT_SCHEMAS",
        "EXPLORATORY ONLY - NOT TRADEABLE",
    ]
    for required in closeout_required_strings:
        if required == "schema contract closeout note":
            assert required in lower_text
        else:
            assert required in text

    # Expected safe statuses
    required_statuses = [
        "adapter_status=DISABLED_BY_POLICY",
        "run_status=DISABLED_BY_POLICY_CONFIRMED",
        "chain_status=DISABLED_CHAIN_CONFIRMED",
        "guard_status=POLICY_GUARD_PASS",
    ]
    for status in required_statuses:
        assert status in text

    # POLICY_GUARD_PASS explanation
    assert (
        "`POLICY_GUARD_PASS` means disabled-policy validation only, not approval to trade." in text
    )

    # Manifest boundary lines (exact matches)
    manifest_boundaries = [
        "This manifest does not approve ingestion.",
        "This manifest does not approve execution.",
        "This manifest does not approve live trading.",
        "This manifest does not promote wallet-flow candidates.",
        "This manifest does not change thresholds.",
        "This manifest does not enable adapters.",
        "This manifest does not allow orders.",
    ]
    for boundary in manifest_boundaries:
        assert boundary in text

    # Additional non-executing and non-promotion boundaries
    non_execution_boundaries = [
        "does not write artifacts",
        "does not run ingestion",
        "does not rerun research",
        "does not execute manifests",
        "does not mutate databases",
        "does not promote candidates",
        "does not promote wallets",
        "does not approve paper trading",
        "does not approve live trading",
        "does not make wallet-flow tradeable",
    ]
    for boundary in non_execution_boundaries:
        assert boundary in lower_text

    # Codespaces hygiene lines
    codespaces_hygiene_lines = [
        "Run `git status -sb` before every phase.",
        "Stop on unexpected dirty files.",
        "Do not commit accidental `poetry.lock`.",
        "Do not commit accidental environment files.",
    ]
    for line in codespaces_hygiene_lines:
        assert line in text

    # Final safety statement
    assert (
        "This docs manifest helps operators navigate the disabled wallet-flow documentation chain; "
        "it does not make wallet-flow tradeable."
    ) in text

    # Forbidden phrases
    forbidden_phrases = [
        "live trading is enabled",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in lower_text
