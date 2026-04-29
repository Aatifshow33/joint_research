# Wallet Flow Signal Research Summary

**EXPLORATORY ONLY - NOT TRADEABLE.**

This report tests whether Polymarket wallet/trader flow predicts forward crypto returns better than probability movement alone. SIMULATION_READY means paper simulation only.

## Coverage

- Segment rows tested: 764
- SIMULATION_READY: 0
- WATCHLIST: 0
- WEAK: 0
- REJECTED: 764
- Segment rows before de-dup: 3513
- Segment rows after de-dup: 764
- wallet_flow rows: 2994
- market_flow_hourly rows: 1135
- whale_flow_hourly rows: 1096
- copy_flow rows: 22

## Rejection/Downgrade Reasons

- insufficient_unique_flow_hours: 616
- insufficient_samples: 82
- no_net_improvement_after_cost: 35
- train_test_direction_mismatch: 31

## Overfit Warnings

- duplicate_segment_competition: 764
- low_sample_warning: 746
- unstable_train_test_warning: 372
- thin_copy_flow_warning: 15

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
