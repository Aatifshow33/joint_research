from __future__ import annotations

from pathlib import Path


RELEASE_NOTES_PATH = Path("docs/wallet_flow_disabled_chain_release_notes.md")


def test_wallet_flow_disabled_chain_release_notes_content() -> None:
    assert RELEASE_NOTES_PATH.exists(), "release notes file must exist"

    text = RELEASE_NOTES_PATH.read_text()
    lower_text = text.lower()

    assert "# Wallet-flow Disabled Chain Release Notes" in text
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in text
    assert "Phases 4.25 through 4.29" in text

    required_status_tokens = [
        "DISABLED_BY_POLICY",
        "DISABLED_BY_POLICY_CONFIRMED",
        "DISABLED_CHAIN_CONFIRMED",
        "POLICY_GUARD_PASS",
    ]
    for token in required_status_tokens:
        assert token in text

    required_policy_lines = [
        "No candidates promoted.",
        "No threshold changes.",
        "No live trading changes.",
        "No ingestion executed by approval artifacts.",
        "No manifest commands executed.",
        "No live execution adapter enabled.",
        "No orders placed.",
        "Adapter remains disabled by policy.",
    ]
    for line in required_policy_lines:
        assert line in text

    assert "docs/wallet_flow_disabled_chain_operator_readme.md" in text
    assert "/Users/muhammadaatif/joint_research" in text
    assert "/Users/muhammadaatif/joint_research/joint_research" in text

    assert (
        "This release checkpoint proves the wallet-flow disabled chain is documented and guarded; "
        "it does not make wallet-flow tradeable."
    ) in text

    forbidden_phrases = [
        "live trading is enabled",
        "orders are allowed",
        "candidates are promoted",
        "thresholds are changed",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in lower_text
