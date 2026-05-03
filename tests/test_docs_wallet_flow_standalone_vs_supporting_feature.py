from __future__ import annotations

from pathlib import Path

COMPARISON_PATH = Path("docs/wallet_flow_standalone_vs_supporting_feature.md")


def test_wallet_flow_standalone_vs_supporting_feature_content() -> None:
    assert COMPARISON_PATH.exists(), "standalone vs supporting feature file must exist"

    text = COMPARISON_PATH.read_text(encoding="utf-8")
    lower_text = text.lower()

    assert "# Wallet-flow Standalone Versus Supporting Feature" in text
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in text
    assert "/workspaces/joint_research" in text
    assert "/Users/muhammadaatif/joint_research" in text
    assert "846b471 phase 4.40: add wallet-flow rejection bottleneck breakdown" in text

    assert "This standalone-versus-supporting-feature plan does not promote wallet-flow candidates." in text
    assert "This standalone-versus-supporting-feature plan does not change thresholds." in text
    assert "This standalone-versus-supporting-feature plan does not approve ingestion, execution, live trading, adapters, manifests, orders, or database mutation." in text

    assert "## Why this comparison comes next" in text
    assert "## Latest known outcome snapshot" in text
    assert "## Known rejection bottlenecks" in text
    assert "## Comparison modes" in text
    assert "## Minimum diagnostic comparisons" in text
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
    assert "These bottlenecks make standalone usefulness unproven." in text
    assert "Supporting-feature value must be tested separately." in text
    assert "Supporting-feature value does not automatically make wallet-flow tradeable." in text

    comparison_modes = [
        "| Mode | Diagnostic question | Interpretation |",
        "| Standalone signal | Does wallet-flow alone survive costs, coverage checks, and win-rate checks?",
        "| Supporting feature | Does wallet-flow improve an existing stronger signal without weakening risk metrics?",
        "| Filter feature | Does wallet-flow help reject bad candidates from another signal?",
        "| Confidence feature | Does wallet-flow improve confidence calibration for another signal?",
        "| Timing feature | Does wallet-flow improve entry or exit timing for another signal?",
        "| Regime feature | Does wallet-flow help only in certain market regimes?",
        "| Risk feature | Does wallet-flow identify fragile or crowded conditions?",
        "| Null feature | Does wallet-flow add no incremental value?",
    ]
    for item in comparison_modes:
        assert item in text

    minimum_comparisons = [
        "Wallet-flow standalone results versus baseline.",
        "Existing signal results without wallet-flow.",
        "Existing signal results with wallet-flow as a feature.",
        "Existing signal results with wallet-flow as a filter.",
        "Existing signal results with wallet-flow as a confidence adjustment.",
        "Market-by-market incremental value.",
        "Wallet-class incremental value.",
        "Horizon-by-horizon incremental value.",
        "Cost-adjusted incremental value.",
        "Out-of-sample stability comparison.",
        "Drawdown or downside-risk comparison.",
        "Rejection-bottleneck change after adding wallet-flow.",
    ]
    for item in minimum_comparisons:
        assert item in text

    interpretation_rules = [
        "If wallet-flow fails standalone checks, do not promote it as a standalone signal.",
        "If wallet-flow only helps before costs, treat it as weak evidence.",
        "If wallet-flow helps only in one narrow market, mark it diagnostic-only.",
        "If wallet-flow improves confidence but worsens drawdown, do not promote.",
        "If wallet-flow improves filtering but not direction, treat it as a supporting filter only.",
        "If wallet-flow helps only after threshold loosening, do not promote.",
        "If wallet-flow adds no incremental value, freeze further expansion.",
        "If wallet-flow adds stable incremental value out-of-sample, move to minimum-evidence definition before any promotion review.",
    ]
    for item in interpretation_rules:
        assert item in text

    stop_continue = [
        "| Finding | Decision |",
        "| Wallet-flow standalone remains rejected | Do not promote standalone wallet-flow.",
        "| Wallet-flow adds no incremental value to stronger signals | Stop expansion except archival maintenance.",
        "| Wallet-flow helps only before costs | Keep rejected; inspect practical edge.",
        "| Wallet-flow helps only in sparse coverage buckets | Continue coverage diagnostics; do not promote.",
        "| Wallet-flow helps as a filter with stable out-of-sample improvement | Continue to minimum-evidence definition.",
        "| Wallet-flow improves confidence but increases downside risk | Do not promote.",
        "| Wallet-flow adds stable value across markets, classes, and horizons | Continue to minimum-evidence definition.",
    ]
    for item in stop_continue:
        assert item in text

    assert "The next phase should be wallet-flow minimum-evidence definition." in text
    assert "Standalone-versus-supporting-feature comparison should come before any threshold review." in text
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
        "This standalone-versus-supporting-feature plan helps decide whether wallet-flow has any incremental research value; it does not make wallet-flow tradeable."
        in text
    )

    forbidden_phrases = [
        "live trading is enabled",
        "wallet-flow is tradeable",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in lower_text
