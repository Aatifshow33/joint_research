from __future__ import annotations

from pathlib import Path

CLOSEOUT_PATH = Path("docs/wallet_flow_schema_contract_closeout_note.md")


def test_wallet_flow_schema_contract_closeout_note_content() -> None:
    assert CLOSEOUT_PATH.exists(), "wallet-flow schema contract closeout note file must exist"

    text = CLOSEOUT_PATH.read_text(encoding="utf-8")
    lower_text = text.lower()

    headings = [
        "## Purpose",
        "## Frozen checkpoint chain",
        "## Canonical schema contract",
        "## Documentation pointers",
        "## Static-only boundary",
        "## Non-goals",
        "## Operator closeout checklist",
    ]
    for heading in headings:
        assert heading in text

    assert "EXPLORATORY ONLY - NOT TRADEABLE" in text

    checkpoints = [
        "1a8e737 phase 4.49: add wallet-flow coverage schema contract",
        "17ea647 phase 4.50: document wallet-flow schema contract pointer",
        "c64825d phase 4.51: add wallet-flow schema contract docs pointer",
    ]
    for checkpoint in checkpoints:
        assert checkpoint in text

    paths = [
        "src/joint_research/wallet_flow_coverage_schema_contract.py",
        "tests/test_wallet_flow_coverage_schema_contract.py",
        "docs/wallet_flow_static_coverage_schema_validation_tests.md",
        "docs/wallet_flow_static_coverage_diagnostic_artifact_spec.md",
        "docs/README.md",
    ]
    for path in paths:
        assert path in text

    symbols = [
        "CoverageArtifactSchema",
        "COVERAGE_ARTIFACT_SCHEMAS",
        "get_coverage_artifact_schema",
        "list_coverage_artifact_names",
    ]
    for symbol in symbols:
        assert symbol in text

    boundaries = [
        "no artifact writing",
        "no diagnostic CSV generation",
        "no diagnostic markdown generation",
        "no ingestion",
        "no research rerun",
        "no manifest execution",
        "no database mutation",
        "no threshold loosening",
        "no candidate promotion",
        "no wallet promotion",
        "no paper trading",
        "no live trading",
        "no order placement",
        "no tradeability claim",
    ]
    for boundary in boundaries:
        assert boundary in text

    checklist_items = [
        "schema contract located",
        "docs pointer located",
        "diagnostic artifact spec located",
        "exploratory-only status confirmed",
        "no rerun approval granted",
        "no execution approval granted",
    ]
    for item in checklist_items:
        assert item in text

    assert (
        "This closeout note freezes the wallet-flow schema contract documentation chain; it does not make wallet-flow tradeable."
        in text
    )

    forbidden_phrases = [
        "live trading is enabled",
        "wallet-flow is tradeable",
        "approve candidates",
        "promote wallets",
        "relax thresholds",
        "execute orders",
        "place orders",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in lower_text
