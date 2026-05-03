# Wallet-flow Coverage Diagnostic Plan

Status: EXPLORATORY ONLY - NOT TRADEABLE

Codespaces repo path:
/workspaces/joint_research

Local Mac repo path reference:
/Users/muhammadaatif/joint_research

Current checkpoint:
6ccca39 phase 4.45: add wallet-flow post-freeze research closeout

This plan starts the data/coverage diagnostic track after the documentation loop was closed. It defines what to inspect before any rerun while keeping wallet-flow exploratory and not tradeable.

This coverage diagnostic plan does not promote wallet-flow candidates.

This coverage diagnostic plan does not change thresholds.

This coverage diagnostic plan does not approve ingestion, execution, live trading, adapters, manifests, orders, or database mutation.

## Why this phase comes after closeout

- The wallet-flow documentation loop was closed by the post-freeze research closeout note.
- More approval docs should not be added without new evidence.
- The next useful work is understanding missing coverage and evidence quality.
- The latest known result still had zero candidates beyond rejected.
- This plan defines diagnostics only and does not run them.

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
- insufficient_unique_flow_hours is the main coverage-specific bottleneck.
- improvement_below_cost_buffer and weak_win_rate cannot be interpreted confidently until coverage quality is understood.

## Coverage diagnostic workstreams

| Workstream | Question | Diagnostic output | Boundary |
|------------|----------|-------------------|----------|
| Market coverage | Which markets have enough flow history to evaluate? | Market-level coverage table | No candidate promotion. |
| Wallet coverage | Which wallets/classes contribute enough observations? | Wallet-class coverage table | No wallet promotion. |
| Time coverage | Are flow hours dense enough across each horizon? | Unique-flow-hour distribution | No threshold change. |
| Horizon coverage | Which horizons are too sparse or noisy? | Horizon-by-coverage matrix | No rerun approval. |
| Missingness | Where are nulls, gaps, or empty flow buckets concentrated? | Missingness summary | No ingestion approval. |
| Concentration | Are results dominated by a few wallets or markets? | Concentration diagnostics | No live execution. |
| Recency | Is useful flow stale or recent enough for evaluation? | Recency distribution | No tradeability claim. |
| Cost sensitivity | Does apparent edge survive cost buffers? | Cost-buffer diagnostic table | No threshold loosening. |
| Win-rate stability | Are weak win rates concentrated in coverage-poor segments? | Win-rate-by-coverage table | No candidate promotion. |
| Rerun readiness | What must be true before rerunning research? | Rerun readiness checklist | No automatic rerun. |

## Minimum diagnostic artifacts

- Market-level coverage table.
- Wallet-class coverage table.
- Unique-flow-hour distribution.
- Horizon-by-coverage matrix.
- Missingness summary.
- Concentration diagnostics.
- Recency distribution.
- Cost-buffer diagnostic table.
- Win-rate-by-coverage table.
- Rerun readiness checklist.
- Operator notes explaining whether evidence is still too sparse.

## Data safety boundaries

- This plan does not authorize new ingestion.
- This plan does not authorize network calls.
- This plan does not authorize manifest execution.
- This plan does not authorize adapter execution.
- This plan does not authorize database mutation.
- This plan does not authorize live trading or orders.
- This plan does not change thresholds.
- This plan does not promote candidates.
- This plan does not make wallet-flow tradeable.

## Rerun readiness criteria

- Coverage diagnostics exist and are reviewed.
- insufficient_unique_flow_hours is explained by market, wallet class, horizon, and time bucket.
- Coverage-poor segments are separated from coverage-usable segments.
- Missingness and concentration are documented.
- Cost-buffer and weak-win-rate failures are reviewed by coverage segment.
- Operator notes explain whether a rerun would test new evidence or merely repeat the same failure.
- Rerun requires separate approval and separate scope.
- Rerun must remain exploratory unless future minimum-evidence requirements are met.

## Recommended next phase

- The next phase should create a static coverage diagnostic artifact specification.
- It should define output schemas and expected files for coverage diagnostics.
- It should not run ingestion or rerun research.
- It should remain exploratory and non-tradeable.

## Operator checklist

- [ ] Run git status -sb before the phase.
- [ ] Confirm the repo path is /workspaces/joint_research in Codespaces.
- [ ] Confirm no accidental poetry.lock, __pycache__, egg-info, or environment files are staged.
- [ ] Confirm no thresholds are changed.
- [ ] Confirm no candidates are promoted.
- [ ] Confirm no ingestion, execution, adapters, manifests, orders, or database mutation are approved.
- [ ] Confirm this phase defines diagnostics only and does not run them.

This coverage diagnostic plan starts the wallet-flow data/coverage research track; it does not make wallet-flow tradeable.
