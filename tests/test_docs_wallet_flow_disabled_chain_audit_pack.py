from pathlib import Path

DOC_PATH = Path("docs/wallet_flow_disabled_chain_audit_pack.md")


def _text() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def test_wallet_flow_disabled_chain_audit_pack_exists_and_contains_required_sections() -> None:
    assert DOC_PATH.exists()
    text = _text()

    assert "# Wallet-flow Disabled Chain Audit Pack" in text
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in text
    assert "/Users/muhammadaatif/joint_research" in text

    for doc_path in [
        "docs/wallet_flow_disabled_chain_operator_readme.md",
        "docs/wallet_flow_disabled_chain_release_notes.md",
        "docs/wallet_flow_disabled_chain_index.md",
    ]:
        assert doc_path in text

    for checklist_item in [
        "- [ ] Confirm wallet-flow remains exploratory only.",
        "- [ ] Confirm no candidates are promoted.",
        "- [ ] Confirm no thresholds are changed.",
        "- [ ] Confirm no live trading changes are included.",
        "- [ ] Confirm no ingestion is executed by approval artifacts.",
        "- [ ] Confirm no manifest commands are executed.",
        "- [ ] Confirm no live execution adapter is enabled.",
        "- [ ] Confirm no orders are placed.",
        "- [ ] Confirm adapter remains disabled by policy.",
    ]:
        assert checklist_item in text

    for status in [
        "DISABLED_BY_POLICY",
        "DISABLED_BY_POLICY_CONFIRMED",
        "DISABLED_CHAIN_CONFIRMED",
        "POLICY_GUARD_PASS",
    ]:
        assert status in text

    for phase_label in [
        "Phase 4.25",
        "Phase 4.26",
        "Phase 4.27",
        "Phase 4.28",
        "Phase 4.29",
        "Phase 4.30",
        "Phase 4.31",
    ]:
        assert phase_label in text

    for stop_condition in [
        "Stop if any expected safe status is missing.",
        "Stop if any artifact implies execution approval.",
        "Stop if any artifact implies ingestion approval.",
        "Stop if any artifact implies candidate promotion.",
        "Stop if any artifact implies threshold changes.",
        "Stop if any artifact implies orders are allowed.",
    ]:
        assert stop_condition in text

    assert "/Users/muhammadaatif/joint_research/joint_research" in text
    assert "This audit pack helps reviewers verify the disabled wallet-flow documentation chain; it does not make wallet-flow tradeable." in text


def test_wallet_flow_disabled_chain_audit_pack_forbidden_phrasing_absent() -> None:
    lowered = _text().lower()

    forbidden_phrases = [
        "live trading is enabled",
    ]

    for phrase in forbidden_phrases:
        assert phrase not in lowered
