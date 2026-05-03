from __future__ import annotations

from pathlib import Path


README_PATH = Path("docs/README.md")


def test_docs_readme_wallet_flow_disabled_pointer_content() -> None:
    assert README_PATH.exists(), "docs/README.md must exist"

    text = README_PATH.read_text(encoding="utf-8")
    lower_text = text.lower()

    assert "# Wallet-flow Disabled Chain Documentation" in text
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in text
    assert "/workspaces/joint_research" in text
    assert "/Users/muhammadaatif/joint_research" in text
    assert "bf3373c phase 4.34: add wallet-flow disabled docs manifest" in text
    assert "docs/wallet_flow_disabled_chain_docs_manifest.md" in text

    required_docs = [
        "docs/wallet_flow_disabled_chain_index.md",
        "docs/wallet_flow_disabled_chain_operator_readme.md",
        "docs/wallet_flow_disabled_chain_release_notes.md",
        "docs/wallet_flow_disabled_chain_audit_pack.md",
        "docs/wallet_flow_disabled_chain_codespaces_note.md",
    ]
    for doc in required_docs:
        assert doc in text

    assert (
        "`POLICY_GUARD_PASS` means disabled-policy validation only, not approval to trade." in text
    )

    boundary_lines = [
        "This root pointer does not approve ingestion.",
        "This root pointer does not approve execution.",
        "This root pointer does not approve live trading.",
        "This root pointer does not promote wallet-flow candidates.",
        "This root pointer does not change thresholds.",
        "This root pointer does not enable adapters.",
        "This root pointer does not allow orders.",
    ]
    for line in boundary_lines:
        assert line in text

    hygiene_lines = [
        "Run `git status -sb` before every phase.",
        "Stop on unexpected dirty files.",
        "Do not commit accidental `poetry.lock`.",
        "Do not commit accidental environment files.",
    ]
    for line in hygiene_lines:
        assert line in text

    assert (
        "This root pointer helps operators find the disabled wallet-flow documentation chain; "
        "it does not make wallet-flow tradeable."
    ) in text

    assert "live trading is enabled" not in lower_text
