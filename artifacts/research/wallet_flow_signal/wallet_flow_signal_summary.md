# Wallet Flow Signal Research Summary

**EXPLORATORY ONLY - NOT TRADEABLE.**

This report tests whether Polymarket wallet/trader flow predicts forward crypto returns better than probability movement alone. SIMULATION_READY means paper simulation only.

## Coverage

- Segment rows tested: 464
- SIMULATION_READY: 0
- WATCHLIST: 0
- WEAK: 0
- REJECTED: 464
- Segment rows before de-dup: 2067
- Segment rows after de-dup: 464
- wallet_flow rows: 1001
- market_flow_hourly rows: 397
- whale_flow_hourly rows: 392
- copy_flow rows: 9

## Rejection/Downgrade Reasons

- insufficient_unique_flow_hours: 379
- insufficient_samples: 85

## Overfit Warnings

- duplicate_segment_competition: 464
- low_sample_warning: 464
- unstable_train_test_warning: 201
- low_non_zero_net_flow_coverage: 3

## Top Wallet-Flow Candidates

No wallet-flow candidate survived beyond REJECTED.

Practical read: wallet-flow does not yet show robust uplift over baseline.

## Recommended Backfill Plan

Data coverage is still thin for stable wallet-flow inference. Recommended next run (manual, not automatic):
- `joint-research ingest polymarket-wallet-flow --limit-markets 150 --limit-events 5000`
- `joint-research ingest polymarket-wallet-flow --asset BTC --limit-markets 100 --limit-events 5000`
- `joint-research ingest polymarket-wallet-flow --asset ETH --limit-markets 100 --limit-events 5000`

## Interpretation Guardrails

- No live trading, no API keys, no execution path.
- Wallet-flow rows align to the same hour or nearest prior flow hour.
- SIMULATION_READY is not tradeable; it only means paper simulation is warranted.
