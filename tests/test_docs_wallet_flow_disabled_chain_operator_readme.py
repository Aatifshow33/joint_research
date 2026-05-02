from __future__ import annotations

from pathlib import Path


README_PATH = Path("docs/wallet_flow_disabled_chain_operator_readme.md")


def test_wallet_flow_disabled_chain_operator_readme_content() -> None:
    assert README_PATH.exists(), "README file must exist"

    text = README_PATH.read_text()
    lower_text = text.lower()

    assert "# Wallet-flow Disabled Chain Operator README" in text
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in text

    required_boundaries = [
        "No candidates promoted.",
        "No threshold changes.",
        "No live trading changes.",
        "No ingestion executed by these approval artifacts.",
        "No manifest commands executed.",
        "No live execution adapter enabled.",
        "No orders placed.",
        "Adapter remains disabled by policy.",
    ]
    for boundary in required_boundaries:
        assert boundary in text

    artifact_names = [
        "wallet_flow_backfill_execution_manifest",
        "wallet_flow_manifest_review_gate",
        "wallet_flow_approved_manifest_packet",
        "wallet_flow_manifest_audit_index",
        "wallet_flow_dry_run_execution_plan",
        "wallet_flow_guarded_operator_handoff",
        "wallet_flow_operator_approval_ledger",
        "wallet_flow_approval_execution_contract",
        "wallet_flow_contract_audit_receipt",
        "wallet_flow_disabled_adapter_interface",
        "wallet_flow_disabled_adapter_run_receipt",
        "wallet_flow_disabled_chain_summary",
        "wallet_flow_disabled_policy_guard",
    ]
    for artifact in artifact_names:
        assert artifact in text

    required_statuses = [
        "APPROVED",
        "CONTRACT_READY",
        "RECEIPT_READY",
        "DISABLED_BY_POLICY",
        "DISABLED_BY_POLICY_CONFIRMED",
        "DISABLED_CHAIN_CONFIRMED",
        "POLICY_GUARD_PASS",
    ]
    for status in required_statuses:
        assert status in text

    assert "/Users/muhammadaatif/joint_research" in text
    assert "/Users/muhammadaatif/joint_research/joint_research" in text

    assert "wallet_flow_disabled_policy_guard.md" in text
    assert "wallet_flow_disabled_policy_guard.json" in text

    assert (
        "This chain proves the wallet-flow path remains disabled by policy; "
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
