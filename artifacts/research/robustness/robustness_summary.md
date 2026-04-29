# Robustness Research Summary

**EXPLORATORY ONLY - NOT TRADEABLE.**

This report checks whether Polymarket probability-change candidates survive temporal validation, deterministic permutation baselines, rolling-window stability checks, and minimum quality filters.

## Coverage

- Hypothesis rows tested: 261
- PROMISING: 3
- WATCHLIST: 2
- WEAK: 80
- REJECTED: 176

## Top Robustness Candidates

| Rank | Grade | Asset | Lag | OOS Match | Emp p | Stability | Market |
| ---: | --- | --- | ---: | --- | ---: | ---: | --- |
| 1 | PROMISING | BTC | 1h | True | 0.0199 | 1.00 | microstrategy-sells-any-bitcoin-by-june-30-2026 |
| 2 | PROMISING | BTC | 1h | True | 0.0249 | 1.00 | bitcoin-all-time-high-by-september-30-2026 |
| 3 | PROMISING | SOL | 4h | True | 0.0199 | 0.75 | will-solana-reach-160-in-april-2026 |
| 4 | WATCHLIST | BTC | 1h | True | 0.0647 | 1.00 | will-bitcoin-reach-110000-by-december-31-2026-658-339-969 |
| 5 | WATCHLIST | ETH | 1h | True | 0.0945 | 0.75 | will-ethereum-reach-3000-in-april-2026 |
| 6 | WEAK | SOL | 24h | True | 0.3731 | 1.00 | will-solana-reach-160-in-april-2026 |
| 7 | WEAK | BTC | 4h | True | 0.1841 | 1.00 | will-bitcoin-dip-to-10000-by-december-31-2026-888-644-567-258-946-853 |
| 8 | WEAK | BTC | 4h | True | 0.1891 | 0.75 | will-bitcoin-dip-to-25000-by-december-31-2026-948-243-253-666-115-787-981-282-573-719-186-417-762-754-486-851-278-145 |
| 9 | WEAK | BTC | 4h | True | 0.0945 | 1.00 | will-bitcoin-reach-150000-by-december-31-2026-557-246-971 |
| 10 | WEAK | BTC | 24h | True | 0.0498 | 1.00 | bitcoin-all-time-high-by-december-31-2026 |

## Interpretation Guardrails

- PROMISING means simulation-worthy, not tradeable.
- These checks still do not model fees, slippage, fill uncertainty, position sizing, or market-impact constraints.
- A robust paper signal must still survive walk-forward simulation before any execution discussion.
