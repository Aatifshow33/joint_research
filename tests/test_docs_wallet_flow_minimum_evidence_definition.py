from __future__ import annotations

from pathlib import Path

EVIDENCE_PATH = Path("docs/wallet_flow_minimum_evidence_definition.md")


def test_wallet_flow_minimum_evidence_definition_content() -> None:
    assert EVIDENCE_PATH.exists(), "minimum evidence definition file must exist"

    text = EVIDENCE_PATH.read_text(encoding="utf-8")
    lower_text = text.lower()

    assert "# Wallet-flow Minimum Evidence Definition" in text
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in text
    assert "/workspaces/joint_research" in text
    assert "/Users/muhammadaatif/joint_research" in text
    assert "a01dabf phase 4.41: add wallet-flow standalone feature comparison" in text

    assert "This minimum-evidence definition does not promote wallet-flow candidates." in text
    assert "This minimum-evidence definition does not change thresholds." in text
    assert "This minimum-evidence definition does not approve ingestion, execution, live trading, adapters, manifests, orders, or database mutation." in text

    assert "## Why minimum evidence comes next" in text
    assert "## Latest known outcome snapshot" in text
    assert "## Known rejection bottlenecks" in text
    assert "## Minimum evidence categories" in text
    assert "## Minimum required review artifacts" in text
    assert "## Evidence interpretation rules" in text
    assert "## Stop / continue criteria" in text
    assert "## Promotion-review RFC boundary" in text
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
    assert "These bottlenecks mean current evidence is not sufficient." in text
    assert "Minimum evidence must address practical edge, data coverage, and win-rate quality." in text
    assert "Passing a future evidence review would still not automatically approve live trading." in text

    categories = [
        "| Category | Minimum evidence question | Required interpretation |",
        "| Coverage | Is market, wallet-class, horizon, and time coverage broad enough to trust?",
        "| Practical edge | Does performance survive fees, slippage, and cost buffers?",
        "| Win rate | Is directional accuracy strong enough without cherry-picking?",
        "| Out-of-sample stability | Does evidence persist outside the discovery sample?",
        "| Segment breadth | Does value appear across more than one narrow market or wallet segment?",
        "| Incremental value | Does wallet-flow add value beyond existing stronger signals?",
        "| Risk behavior | Does wallet-flow avoid increasing drawdown or downside concentration?",
        "| Reproducibility | Can the result be reproduced deterministically from documented inputs?",
    ]
    for item in categories:
        assert item in text

    artifacts = [
        "Coverage quality report.",
        "Rejection-bottleneck breakdown report.",
        "Standalone-versus-supporting-feature comparison report.",
        "Cost-adjusted performance summary.",
        "Out-of-sample stability report.",
        "Market-by-market evidence table.",
        "Wallet-class evidence table.",
        "Horizon-by-horizon evidence table.",
        "Risk and drawdown comparison.",
        "Reproducibility checklist.",
        "Operator review notes.",
        "Explicit non-tradeability statement.",
    ]
    for item in artifacts:
        assert item in text

    interpretation_rules = [
        "If coverage is weak, do not start promotion review.",
        "If cost-adjusted results fail, do not promote.",
        "If win rate remains weak, do not promote.",
        "If evidence only works in-sample, do not promote.",
        "If evidence only works after threshold loosening, do not promote.",
        "If wallet-flow adds no incremental value, stop expansion.",
        "If risk worsens, do not promote.",
        "If all evidence is strong, proceed only to a separate promotion-review RFC.",
    ]
    for item in interpretation_rules:
        assert item in text

    stop_continue = [
        "| Finding | Decision |",
        "| Evidence fails coverage requirements | Stop promotion review; improve diagnostics only.",
        "| Evidence fails cost-adjusted requirements | Keep candidates rejected.",
        "| Evidence fails win-rate requirements | Keep candidates rejected.",
        "| Evidence is narrow or segment-specific | Mark diagnostic-only.",
        "| Evidence is in-sample only | Require out-of-sample review before any next step.",
        "| Evidence adds no incremental value | Stop expansion except archival maintenance.",
        "| Evidence is strong across coverage, cost, win rate, stability, and risk | Continue only to separate promotion-review RFC.",
        "| Any next step requires threshold loosening | Stop; do not promote.",
    ]
    for item in stop_continue:
        assert item in text

    assert "This document is not the promotion-review RFC." in text
    assert "A future promotion-review RFC would need separate scope, separate approval, and separate tests." in text
    assert "Any future live execution work would require a separate execution RFC." in text
    assert "No candidate can be promoted from this document." in text

    assert "The next phase should be wallet-flow research diagnostic package index." in text
    assert "The index should organize the post-freeze diagnostic documents." in text
    assert "All outputs must remain exploratory and non-tradeable." in text

    operator_checks = [
        "Run git status -sb before the phase.",
        "Confirm the repo path is /workspaces/joint_research in Codespaces.",
        "Confirm no accidental poetry.lock, __pycache__, egg-info, or environment files are staged.",
        "Confirm no thresholds are changed.",
        "Confirm no candidates are promoted.",
        "Confirm no ingestion, execution, adapters, manifests, orders, or database mutation are approved.",
    ]
    for item in operator_checks:
        assert item in text

    assert (
        "This minimum-evidence definition describes what future wallet-flow evidence would need before review; it does not make wallet-flow tradeable."
        in text
    )

    forbidden_phrases = [
        "live trading is enabled",
        "wallet-flow is tradeable",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in lower_text
