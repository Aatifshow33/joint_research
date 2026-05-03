# Wallet-flow Research Effectiveness Audit

Status: EXPLORATORY ONLY - NOT TRADEABLE

Codespaces repo path: /workspaces/joint_research
Local Mac repo path reference: /Users/muhammadaatif/joint_research
Current checkpoint: 0f9f7c1 phase 4.35: add wallet-flow disabled docs root pointer

The disabled-chain safety package is strong, but the next question is whether wallet-flow research is useful enough to continue improving.

This audit does not promote wallet-flow candidates.
This audit does not change thresholds.
This audit does not approve ingestion, execution, live trading, adapters, manifests, orders, or database mutation.

## Current best assessment

- Safety and governance are strong.
- Documentation and traceability are strong.
- Research usefulness is not proven yet.
- Wallet-flow candidate quality is the main unresolved question.
- Wallet-flow should remain exploratory until coverage and rejection bottlenecks improve.

## Known latest research outcome

- SIMULATION_READY: 0
- WATCHLIST: 0
- WEAK: 0
- REJECTED: 1049
- No wallet-flow candidate survived beyond REJECTED.

## Known rejection bottlenecks

- improvement_below_cost_buffer: 5426
- insufficient_unique_flow_hours: 4993
- weak_win_rate: 4904

improvement_below_cost_buffer means the measured edge did not clear estimated trading cost or friction buffer.
insufficient_unique_flow_hours means the flow sample is too thin or repetitive to trust.
weak_win_rate means forward outcomes were not consistent enough.

## Strengths

- Strong disabled-chain safety boundary.
- Deterministic artifact trail.
- Clear approval and policy guard layers.
- Good documentation coverage.
- Repeatable test coverage around docs and disabled-policy artifacts.
- Conservative bias against over-promoting weak signals.

## Weaknesses

- Research value is still unproven.
- Candidate survival is currently zero beyond rejected.
- Wallet-flow coverage appears too thin for robust signal selection.
- Rejection counts suggest cost-buffer and sample-size issues dominate.
- The system has many governance artifacts but limited alpha evidence.
- More documentation will not fix signal weakness by itself.

## Priority audit questions

1. Are we collecting enough wallet-flow history?
2. Are unique flow hours sufficient across markets and wallets?
3. Are rejected candidates failing because thresholds are appropriate or because data coverage is poor?
4. Are cost and slippage assumptions too conservative, too loose, or correct?
5. Does wallet-flow work better as a supporting feature than as a standalone signal?
6. Which markets, wallets, and horizons produce the least-bad rejected candidates?
7. What minimum evidence is required before any future promotion review?

## Stop / keep / improve matrix

| Area | Decision | Reason |
|------|----------|--------|
| Disabled execution chain | Keep | Strong safety boundary and useful audit trail. |
| More disabled-chain docs | Stop for now | Current docs package is already strong enough; more docs may add clutter. |
| Wallet-flow signal promotion | Stop | Current outcomes do not justify promotion. |
| Wallet-flow coverage expansion | Improve | Candidate rejection suggests sample-size and coverage gaps. |
| Rejection bottleneck reporting | Improve | Needed to know exactly where research fails. |
| Threshold changes | Stop | Do not loosen thresholds before coverage and bottleneck evidence improves. |
| Future live execution | Stop | Must remain separate and intentionally far from this disabled-chain package. |

## Recommended next roadmap

1. Build one master wallet-flow research summary report.
2. Add a rejection-bottleneck breakdown by market, wallet class, and horizon.
3. Add coverage quality metrics before any threshold discussion.
4. Compare wallet-flow as standalone signal versus supporting feature.
5. Produce a final go / no-go recommendation for wallet-flow research continuation.
6. Keep all work exploratory and non-tradeable.

## Finish-line judgment

- The disabled-chain package is near-finish.
- The wallet-flow research signal is not near-finish.
- The project should freeze disabled-chain packaging soon.
- The next useful work should focus on coverage, rejection diagnostics, and evidence quality.
- Wallet-flow should not be promoted until candidate survival improves with stronger evidence.

This research-effectiveness audit helps decide whether wallet-flow deserves more research investment; it does not make wallet-flow tradeable.