from __future__ import annotations

from pathlib import Path


INDEX_PATH = Path("docs/wallet_flow_disabled_chain_index.md")


def test_wallet_flow_disabled_chain_index_content() -> None:
    assert INDEX_PATH.exists(), "index file must exist"

    text = INDEX_PATH.read_text()
    lower_text = text.lower()

    assert "# Wallet-flow Disabled Chain Docs Index" in text
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in text
    assert "/Users/muhammadaatif/joint_research" in text

    assert "docs/wallet_flow_disabled_chain_operator_readme.md" in text
    assert "docs/wallet_flow_disabled_chain_release_notes.md" in text

    required_checkpoint_lines = [
        "Phase 4.25 disabled adapter interface",
        "Phase 4.26 disabled adapter run receipt",
        "Phase 4.27 disabled chain summary",
        "Phase 4.28 disabled policy guard",
        "Phase 4.29 operator README",
        "Phase 4.30 release notes",
    ]
    for line in required_checkpoint_lines:
        assert line in text

    required_non_approval_lines = [
        "The index does not approve ingestion.",
        "The index does not approve execution.",
        "The index does not approve live trading.",
        "The index does not promote wallet-flow candidates.",
        "The index does not change thresholds.",
        "The index does not enable an adapter.",
        "The index does not allow orders.",
    ]
    for line in required_non_approval_lines:
        assert line in text

    required_status_tokens = [
        "DISABLED_BY_POLICY",
        "DISABLED_BY_POLICY_CONFIRMED",
        "DISABLED_CHAIN_CONFIRMED",
        "POLICY_GUARD_PASS",
    ]
    for token in required_status_tokens:
        assert token in text

    assert "/Users/muhammadaatif/joint_research/joint_research" in text
    assert (
        "This docs index helps operators find the disabled wallet-flow chain documentation; "
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
