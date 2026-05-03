from __future__ import annotations

from pathlib import Path


AUDIT_PATH = Path("docs/wallet_flow_research_effectiveness_audit.md")


def test_wallet_flow_research_effectiveness_audit_content() -> None:
    assert AUDIT_PATH.exists(), "audit file must exist"

    text = AUDIT_PATH.read_text(encoding="utf-8")
    lower_text = text.lower()

    assert "# Wallet-flow Research Effectiveness Audit" in text
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in text
    assert "/workspaces/joint_research" in text
    assert "/Users/muhammadaatif/joint_research" in text
    assert "0f9f7c1 phase 4.35: add wallet-flow disabled docs root pointer" in text

    assert "This audit does not promote wallet-flow candidates." in text
    assert "This audit does not change thresholds." in text
    assert "This audit does not approve ingestion, execution, live trading, adapters, manifests, orders, or database mutation." in text

    assert "## Current best assessment" in text
    assert "Safety and governance are strong." in text
    assert "Documentation and traceability are strong." in text
    assert "Research usefulness is not proven yet." in text
    assert "Wallet-flow candidate quality is the main unresolved question." in text
    assert "Wallet-flow should remain exploratory until coverage and rejection bottlenecks improve." in text

    assert "## Known latest research outcome" in text
    assert "SIMULATION_READY: 0" in text
    assert "WATCHLIST: 0" in text
    assert "WEAK: 0" in text
    assert "REJECTED: 1049" in text
    assert "No wallet-flow candidate survived beyond REJECTED." in text

    assert "## Known rejection bottlenecks" in text
    assert "improvement_below_cost_buffer: 5426" in text
    assert "insufficient_unique_flow_hours: 4993" in text
    assert "weak_win_rate: 4904" in text
    assert "improvement_below_cost_buffer means the measured edge did not clear estimated trading cost or friction buffer." in text
    assert "insufficient_unique_flow_hours means the flow sample is too thin or repetitive to trust." in text
    assert "weak_win_rate means forward outcomes were not consistent enough." in text

    assert "## Strengths" in text
    strengths = [
        "Strong disabled-chain safety boundary.",
        "Deterministic artifact trail.",
        "Clear approval and policy guard layers.",
        "Good documentation coverage.",
        "Repeatable test coverage around docs and disabled-policy artifacts.",
        "Conservative bias against over-promoting weak signals.",
    ]
    for strength in strengths:
        assert strength in text

    assert "## Weaknesses" in text
    weaknesses = [
        "Research value is still unproven.",
        "Candidate survival is currently zero beyond rejected.",
        "Wallet-flow coverage appears too thin for robust signal selection.",
        "Rejection counts suggest cost-buffer and sample-size issues dominate.",
        "The system has many governance artifacts but limited alpha evidence.",
        "More documentation will not fix signal weakness by itself.",
    ]
    for weakness in weaknesses:
        assert weakness in text

    assert "## Priority audit questions" in text
    questions = [
        "1. Are we collecting enough wallet-flow history?",
        "2. Are unique flow hours sufficient across markets and wallets?",
        "3. Are rejected candidates failing because thresholds are appropriate or because data coverage is poor?",
        "4. Are cost and slippage assumptions too conservative, too loose, or correct?",
        "5. Does wallet-flow work better as a supporting feature than as a standalone signal?",
        "6. Which markets, wallets, and horizons produce the least-bad rejected candidates?",
        "7. What minimum evidence is required before any future promotion review?",
    ]
    for question in questions:
        assert question in text

    assert "## Stop / keep / improve matrix" in text
    assert "| Area | Decision | Reason |" in text
    assert "| Disabled execution chain | Keep | Strong safety boundary and useful audit trail. |" in text
    assert "| More disabled-chain docs | Stop for now | Current docs package is already strong enough; more docs may add clutter. |" in text
    assert "| Wallet-flow signal promotion | Stop | Current outcomes do not justify promotion. |" in text
    assert "| Wallet-flow coverage expansion | Improve | Candidate rejection suggests sample-size and coverage gaps. |" in text
    assert "| Rejection bottleneck reporting | Improve | Needed to know exactly where research fails. |" in text
    assert "| Threshold changes | Stop | Do not loosen thresholds before coverage and bottleneck evidence improves. |" in text
    assert "| Future live execution | Stop | Must remain separate and intentionally far from this disabled-chain package. |" in text

    assert "## Recommended next roadmap" in text
    roadmap = [
        "1. Build one master wallet-flow research summary report.",
        "2. Add a rejection-bottleneck breakdown by market, wallet class, and horizon.",
        "3. Add coverage quality metrics before any threshold discussion.",
        "4. Compare wallet-flow as standalone signal versus supporting feature.",
        "5. Produce a final go / no-go recommendation for wallet-flow research continuation.",
        "6. Keep all work exploratory and non-tradeable.",
    ]
    for item in roadmap:
        assert item in text

    assert "## Finish-line judgment" in text
    judgment = [
        "The disabled-chain package is near-finish.",
        "The wallet-flow research signal is not near-finish.",
        "The project should freeze disabled-chain packaging soon.",
        "The next useful work should focus on coverage, rejection diagnostics, and evidence quality.",
        "Wallet-flow should not be promoted until candidate survival improves with stronger evidence.",
    ]
    for line in judgment:
        assert line in text

    assert (
        "This research-effectiveness audit helps decide whether wallet-flow deserves more research investment; "
        "it does not make wallet-flow tradeable."
    ) in text

    forbidden_phrases = [
        "live trading is enabled",
        "wallet-flow is tradeable",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in lower_text