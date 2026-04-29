# Derivatives Regime Research Summary

**EXPLORATORY ONLY - NOT TRADEABLE.**

This report tests whether Polymarket -> crypto signal behavior improves when conditioned on funding/perp-basis regimes. SIMULATION_READY means paper simulation only.

## Coverage

- Segment rows tested: 581
- SIMULATION_READY: 0
- WATCHLIST: 0
- WEAK: 158
- REJECTED: 423

## Top Regime Candidates

| Rank | Grade | Asset | Segment | Horizon | Test Avg | Baseline Test Avg | Improvement | Win Rate |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | WEAK | BTC | funding_intensity:normal | 4h | +0.00084 | +0.00002 | +0.00081 | 0.50 |
| 2 | WEAK | BTC | funding_intensity:normal | 1h | +0.00064 | -0.00012 | +0.00076 | 0.50 |
| 3 | WEAK | ETH | funding_intensity:normal | 24h | +0.00000 | -0.00037 | +0.00037 | 0.00 |
| 4 | WEAK | ETH | funding_intensity:low | 24h | -0.00001 | -0.00011 | +0.00010 | 0.17 |
| 5 | WEAK | ETH | funding_intensity:normal | 24h | +0.00000 | -0.00010 | +0.00010 | 0.00 |
| 6 | WEAK | ETH | funding_direction:positive | 24h | -0.00028 | -0.00037 | +0.00009 | 0.00 |
| 7 | WEAK | BTC | funding_direction:negative | 4h | -0.00002 | -0.00010 | +0.00008 | 0.05 |
| 8 | WEAK | BTC | funding_intensity:low | 4h | -0.00002 | -0.00010 | +0.00008 | 0.05 |
| 9 | WEAK | ETH | funding_intensity:low | 24h | -0.00000 | -0.00008 | +0.00007 | 0.07 |
| 10 | WEAK | ETH | funding_direction:positive | 4h | +0.00000 | -0.00007 | +0.00007 | 0.00 |

## Interpretation Guardrails

- No live trading, no API keys, no execution path.
- Regime alignment uses nearest prior derivatives regime hour per asset symbol.
- SIMULATION_READY is not tradeable; it only means paper simulation is warranted.
