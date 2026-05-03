from __future__ import annotations

from pathlib import Path

PLAN_PATH = Path("docs/wallet_flow_coverage_diagnostic_plan.md")


def test_wallet_flow_coverage_diagnostic_plan_content() -> None:
    assert PLAN_PATH.exists(), "coverage diagnostic plan file must exist"

    text = PLAN_PATH.read_text(encoding="utf-8")
    lower_text = text.lower()

    assert "# Wallet-flow Coverage Diagnostic Plan" in text
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in text
    assert "/workspaces/joint_research" in text
    assert "/Users/muhammadaatif/joint_research" in text
    assert "6ccca39 phase 4.45: add wallet-flow post-freeze research closeout" in text

    assert "This coverage diagnostic plan does not promote wallet-flow candidates." in text
    assert "This coverage diagnostic plan does not change thresholds." in text
    assert "This coverage diagnostic plan does not approve ingestion, execution, live trading, adapters, manifests, orders, or database mutation." in text

    assert "## Why this phase comes after closeout" in text
    assert "## Latest known outcome snapshot" in text
    assert "## Known rejection bottlenecks" in text
    assert "## Coverage diagnostic workstreams" in text
    assert "## Minimum diagnostic artifacts" in text
    assert "## Data safety boundaries" in text
    assert "## Rerun readiness criteria" in text
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
    assert "insufficient_unique_flow_hours is the main coverage-specific bottleneck." in text
    assert "improvement_below_cost_buffer and weak_win_rate cannot be interpreted confidently until coverage quality is understood." in text

    workstream_rows = [
        "| Market coverage | Which markets have enough flow history to evaluate? | Market-level coverage table | No candidate promotion. |",
        "| Wallet coverage | Which wallets/classes contribute enough observations? | Wallet-class coverage table | No wallet promotion. |",
        "| Time coverage | Are flow hours dense enough across each horizon? | Unique-flow-hour distribution | No threshold change. |",
        "| Horizon coverage | Which horizons are too sparse or noisy? | Horizon-by-coverage matrix | No rerun approval. |",
        "| Missingness | Where are nulls, gaps, or empty flow buckets concentrated? | Missingness summary | No ingestion approval. |",
        "| Concentration | Are results dominated by a few wallets or markets? | Concentration diagnostics | No live execution. |",
        "| Recency | Is useful flow stale or recent enough for evaluation? | Recency distribution | No tradeability claim. |",
        "| Cost sensitivity | Does apparent edge survive cost buffers? | Cost-buffer diagnostic table | No threshold loosening. |",
        "| Win-rate stability | Are weak win rates concentrated in coverage-poor segments? | Win-rate-by-coverage table | No candidate promotion. |",
        "| Rerun readiness | What must be true before rerunning research? | Rerun readiness checklist | No automatic rerun. |",
    ]
    for item in workstream_rows:
        assert item in text

    artifact_items = [
        "Market-level coverage table.",
        "Wallet-class coverage table.",
        "Unique-flow-hour distribution.",
        "Horizon-by-coverage matrix.",
        "Missingness summary.",
        "Concentration diagnostics.",
        "Recency distribution.",
        "Cost-buffer diagnostic table.",
        "Win-rate-by-coverage table.",
        "Rerun readiness checklist.",
        "Operator notes explaining whether evidence is still too sparse.",
    ]
    for item in artifact_items:
        assert item in text

    safety_boundaries = [
        "This plan does not authorize new ingestion.",
        "This plan does not authorize network calls.",
        "This plan does not authorize manifest execution.",
        "This plan does not authorize adapter execution.",
        "This plan does not authorize database mutation.",
        "This plan does not authorize live trading or orders.",
        "This plan does not change thresholds.",
        "This plan does not promote candidates.",
        "This plan does not make wallet-flow tradeable.",
    ]
    for item in safety_boundaries:
        assert item in text

    rerun_criteria = [
        "Coverage diagnostics exist and are reviewed.",
        "insufficient_unique_flow_hours is explained by market, wallet class, horizon, and time bucket.",
        "Coverage-poor segments are separated from coverage-usable segments.",
        "Missingness and concentration are documented.",
        "Cost-buffer and weak-win-rate failures are reviewed by coverage segment.",
        "Operator notes explain whether a rerun would test new evidence or merely repeat the same failure.",
        "Rerun requires separate approval and separate scope.",
        "Rerun must remain exploratory unless future minimum-evidence requirements are met.",
    ]
    for item in rerun_criteria:
        assert item in text

    assert "The next phase should create a static coverage diagnostic artifact specification." in text
    assert "It should define output schemas and expected files for coverage diagnostics." in text
    assert "It should not run ingestion or rerun research." in text
    assert "It should remain exploratory and non-tradeable." in text

    operator_checks = [
        "Run git status -sb before the phase.",
        "Confirm the repo path is /workspaces/joint_research in Codespaces.",
        "Confirm no accidental poetry.lock, __pycache__, egg-info, or environment files are staged.",
        "Confirm no thresholds are changed.",
        "Confirm no candidates are promoted.",
        "Confirm no ingestion, execution, adapters, manifests, orders, or database mutation are approved.",
        "Confirm this phase defines diagnostics only and does not run them.",
    ]
    for item in operator_checks:
        assert item in text

    assert (
        "This coverage diagnostic plan starts the wallet-flow data/coverage research track; it does not make wallet-flow tradeable."
        in text
    )

    forbidden_phrases = [
        "live trading is enabled",
        "wallet-flow is tradeable",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in lower_text
