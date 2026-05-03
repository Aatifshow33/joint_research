# Wallet-flow Rejection Bottleneck Breakdown

Status: EXPLORATORY ONLY - NOT TRADEABLE

Codespaces repo path:
/workspaces/joint_research

Local Mac repo path reference:
/Users/muhammadaatif/joint_research

Current checkpoint:
e34aa68 phase 4.39: add wallet-flow coverage quality diagnostics

This document defines how to analyze why wallet-flow candidates are rejected by market, wallet class, and horizon before any future threshold or promotion review. It is intended to keep rejection diagnosis separate from candidate promotion.

This rejection-bottleneck breakdown does not promote wallet-flow candidates.

This rejection-bottleneck breakdown does not change thresholds.

This rejection-bottleneck breakdown does not approve ingestion, execution, live trading, adapters, manifests, orders, or database mutation.

## Why rejection bottlenecks come next

- Coverage quality diagnostics were defined first.
- Wallet-flow research usefulness is still unproven.
- The latest known result had zero candidates beyond rejected.
- Rejection reasons must be broken down before debating thresholds.
- Bottleneck analysis is for diagnosis only, not promotion.

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
- improvement_below_cost_buffer means the candidate edge failed after applying costs, slippage, or buffer allowances.
- insufficient_unique_flow_hours means the flow sample is too thin, repetitive, or sparse to trust.
- weak_win_rate means the directionality signal is not strong enough to justify the candidate.
- A high bottleneck count does not prove the inverse is tradeable.
- Reducing a bottleneck only makes later evaluation cleaner.

## Breakdown dimensions

| Dimension | Diagnostic question | Why it matters |
|-----------|---------------------|----------------|
| Market | Which markets fail each rejection reason most often? | Identifies whether failures are broad or concentrated in a few markets. |
| Wallet class | Do whale, market, and copy-flow classes fail for different reasons? | Different flow sources may have different failure modes. |
| Horizon | Do 1h, 4h, and 24h horizons fail for different reasons? | A candidate may be invalid at one horizon but diagnosable at another. |
| Coverage bucket | Are low-coverage candidates rejected for different reasons than high-coverage candidates? | Separates data-quality failures from signal-quality failures. |
| Cost bucket | Do candidates fail only after fees, slippage, or buffers are applied? | Distinguishes raw edge from practical edge. |
| Win-rate bucket | Are candidates rejected because directionality is weak? | Identifies whether the signal has basic predictive weakness. |
| Concentration bucket | Are results dominated by a small number of wallets or hours? | Detects fragile results that may not generalize. |
| Recency bucket | Are stale samples failing differently than recent samples? | Helps avoid over-trusting old behavior. |

## Minimum diagnostic outputs

- Rejection counts by market.
- Rejection counts by wallet class.
- Rejection counts by horizon.
- Rejection counts by market and horizon.
- Rejection counts by wallet class and horizon.
- Rejection counts by coverage bucket.
- Rejection counts by cost bucket.
- Rejection counts by win-rate bucket.
- Rejection counts by concentration bucket.
- Rejection counts by recency bucket.
- Top repeated rejection combinations.
- Least-bad rejected candidates for review only.

## Interpretation rules

- If most failures are cost-buffer related, do not remove costs; inspect raw edge versus practical edge.
- If most failures are insufficient unique flow hours, improve coverage diagnostics before promotion review.
- If most failures are weak win rate, treat wallet-flow as weak standalone signal.
- If one market class performs better, mark it diagnostic-only until out-of-sample evidence exists.
- If one horizon performs better, do not generalize it to other horizons.
- If failures disappear only after threshold loosening, do not promote.
- If least-bad rejected candidates still fail cost or win-rate checks, keep them rejected.
- If bottlenecks improve after better coverage, proceed to standalone-versus-supporting-feature comparison.

## Stop / continue criteria

| Finding | Decision |
|---------|----------|
| Bottlenecks are broad across markets, classes, and horizons | Treat wallet-flow as likely weak standalone signal. |
| Bottlenecks are concentrated in low-coverage buckets | Continue coverage work before judging signal quality. |
| Bottlenecks are mostly cost-buffer failures | Review raw edge versus practical edge; do not remove costs. |
| Bottlenecks are mostly weak win-rate failures | Stop promotion review and keep candidates rejected. |
| A narrow segment looks better but evidence is sparse | Mark diagnostic-only; do not promote. |
| A narrow segment looks better with broad coverage | Continue to standalone-versus-supporting-feature comparison. |
| Any improvement requires threshold loosening | Stop; do not promote. |

## Recommended next phase

- The next phase should be wallet-flow standalone-versus-supporting-feature comparison.
- Rejection-bottleneck breakdowns should come before any threshold review.
- All outputs must remain exploratory and non-tradeable.

## Operator checklist

- [ ] Run git status -sb before the phase.
- [ ] Confirm the repo path is /workspaces/joint_research in Codespaces.
- [ ] Confirm no accidental poetry.lock, __pycache__, egg-info, or environment files are staged.
- [ ] Confirm no thresholds are changed.
- [ ] Confirm no candidates are promoted.
- [ ] Confirm no ingestion, execution, adapters, manifests, orders, or database mutation are approved.

This rejection-bottleneck breakdown helps explain why wallet-flow candidates failed; it does not make wallet-flow tradeable.
