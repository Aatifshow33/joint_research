# Wallet-flow Standalone Versus Supporting Feature

Status: EXPLORATORY ONLY - NOT TRADEABLE

Codespaces repo path:
/workspaces/joint_research

Local Mac repo path reference:
/Users/muhammadaatif/joint_research

Current checkpoint:
846b471 phase 4.40: add wallet-flow rejection bottleneck breakdown

This document defines how to compare wallet-flow as a standalone signal versus a supporting feature before any future threshold or promotion review. It is intended to keep standalone signal assessment separate from any candidate promotion discussion.

This standalone-versus-supporting-feature plan does not promote wallet-flow candidates.

This standalone-versus-supporting-feature plan does not change thresholds.

This standalone-versus-supporting-feature plan does not approve ingestion, execution, live trading, adapters, manifests, orders, or database mutation.

## Why this comparison comes next

- Coverage quality diagnostics and rejection-bottleneck breakdowns were defined first.
- Wallet-flow research usefulness is still unproven.
- The latest known result had zero candidates beyond rejected.
- Wallet-flow may be too weak as a standalone signal.
- The next diagnostic question is whether wallet-flow adds value as a supporting feature.

## Latest known outcome snapshot

- SIMULATION_READY: 0
- WATCHLIST: 0
- WEAK: 0
- REJECTED: 1049
- No wallet-flow candidate survived beyond REJECTED.

## Known rejection bottlenecks

- improvement_below_cost_buffer: 5426
- insufficient_unique_flow_hours: 4993
- weak_win_rate: 4904
- These bottlenecks make standalone usefulness unproven.
- Supporting-feature value must be tested separately.
- Supporting-feature value does not automatically make wallet-flow tradeable.

## Comparison modes

| Mode | Diagnostic question | Interpretation |
|------|---------------------|----------------|
| Standalone signal | Does wallet-flow alone survive costs, coverage checks, and win-rate checks? | If not, wallet-flow should not be promoted as its own signal. |
| Supporting feature | Does wallet-flow improve an existing stronger signal without weakening risk metrics? | If yes, wallet-flow may be useful as context only. |
| Filter feature | Does wallet-flow help reject bad candidates from another signal? | Useful filters may reduce false positives without generating trades alone. |
| Confidence feature | Does wallet-flow improve confidence calibration for another signal? | Confidence improvement must be out-of-sample and stable. |
| Timing feature | Does wallet-flow improve entry or exit timing for another signal? | Timing value must survive costs and not be horizon-specific noise. |
| Regime feature | Does wallet-flow help only in certain market regimes? | Regime-specific value must not be generalized. |
| Risk feature | Does wallet-flow identify fragile or crowded conditions? | Risk value can be useful even if directional value is weak. |
| Null feature | Does wallet-flow add no incremental value? | If null, stop expanding wallet-flow except for archival docs. |

## Minimum diagnostic comparisons

- Wallet-flow standalone results versus baseline.
- Existing signal results without wallet-flow.
- Existing signal results with wallet-flow as a feature.
- Existing signal results with wallet-flow as a filter.
- Existing signal results with wallet-flow as a confidence adjustment.
- Market-by-market incremental value.
- Wallet-class incremental value.
- Horizon-by-horizon incremental value.
- Cost-adjusted incremental value.
- Out-of-sample stability comparison.
- Drawdown or downside-risk comparison.
- Rejection-bottleneck change after adding wallet-flow.

## Interpretation rules

- If wallet-flow fails standalone checks, do not promote it as a standalone signal.
- If wallet-flow only helps before costs, treat it as weak evidence.
- If wallet-flow helps only in one narrow market, mark it diagnostic-only.
- If wallet-flow improves confidence but worsens drawdown, do not promote.
- If wallet-flow improves filtering but not direction, treat it as a supporting filter only.
- If wallet-flow helps only after threshold loosening, do not promote.
- If wallet-flow adds no incremental value, freeze further expansion.
- If wallet-flow adds stable incremental value out-of-sample, move to minimum-evidence definition before any promotion review.

## Stop / continue criteria

| Finding | Decision |
|---------|----------|
| Wallet-flow standalone remains rejected | Do not promote standalone wallet-flow. |
| Wallet-flow adds no incremental value to stronger signals | Stop expansion except archival maintenance. |
| Wallet-flow helps only before costs | Keep rejected; inspect practical edge. |
| Wallet-flow helps only in sparse coverage buckets | Continue coverage diagnostics; do not promote. |
| Wallet-flow helps as a filter with stable out-of-sample improvement | Continue to minimum-evidence definition. |
| Wallet-flow improves confidence but increases downside risk | Do not promote. |
| Wallet-flow adds stable value across markets, classes, and horizons | Continue to minimum-evidence definition. |

## Recommended next phase

- The next phase should be wallet-flow minimum-evidence definition.
- Standalone-versus-supporting-feature comparison should come before any threshold review.
- All outputs must remain exploratory and non-tradeable.

## Operator checklist

- [ ] Run git status -sb before the phase.
- [ ] Confirm the repo path is /workspaces/joint_research in Codespaces.
- [ ] Confirm no accidental poetry.lock, __pycache__, egg-info, or environment files are staged.
- [ ] Confirm no thresholds are changed.
- [ ] Confirm no candidates are promoted.
- [ ] Confirm no ingestion, execution, adapters, manifests, orders, or database mutation are approved.

This standalone-versus-supporting-feature plan helps decide whether wallet-flow has any incremental research value; it does not make wallet-flow tradeable.
