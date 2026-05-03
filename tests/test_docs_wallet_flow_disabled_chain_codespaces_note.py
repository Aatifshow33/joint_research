from __future__ import annotations

from pathlib import Path


NOTE_PATH = Path("docs/wallet_flow_disabled_chain_codespaces_note.md")


def test_wallet_flow_disabled_chain_codespaces_note_content() -> None:
    assert NOTE_PATH.exists(), "Codespaces operator note file must exist"

    text = NOTE_PATH.read_text()
    lower_text = text.lower()

    assert "# Wallet-flow Disabled Chain Codespaces Operator Note" in text
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in text
    assert "/workspaces/joint_research" in text
    assert "/Users/muhammadaatif/joint_research" in text
    assert "git status -sb" in text
    assert "poetry.lock" in text
    assert "c8b0865 phase 4.32: add wallet-flow disabled chain audit pack" in text

    required_docs = [
        "docs/wallet_flow_disabled_chain_operator_readme.md",
        "docs/wallet_flow_disabled_chain_release_notes.md",
        "docs/wallet_flow_disabled_chain_index.md",
        "docs/wallet_flow_disabled_chain_audit_pack.md",
    ]
    for doc in required_docs:
        assert doc in text

    required_statuses = [
        "adapter_status=DISABLED_BY_POLICY",
        "run_status=DISABLED_BY_POLICY_CONFIRMED",
        "chain_status=DISABLED_CHAIN_CONFIRMED",
        "guard_status=POLICY_GUARD_PASS",
    ]
    for status in required_statuses:
        assert status in text

    assert (
        "POLICY_GUARD_PASS means disabled-policy validation only, not approval to trade." in text
        or "`POLICY_GUARD_PASS` means disabled-policy validation only, not approval to trade." in text
    )

    do_not_do_lines = [
        "Do not run ingestion.",
        "Do not enable adapters.",
        "Do not execute manifests.",
        "Do not place orders.",
        "Do not change thresholds.",
        "Do not promote candidates.",
        "Do not commit accidental environment files.",
    ]
    for line in do_not_do_lines:
        assert line in text

    assert (
        "This Codespaces note helps operators keep the disabled wallet-flow chain safe in Codespaces; "
        "it does not make wallet-flow tradeable."
    ) in text

    forbidden_phrases = [
        "live trading is enabled",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in lower_text
