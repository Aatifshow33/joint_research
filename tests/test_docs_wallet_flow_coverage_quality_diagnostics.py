from __future__ import annotations

from pathlib import Path

DIAGNOSTICS_PATH = Path("docs/wallet_flow_coverage_quality_diagnostics.md")


def test_wallet_flow_coverage_quality_diagnostics_content() -> None:
    assert DIAGNOSTICS_PATH.exists(), "coverage quality diagnostics file must exist"

    text = DIAGNOSTICS_PATH.read_text(encoding="utf-8")
    lower_text = text.lower()

    assert "# Wallet-flow Coverage Quality Diagnostics" in text
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in text
    assert "/workspaces/joint_research" in text
    assert "/Users/muhammadaatif/joint_research" in text
    assert "65efd05 phase 4.38: add wallet-flow final freeze checklist" in text

    assert "This diagnostic plan does not promote wallet-flow candidates." in text
    assert "This diagnostic plan does not change thresholds." in text
    assert "This diagnostic plan does not approve ingestion, execution, live trading, adapters, manifests, orders, or database mutation." in text

    assert "## Why coverage quality comes next" in text
    assert "## Latest known outcome snapshot" in text
    assert "## Coverage-related bottleneck context" in text
    assert "## Coverage quality dimensions" in text
    assert "## Minimum diagnostic outputs" in text
    assert "## Diagnostic interpretation rules" in text
    assert "## Stop / continue criteria" in text
    assert "## Recommended next phase" in text
    assert "## Operator checklist" in text

    assert "SIMULATION_READY: 0" in text
    assert "WATCHLIST: 0" in text
    assert "WEAK: 0" in text
    assert "REJECTED: 1049" in text
    assert "No wallet-flow candidate survived beyond REJECTED." in text

    assert "insufficient_unique_flow_hours: 4993" in text
    assert "insufficient_unique_flow_hours means the flow sample is too thin, repetitive, or sparse to trust." in text
    assert "Fixing coverage does not automatically make a signal valid." in text
    assert "Better coverage only makes later rejection analysis more reliable." in text

    dimensions_table = [
        "| Dimension | Diagnostic question | Why it matters |",
        "| Market coverage | Do enough markets have wallet-flow history across the tested horizon?",
        "| Wallet coverage | Are enough distinct wallets represented without one wallet dominating?",
        "| Time coverage | Are there enough unique flow hours across each horizon?",
        "| Horizon coverage | Do 1h, 4h, and 24h horizons each have enough observations?",
        "| Class coverage | Are whale, market, and copy-flow classes represented clearly?",
        "| Missingness | Which markets, wallets, classes, or horizons have missing data?",
        "| Recency | Is coverage recent enough for current market behavior?",
        "| Duplication | Are repeated events or duplicate flow hours inflating counts?",
    ]
    for item in dimensions_table:
        assert item in text

    diagnostic_outputs = [
        "Coverage by market.",
        "Coverage by wallet class.",
        "Coverage by horizon.",
        "Unique flow hours by market and horizon.",
        "Candidate rejection counts by coverage bucket.",
        "Missingness table by market, class, and horizon.",
        "Concentration table showing top-wallet share.",
        "Recency table showing how much coverage is stale.",
        "Duplication check for repeated flow hours.",
    ]
    for item in diagnostic_outputs:
        assert item in text

    interpretation_rules = [
        "If unique flow hours are low, do not loosen thresholds.",
        "If one wallet dominates a market, mark the signal fragile.",
        "If coverage is stale, do not treat old performance as current evidence.",
        "If rejection improves only after removing costs, treat it as weak evidence.",
        "If coverage improves but win rate remains weak, do not promote.",
        "If coverage is strong and rejection remains high, wallet-flow may be a weak standalone signal.",
        "If coverage is weak but some markets look promising, treat them as diagnostic-only watch areas.",
    ]
    for item in interpretation_rules:
        assert item in text

    stop_continue_table = [
        "| Finding | Decision |",
        "| Coverage is thin across most markets and horizons | Continue diagnostics; do not promote.",
        "| Coverage is dominated by a few wallets | Continue diagnostics; mark fragile.",
        "| Coverage is stale | Refresh coverage plan before interpreting results.",
        "| Coverage is broad but win rate remains weak | Treat wallet-flow as likely weak standalone signal.",
        "| Coverage is broad and rejection bottlenecks improve | Continue to rejection-bottleneck breakdown phase.",
        "| Any candidate appears strong only after loosening thresholds | Stop; do not promote.",
    ]
    for item in stop_continue_table:
        assert item in text

    assert "The next phase should be wallet-flow rejection-bottleneck breakdowns by market, wallet class, and horizon." in text
    assert "Coverage diagnostics should come before any threshold review." in text
    assert "All outputs must remain exploratory and non-tradeable." in text

    operator_checklist = [
        "Run git status -sb before the phase.",
        "Confirm the repo path is /workspaces/joint_research in Codespaces.",
        "Confirm no accidental poetry.lock, __pycache__, egg-info, or environment files are staged.",
        "Confirm no thresholds are changed.",
        "Confirm no candidates are promoted.",
        "Confirm no ingestion, execution, adapters, manifests, orders, or database mutation are approved.",
    ]
    for item in operator_checklist:
        assert item in text

    assert (
        "This coverage quality diagnostic plan helps decide what wallet-flow evidence is trustworthy; it does not make wallet-flow tradeable."
        in text
    )

    forbidden_phrases = [
        "live trading is enabled",
        "wallet-flow is tradeable",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in lower_text