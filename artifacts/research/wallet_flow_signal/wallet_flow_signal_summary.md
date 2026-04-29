# Wallet Flow Signal Research Summary

**EXPLORATORY ONLY - NOT TRADEABLE.**

This report tests whether Polymarket wallet/trader flow predicts forward crypto returns better than probability movement alone. SIMULATION_READY means paper simulation only.

## Coverage

- Segment rows tested: 2060
- SIMULATION_READY: 9
- WATCHLIST: 110
- WEAK: 1026
- REJECTED: 915

## Top Wallet-Flow Candidates

| Rank | Grade | Asset | Feature | Segment | Horizon | Test Avg | Baseline Test Avg | Improvement | Win Rate |
| ---: | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | SIMULATION_READY | BTC | flow_momentum_4h | all:all | 1h | +0.00057 | -0.00023 | +0.00080 | 0.59 |
| 2 | SIMULATION_READY | BTC | flow_momentum_4h | active_wallet_bucket:high | 1h | +0.00057 | -0.00023 | +0.00080 | 0.59 |
| 3 | SIMULATION_READY | BTC | flow_momentum_4h | whale_flow_bucket:normal | 1h | +0.00057 | -0.00023 | +0.00080 | 0.59 |
| 4 | SIMULATION_READY | ETH | net_flow_usdc | all:all | 1h | +0.00101 | +0.00037 | +0.00064 | 0.62 |
| 5 | SIMULATION_READY | ETH | net_flow_usdc | active_wallet_bucket:high | 1h | +0.00101 | +0.00037 | +0.00064 | 0.62 |
| 6 | SIMULATION_READY | ETH | net_flow_usdc | whale_flow_bucket:normal | 1h | +0.00101 | +0.00037 | +0.00064 | 0.62 |
| 7 | SIMULATION_READY | BTC | net_flow_usdc | all:all | 1h | +0.00064 | +0.00000 | +0.00063 | 0.59 |
| 8 | SIMULATION_READY | BTC | net_flow_usdc | active_wallet_bucket:high | 1h | +0.00064 | +0.00000 | +0.00063 | 0.59 |
| 9 | SIMULATION_READY | BTC | net_flow_usdc | whale_flow_bucket:normal | 1h | +0.00064 | +0.00000 | +0.00063 | 0.59 |
| 10 | WATCHLIST | ETH | flow_momentum_4h | flow_direction:buy_dominant | 4h | +0.00243 | +0.00033 | +0.00210 | 0.54 |

## Interpretation Guardrails

- No live trading, no API keys, no execution path.
- Wallet-flow rows align to the same hour or nearest prior flow hour.
- SIMULATION_READY is not tradeable; it only means paper simulation is warranted.
