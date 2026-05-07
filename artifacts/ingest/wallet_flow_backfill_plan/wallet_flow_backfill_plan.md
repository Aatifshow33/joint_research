# Wallet Flow Backfill Plan

**EXPLORATORY ONLY - NOT TRADEABLE.**

- Mode: execute
- Selected stage: stage_1_quick
- Stage 1 markets: 75
- Stage 2 markets: 75
- Stage 3 markets: 75

## Coverage Snapshot

- markets_total: 1952
- markets_with_wallet_flow: 132
- wallet_flow_rows: 25052
- trade_rows: 24823
- copy_rows: 229
- market_flow_hourly_rows: 3075
- whale_flow_hourly_rows: 2894

## Coverage Quality Focus

- Prioritize continuity gain: markets where additional backfill can repair missing hourly gaps.
- Keep breadth/depth expansion, but deprioritize stale high-row markets with weak marginal continuity gain.
- Still exploratory only, not tradeable.

## Staged Plan

- `stage_1_quick`: BTC/ETH-first continuity + depth repair
- `stage_2_depth`: all-asset continuity repair and depth expansion
- `stage_3_breadth`: broad coverage expansion after continuity/depth priorities

## Top Selected Stage Markets

| Rank | Asset | Market | 1mo Vol | Need | Obs Hours | Span Hrs | Continuity | Missing Hrs | Recent | Reason |
| ---: | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | --- | --- |
| 1 | BTC | will-bitcoin-reach-82500-in-april | 889805.44 | continuity_repair | 98 | 194 | 0.50 | 97 | no | priority_asset,active,undercovered,need:continuity_repair,stale,gap_repair,volume |
| 2 | BTC | bitcoin-above-76k-on-april-28 | 75436.75 | continuity_repair | 41 | 85 | 0.48 | 45 | no | priority_asset,active,undercovered,need:continuity_repair,stale,gap_repair,volume |
| 3 | BTC | will-bitcoin-dip-to-70000-in-april-118-383 | 965628.05 | continuity_repair | 107 | 228 | 0.47 | 122 | no | priority_asset,active,undercovered,need:continuity_repair,stale,gap_repair,volume |
| 4 | BTC | bitcoin-above-78k-on-april-28 | 69470.85 | continuity_repair | 38 | 86 | 0.44 | 49 | no | priority_asset,active,undercovered,need:continuity_repair,stale,gap_repair,volume |
| 5 | BTC | bitcoin-above-74k-on-april-29 | 522157.39 | continuity_repair | 37 | 87 | 0.42 | 51 | no | priority_asset,active,undercovered,need:continuity_repair,stale,gap_repair,volume |
| 6 | BTC | bitcoin-above-72k-on-april-30 | 601809.71 | continuity_repair | 36 | 85 | 0.42 | 50 | no | priority_asset,active,undercovered,need:continuity_repair,stale,gap_repair,volume |
| 7 | BTC | bitcoin-above-78k-on-april-29 | 84844.01 | continuity_repair | 49 | 127 | 0.38 | 79 | no | priority_asset,active,undercovered,need:continuity_repair,stale,gap_repair,volume |
| 8 | BTC | bitcoin-above-74k-on-april-30 | 68449.50 | continuity_repair | 27 | 71 | 0.38 | 45 | no | priority_asset,active,undercovered,need:continuity_repair,stale,gap_repair,volume |
| 9 | BTC | will-bitcoin-dip-to-70k-in-may-2026 | 93604.43 | continuity_repair | 29 | 77 | 0.37 | 49 | yes | priority_asset,active,undercovered,need:continuity_repair,recent,gap_repair,volume |
| 10 | BTC | will-bitcoin-dip-to-74k-april-27-may-3 | 92717.76 | continuity_repair | 55 | 147 | 0.37 | 93 | no | priority_asset,active,undercovered,need:continuity_repair,stale,gap_repair,volume |
| 11 | BTC | bitcoin-above-72k-on-april-28 | 94728.69 | continuity_repair | 32 | 87 | 0.36 | 56 | no | priority_asset,active,undercovered,need:continuity_repair,stale,gap_repair,volume |
| 12 | BTC | will-bitcoin-reach-82k-april-27-may-3 | 96439.60 | continuity_repair | 61 | 169 | 0.36 | 109 | no | priority_asset,active,undercovered,need:continuity_repair,stale,gap_repair,volume |
| 13 | BTC | bitcoin-above-76k-on-may-1 | 96988.50 | continuity_repair | 29 | 82 | 0.35 | 54 | no | priority_asset,active,undercovered,need:continuity_repair,stale,gap_repair,volume |
| 14 | BTC | bitcoin-above-80k-on-april-28 | 69232.63 | continuity_repair | 27 | 77 | 0.35 | 51 | no | priority_asset,active,undercovered,need:continuity_repair,stale,gap_repair,volume |
| 15 | BTC | bitcoin-above-78k-on-may-1 | 96814.12 | continuity_repair | 26 | 75 | 0.34 | 50 | no | priority_asset,active,undercovered,need:continuity_repair,stale,gap_repair,volume |
| 16 | BTC | will-bitcoin-dip-to-75000-in-april | 774913.77 | continuity_repair | 79 | 263 | 0.30 | 185 | no | priority_asset,active,undercovered,need:continuity_repair,stale,gap_repair,volume |
| 17 | BTC | will-bitcoin-dip-to-72k-april-27-may-3 | 84609.66 | continuity_repair | 30 | 118 | 0.25 | 89 | no | priority_asset,active,undercovered,need:continuity_repair,stale,gap_repair,volume |
| 18 | BTC | will-bitcoin-dip-to-70k-april-27-may-3 | 90620.92 | continuity_repair | 32 | 146 | 0.22 | 115 | no | priority_asset,active,undercovered,need:continuity_repair,stale,gap_repair,volume |
| 19 | BTC | will-bitcoin-reach-80k-in-april-2026-794 | 8689572.23 | continuity_repair | 134 | 782 | 0.17 | 649 | yes | priority_asset,active,undercovered,need:continuity_repair,recent,gap_repair,volume |
| 20 | BTC | bitcoin-above-72k-on-may-1 | 90032.08 | continuity_repair | 27 | 162 | 0.17 | 136 | no | priority_asset,active,undercovered,need:continuity_repair,stale,gap_repair,volume |
