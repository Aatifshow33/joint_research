# Cross-Venue Prediction-Market Arbitrage Scan

> Research / detection artifact. No orders are placed. Edges are net of
> modeled venue fees; near-misses are retained on purpose.

- generated_at: `2026-06-18T23:26:30.122437+00:00`
- venue A quotes: 3
- venue B quotes: 2
- matched markets: 2
- **actionable opportunities: 1**
- total actionable net profit (modeled): $36.07

## Outcome reason codes

| reason_code | count |
| --- | ---: |
| actionable | 1 |
| negative_gross_edge | 1 |

## Top opportunities by net edge per pair

| market_key | net_edge/pair | contracts | capital | net_profit | reason |
| --- | ---: | ---: | ---: | ---: | --- |
| BTC-100K-20261231|0xbtc100k | 0.1528 | 236 | $199.93 | $36.07 | actionable |
| ETH-5K-20261231|0xeth5k | 0.0000 | 0 | $0.00 | $0.00 | negative_gross_edge |
