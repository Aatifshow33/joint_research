# Wallet Flow Signal Research Summary

**EXPLORATORY ONLY - NOT TRADEABLE.**

This report tests whether Polymarket wallet/trader flow predicts forward crypto returns better than probability movement alone. SIMULATION_READY means paper simulation only.

## Coverage

- Segment rows tested: 1082
- SIMULATION_READY: 0
- WATCHLIST: 0
- WEAK: 0
- REJECTED: 1082
- Segment rows before de-dup: 5661
- Segment rows after de-dup: 1082
- wallet_flow rows: 26658
- market_flow_hourly rows: 3296
- whale_flow_hourly rows: 3110
- copy_flow rows: 233

## Rejection/Downgrade Reasons

- insufficient_unique_flow_hours: 616
- no_net_improvement_after_cost: 187
- train_test_direction_mismatch: 151
- insufficient_samples: 128

## Overfit Warnings

- duplicate_segment_competition: 1082
- low_sample_warning: 831
- unstable_train_test_warning: 516
- thin_copy_flow_warning: 210

## Top Wallet-Flow Candidates

No wallet-flow candidate survived beyond REJECTED.

Practical read: wallet-flow does not yet show robust uplift over baseline.

## Interpretation Guardrails

- No live trading, no API keys, no execution path.
- Wallet-flow rows align to the same hour or nearest prior flow hour.
- SIMULATION_READY is not tradeable; it only means paper simulation is warranted.
