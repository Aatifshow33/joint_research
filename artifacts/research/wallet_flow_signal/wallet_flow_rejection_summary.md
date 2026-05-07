# Wallet Flow Rejection Diagnostics

**EXPLORATORY ONLY - NOT TRADEABLE.**

Diagnostics explain why wallet-flow segments were not promoted to SIMULATION_READY.

## Counts

- total_candidates_evaluated=5661
- final_simulation_ready=0
- final_watchlist=0
- final_weak=0
- final_rejected=1082
- dropped_by_duplicate_competition=4579
- segment_rows_before_dedup=5661
- segment_rows_after_dedup=1082

## Rejection Reason Counts

- improvement_below_cost_buffer: 5648
- insufficient_unique_flow_hours: 5129
- weak_win_rate: 5055
- unstable_train_test_behavior: 4778
- duplicate_segment_competition: 4579
- weak_or_negative_test_improvement: 4040
- low_sample_count: 1934
- copy_flow_too_thin: 868
- insufficient_non_zero_net_flow_coverage: 73

## Top Blockers

- improvement_below_cost_buffer: 5648
- insufficient_unique_flow_hours: 5129
- weak_win_rate: 5055

## Top Near-Miss Candidates

| Rank | Candidate Rank | Final Grade | Candidate | Improvement | Net After Cost | Reasons |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | 85 | REJECTED | BTC:bitcoin-all-time-high-by-december-31-2026:102959890468928530190954086704155483076852880798676895426376704430618826404382:1h:net_flow_usdc:all:all | +0.00242 | -0.00158 | improvement_below_cost_buffer;insufficient_unique_flow_hours;unstable_train_test_behavior;weak_win_rate |
| 2 | 61 | REJECTED | BTC:bitcoin-all-time-high-by-december-31-2026:102959890468928530190954086704155483076852880798676895426376704430618826404382:1h:sell_volume_usdc:all:all | +0.00273 | -0.00127 | improvement_below_cost_buffer;insufficient_unique_flow_hours;weak_win_rate |
| 3 | 89 | REJECTED | BTC:bitcoin-all-time-high-by-december-31-2026:102959890468928530190954086704155483076852880798676895426376704430618826404382:1h:flow_momentum_4h:all:all | +0.00238 | -0.00162 | improvement_below_cost_buffer;insufficient_unique_flow_hours;unstable_train_test_behavior;weak_win_rate |
| 4 | 92 | REJECTED | BTC:bitcoin-all-time-high-by-december-31-2026:102959890468928530190954086704155483076852880798676895426376704430618826404382:1h:buy_volume_usdc:all:all | +0.00237 | -0.00163 | improvement_below_cost_buffer;insufficient_unique_flow_hours;unstable_train_test_behavior;weak_win_rate |
| 5 | 30 | REJECTED | XRP:will-xrp-dip-to-1-in-april-2026:100486776543789753604313132714049178819643221848759068035081318302712172295545:1h:whale_flow_score:all:all | +0.00325 | -0.00075 | improvement_below_cost_buffer;insufficient_unique_flow_hours;low_sample_count;unstable_train_test_behavior |

## Recommended Next Data Action

- Priority: widen historical coverage before changing thresholds; current edge does not clear the cost buffer.
- Keep filters unchanged and collect more diverse market regimes to retest improvement stability.

## Guardrails

- Exploratory research only.
- Not tradeable.
- No live trading or execution.
