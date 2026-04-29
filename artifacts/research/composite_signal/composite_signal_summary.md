# Composite Signal Research Summary

**EXPLORATORY ONLY - NOT TRADEABLE.**

This report scans deterministic, train-learned composite rule families. SIMULATION_READY means send to paper simulation only.

## Coverage

- Rule rows tested: 1305
- SIMULATION_READY: 0
- WATCHLIST: 56
- WEAK: 66
- REJECTED: 1183

## Top Composite Candidates

| Rank | Grade | Asset | Rule | Horizon | Test Acc | Test Avg | Market |
| ---: | --- | --- | --- | ---: | ---: | ---: | --- |
| 1 | WATCHLIST | XRP | polymarket_leads_crypto_momentum | 24h | 0.76 | 0.00101 | will-xrp-reach-2-in-april-2026 |
| 2 | WATCHLIST | BTC | probability_momentum_continuation | 24h | 0.59 | 0.00051 | will-bitcoin-reach-110000-by-december-31-2026-658-339-969 |
| 3 | WATCHLIST | BTC | probability_reversal | 24h | 0.59 | 0.00051 | will-bitcoin-reach-110000-by-december-31-2026-658-339-969 |
| 4 | WATCHLIST | BTC | probability_momentum_continuation | 4h | 0.58 | 0.00049 | will-bitcoin-reach-110000-by-december-31-2026-658-339-969 |
| 5 | WATCHLIST | BTC | probability_reversal | 4h | 0.58 | 0.00049 | will-bitcoin-reach-110000-by-december-31-2026-658-339-969 |
| 6 | WATCHLIST | ETH | probability_momentum_continuation | 1h | 0.56 | 0.00056 | will-ethereum-dip-to-2000-in-april-2026 |
| 7 | WATCHLIST | ETH | probability_reversal | 1h | 0.56 | 0.00056 | will-ethereum-dip-to-2000-in-april-2026 |
| 8 | WATCHLIST | BTC | probability_momentum_continuation | 24h | 0.57 | 0.00022 | will-bitcoin-dip-to-65k-in-april-2026-355-765 |
| 9 | WATCHLIST | BTC | probability_reversal | 24h | 0.57 | 0.00022 | will-bitcoin-dip-to-65k-in-april-2026-355-765 |
| 10 | WATCHLIST | ETH | probability_momentum_continuation | 24h | 0.58 | 0.00030 | megaeth-market-cap-fdv-2b-one-day-after-launch-738-867-649-272-765-733 |

## Interpretation Guardrails

- No live trading, no API keys, no execution path.
- Rule directions are learned on train only and validated on test.
- SIMULATION_READY is not tradeable; it only means paper simulation is warranted.
