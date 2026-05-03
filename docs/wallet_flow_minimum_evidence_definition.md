# Wallet-flow Minimum Evidence Definition

Status: EXPLORATORY ONLY - NOT TRADEABLE

Codespaces repo path:
/workspaces/joint_research

Local Mac repo path reference:
/Users/muhammadaatif/joint_research

Current checkpoint:
a01dabf phase 4.41: add wallet-flow standalone feature comparison

This document defines the minimum evidence required before any future wallet-flow promotion review. It is designed to keep evidence requirements separate from promotion decisions and to preserve wallet-flow as exploratory only.

This minimum-evidence definition does not promote wallet-flow candidates.

This minimum-evidence definition does not change thresholds.

This minimum-evidence definition does not approve ingestion, execution, live trading, adapters, manifests, orders, or database mutation.

## Why minimum evidence comes next

- Coverage quality diagnostics, rejection-bottleneck breakdowns, and standalone-versus-supporting-feature comparison were defined first.
- Wallet-flow research usefulness is still unproven.
- The latest known result had zero candidates beyond rejected.
- Minimum evidence must be defined before any future promotion review.
- Minimum evidence is a review gate, not approval.

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
- These bottlenecks mean current evidence is not sufficient.
- Minimum evidence must address practical edge, data coverage, and win-rate quality.
- Passing a future evidence review would still not automatically approve live trading.

## Minimum evidence categories

| Category | Minimum evidence question | Required interpretation |
|----------|---------------------------|-------------------------|
| Coverage | Is market, wallet-class, horizon, and time coverage broad enough to trust? | Weak coverage blocks promotion review. |
| Practical edge | Does performance survive fees, slippage, and cost buffers? | Raw edge without practical edge is insufficient. |
| Win rate | Is directional accuracy strong enough without cherry-picking? | Weak win rate keeps candidates rejected. |
| Out-of-sample stability | Does evidence persist outside the discovery sample? | In-sample-only evidence is insufficient. |
| Segment breadth | Does value appear across more than one narrow market or wallet segment? | Narrow evidence remains diagnostic-only. |
| Incremental value | Does wallet-flow add value beyond existing stronger signals? | No incremental value blocks expansion. |
| Risk behavior | Does wallet-flow avoid increasing drawdown or downside concentration? | Worse risk blocks promotion review. |
| Reproducibility | Can the result be reproduced deterministically from documented inputs? | Non-reproducible evidence is insufficient. |

## Minimum required review artifacts

- Coverage quality report.
- Rejection-bottleneck breakdown report.
- Standalone-versus-supporting-feature comparison report.
- Cost-adjusted performance summary.
- Out-of-sample stability report.
- Market-by-market evidence table.
- Wallet-class evidence table.
- Horizon-by-horizon evidence table.
- Risk and drawdown comparison.
- Reproducibility checklist.
- Operator review notes.
- Explicit non-tradeability statement.

## Evidence interpretation rules

- If coverage is weak, do not start promotion review.
- If cost-adjusted results fail, do not promote.
- If win rate remains weak, do not promote.
- If evidence only works in-sample, do not promote.
- If evidence only works after threshold loosening, do not promote.
- If wallet-flow adds no incremental value, stop expansion.
- If risk worsens, do not promote.
- If all evidence is strong, proceed only to a separate promotion-review RFC.

## Stop / continue criteria

| Finding | Decision |
|---------|----------|
| Evidence fails coverage requirements | Stop promotion review; improve diagnostics only. |
| Evidence fails cost-adjusted requirements | Keep candidates rejected. |
| Evidence fails win-rate requirements | Keep candidates rejected. |
| Evidence is narrow or segment-specific | Mark diagnostic-only. |
| Evidence is in-sample only | Require out-of-sample review before any next step. |
| Evidence adds no incremental value | Stop expansion except archival maintenance. |
| Evidence is strong across coverage, cost, win rate, stability, and risk | Continue only to separate promotion-review RFC. |
| Any next step requires threshold loosening | Stop; do not promote. |

## Promotion-review RFC boundary

- This document is not the promotion-review RFC.
- A future promotion-review RFC would need separate scope, separate approval, and separate tests.
- Any future live execution work would require a separate execution RFC.
- No candidate can be promoted from this document.

## Recommended next phase

- The next phase should be wallet-flow research diagnostic package index.
- The index should organize the post-freeze diagnostic documents.
- All outputs must remain exploratory and non-tradeable.

## Operator checklist

- [ ] Run git status -sb before the phase.
- [ ] Confirm the repo path is /workspaces/joint_research in Codespaces.
- [ ] Confirm no accidental poetry.lock, __pycache__, egg-info, or environment files are staged.
- [ ] Confirm no thresholds are changed.
- [ ] Confirm no candidates are promoted.
- [ ] Confirm no ingestion, execution, adapters, manifests, orders, or database mutation are approved.

This minimum-evidence definition describes what future wallet-flow evidence would need before review; it does not make wallet-flow tradeable.
