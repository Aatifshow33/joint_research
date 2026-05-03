from __future__ import annotations

from pathlib import Path

BREAKDOWN_PATH = Path("docs/wallet_flow_rejection_bottleneck_breakdown.md")


def test_wallet_flow_rejection_bottleneck_breakdown_content() -> None:
    assert BREAKDOWN_PATH.exists(), "rejection bottleneck breakdown file must exist"

    text = BREAKDOWN_PATH.read_text(encoding="utf-8")
    lower_text = text.lower()

    assert "# Wallet-flow Rejection Bottleneck Breakdown" in text
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in text
    assert "/workspaces/joint_research" in text
    assert "/Users/muhammadaatif/joint_research" in text
    assert "e34aa68 phase 4.39: add wallet-flow coverage quality diagnostics" in text

    assert "This rejection-bottleneck breakdown does not promote wallet-flow candidates." in text
    assert "This rejection-bottleneck breakdown does not change thresholds." in text
    assert "This rejection-bottleneck breakdown does not approve ingestion, execution, live trading, adapters, manifests, orders, or database mutation." in text

    assert "## Why rejection bottlenecks come next" in text
    assert "## Latest known outcome snapshot" in text
    assert "## Known rejection bottlenecks" in text
    assert "## Breakdown dimensions" in text
    assert "## Minimum diagnostic outputs" in text
    assert "## Interpretation rules" in text
    assert "## Stop / continue criteria" in text
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
    assert "improvement_below_cost_buffer means the candidate edge failed after applying costs, slippage, or buffer allowances." in text
    assert "insufficient_unique_flow_hours means the flow sample is too thin, repetitive, or sparse to trust." in text
    assert "weak_win_rate means the directionality signal is not strong enough to justify the candidate." in text
    assert "A high bottleneck count does not prove the inverse is tradeable." in text
    assert "Reducing a bottleneck only makes later evaluation cleaner." in text

    breakdown_dimensions = [
        "| Dimension | Diagnostic question | Why it matters |",
        "| Market | Which markets fail each rejection reason most often?",
        "| Wallet class | Do whale, market, and copy-flow classes fail for different reasons?",
        "| Horizon | Do 1h, 4h, and 24h horizons fail for different reasons?",
        "| Coverage bucket | Are low-coverage candidates rejected for different reasons than high-coverage candidates?",
        "| Cost bucket | Do candidates fail only after fees, slippage, or buffers are applied?",
        "| Win-rate bucket | Are candidates rejected because directionality is weak?",
        "| Concentration bucket | Are results dominated by a small number of wallets or hours?",
        "| Recency bucket | Are stale samples failing differently than recent samples?",
    ]
    for item in breakdown_dimensions:
        assert item in text

    minimum_outputs = [
        "Rejection counts by market.",
        "Rejection counts by wallet class.",
        "Rejection counts by horizon.",
        "Rejection counts by market and horizon.",
        "Rejection counts by wallet class and horizon.",
        "Rejection counts by coverage bucket.",
        "Rejection counts by cost bucket.",
        "Rejection counts by win-rate bucket.",
        "Rejection counts by concentration bucket.",
        "Rejection counts by recency bucket.",
        "Top repeated rejection combinations.",
        "Least-bad rejected candidates for review only.",
    ]
    for item in minimum_outputs:
        assert item in text

    interpretation_rules = [
        "If most failures are cost-buffer related, do not remove costs; inspect raw edge versus practical edge.",
        "If most failures are insufficient unique flow hours, improve coverage diagnostics before promotion review.",
        "If most failures are weak win rate, treat wallet-flow as weak standalone signal.",
        "If one market class performs better, mark it diagnostic-only until out-of-sample evidence exists.",
        "If one horizon performs better, do not generalize it to other horizons.",
        "If failures disappear only after threshold loosening, do not promote.",
        "If least-bad rejected candidates still fail cost or win-rate checks, keep them rejected.",
        "If bottlenecks improve after better coverage, proceed to standalone-versus-supporting-feature comparison.",
    ]
    for item in interpretation_rules:
        assert item in text

    stop_continue = [
        "| Finding | Decision |",
        "| Bottlenecks are broad across markets, classes, and horizons | Treat wallet-flow as likely weak standalone signal.",
        "| Bottlenecks are concentrated in low-coverage buckets | Continue coverage work before judging signal quality.",
        "| Bottlenecks are mostly cost-buffer failures | Review raw edge versus practical edge; do not remove costs.",
        "| Bottlenecks are mostly weak win-rate failures | Stop promotion review and keep candidates rejected.",
        "| A narrow segment looks better but evidence is sparse | Mark diagnostic-only; do not promote.",
        "| A narrow segment looks better with broad coverage | Continue to standalone-versus-supporting-feature comparison.",
        "| Any improvement requires threshold loosening | Stop; do not promote.",
    ]
    for item in stop_continue:
        assert item in text

    assert "The next phase should be wallet-flow standalone-versus-supporting-feature comparison." in text
    assert "Rejection-bottleneck breakdowns should come before any threshold review." in text
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
        "This rejection-bottleneck breakdown helps explain why wallet-flow candidates failed; it does not make wallet-flow tradeable."
        in text
    )

    forbidden_phrases = [
        "live trading is enabled",
        "wallet-flow is tradeable",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in lower_text
