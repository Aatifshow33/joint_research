# Lead-Lag Research Summary

**EXPLORATORY ONLY - NOT TRADEABLE.**

This report scans aligned Polymarket YES probability changes against same-hour and forward crypto returns. It is a research screen, not a trading signal.

## Coverage

- Markets/tokens tested: 40
- Hypothesis rows: 160
- Segmented bucket rows: 74
- Horizons: same-hour, +1h, +4h, +24h
- Segments: asset, market/question/slug, time-to-resolution bucket, volume bucket, liquidity bucket

## Top Candidates

| Rank | Asset | Lag | N | Corr | t-stat | p-value | Market |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | BTC | 1h | 357 | -0.1496 | -2.85 | 0.004613 | microstrategy-sells-any-bitcoin-by-june-30-2026 |
| 2 | BTC | 1h | 529 | -0.1035 | -2.39 | 0.01723 | will-bitcoin-reach-1000000-by-december-31-2026-946 |
| 3 | SOL | 4h | 424 | +0.1114 | +2.30 | 0.0218 | will-solana-reach-160-in-april-2026 |
| 4 | BTC | 24h | 313 | -0.1288 | -2.29 | 0.02265 | bitcoin-all-time-high-by-december-31-2026 |
| 5 | BTC | 1h | 304 | -0.1302 | -2.28 | 0.02319 | bitcoin-all-time-high-by-september-30-2026 |
| 6 | BTC | 1h | 278 | +0.1192 | +1.99 | 0.04713 | will-bitcoin-dip-to-40k-in-april-2026-795-619 |
| 7 | BTC | 1h | 567 | -0.0816 | -1.95 | 0.05212 | will-bitcoin-reach-110000-by-december-31-2026-658-339-969 |
| 8 | ETH | 24h | 581 | -0.0734 | -1.77 | 0.07701 | megaeth-market-cap-fdv-1pt5b-one-day-after-launch-371-844-879-681 |
| 9 | BTC | 4h | 333 | -0.0963 | -1.76 | 0.07944 | microstrategy-sells-any-bitcoin-by-december-31-2026 |
| 10 | BTC | 4h | 393 | -0.0880 | -1.75 | 0.0815 | will-bitcoin-reach-150000-by-december-31-2026-557-246-971 |

## Interpretation Guardrails

- These are univariate exploratory correlations, not causal evidence.
- Multiple testing, thin samples, overlapping markets, and stale Polymarket pricing can create false positives.
- A candidate is not tradeable until it survives out-of-sample testing, cost/slippage modeling, execution simulation, and risk controls.
