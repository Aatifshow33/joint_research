# Derivatives-Regime Evidence-Strengthening Plan

Status: RESEARCH-ONLY PLAN (NON-EXECUTING)

## 1. Current posture

Derivatives-regime is the active next research lane after wallet-flow was closed as exploratory-only. The current derivatives-regime lane remains exploratory and not tradeable.

## 2. Evidence from Phase 4.63

Source: `docs/derivatives_regime_artifact_review.md` (committed-artifact review only)

- Segment rows tested: 581
- SIMULATION_READY: 0
- WATCHLIST: 0
- WEAK: 158
- REJECTED: 423
- Candidate rows: 20
- Candidate grades: WEAK only
- Additional blocker evidence from filter reasons:
  - insufficient_samples: 269
  - train_test_direction_mismatch: 172
  - no_improvement_over_baseline: 68

## 3. Main blockers

- Sample sufficiency gaps across regime segments and horizons.
- Train/test direction mismatch in many segments, reducing stability confidence.
- Insufficient strength and stability to justify promotion or simulation-readiness.

## 4. Diagnostics-only next steps

1. Segment coverage diagnostics:
   define a diagnostics pass that breaks sample counts by asset, horizon, regime type, and regime bucket to identify where insufficiency is concentrated.
2. Stability diagnostics:
   add read-only diagnostics that profile train/test direction agreement by segment family and rank mismatch-prone combinations.
3. Strength diagnostics:
   produce diagnostics-only distributions for improvement-over-baseline and win-rate by segment to distinguish marginal from durable signal pockets.
4. Candidate quality diagnostics:
   add a read-only candidate-quality rubric report that flags candidate rows failing stability or sufficiency checks.
5. Prioritization output:
   produce a diagnostics summary that ranks next research targets by expected evidence gain, without changing grades or artifacts.

## 5. What not to do

- Do not run ingestion.
- Do not refresh artifacts.
- Do not rerun research outputs.
- Do not enable paper trading.
- Do not enable live trading.
- Do not loosen thresholds.
- Do not promote candidates.
- Do not mark derivatives-regime as tradeable.

## 6. Acceptance criteria for future research deepening

- A diagnostics package exists that clearly attributes rejection pressure to specific segment/horizon coverage and stability causes.
- Sample sufficiency diagnostics identify concrete low-support areas and clear high-support areas.
- Train/test direction mismatch diagnostics isolate stable versus unstable segment groups.
- Strength diagnostics show whether any segments have repeatable, non-marginal improvement patterns.
- A documented evidence gate exists for when a future deepening phase is justified, while still preserving non-tradeable policy.

## 7. Explicit non-authorization statement

This plan is research-only and does not authorize ingestion, artifact refresh, paper trading, live trading, threshold loosening, or candidate promotion.

## 8. Recommended next implementation phase

Recommended next phase: implement a diagnostics-only derivatives-regime evidence-attribution report that consumes existing committed artifacts and emits non-executing, non-promotional analysis outputs only.
