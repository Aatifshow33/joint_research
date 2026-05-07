# Derivatives-Regime Artifact Review

Status: RESEARCH-ONLY ARTIFACT REVIEW (NON-EXECUTING)

## 1. Current research posture

Derivatives-regime is the active next research lane after wallet-flow was closed as exploratory-only. Current committed derivatives-regime evidence remains exploratory and non-tradeable.

## 2. Artifact files reviewed

- `artifacts/research/derivatives_regime/derivatives_regime_results.csv`
- `artifacts/research/derivatives_regime/derivatives_regime_candidates.json`
- `artifacts/research/derivatives_regime/derivatives_regime_summary.md`

## 3. Grade/count summary

From committed `derivatives_regime_results.csv`:

- Segment rows tested: 581
- SIMULATION_READY: 0
- WATCHLIST: 0
- WEAK: 158
- REJECTED: 423

Additional filter-reason distribution:

- passed: 72
- train_test_direction_mismatch: 172
- insufficient_samples: 269
- no_improvement_over_baseline: 68

## 4. Candidate summary

From committed `derivatives_regime_candidates.json`:

- Candidate rows: 20
- Candidate grades: WEAK (20), SIMULATION_READY (0), WATCHLIST (0), REJECTED (0)
- Top rows are primarily BTC/ETH funding-intensity or funding-direction segments with positive baseline improvement but insufficient strength/stability to clear higher grades.

## 5. What looks promising

- Some segments show positive test improvement over baseline in both BTC and ETH slices.
- Funding-intensity segmentation appears repeatedly in top-ranked rows, suggesting the lane has directional signal structure worth further research.
- The committed summary already enforces guardrails and preserves non-tradeable framing.

## 6. What remains blocked or weak

- No SIMULATION_READY and no WATCHLIST rows in committed results.
- High volume of REJECTED rows and significant train/test direction mismatch.
- Many rows fail minimum sample requirements, indicating limited robustness across regime slices.
- Current evidence is not strong enough for promotion or simulation enablement.

## 7. Explicit research-only statement

This review is research-only and based strictly on committed artifacts. It does not mark derivatives-regime as tradeable.

## 8. Explicit non-authorization statement

This review does not authorize ingestion, artifact refresh, paper trading, live trading, threshold loosening, or candidate promotion.

## 9. Recommended next phase

Recommended next phase: a diagnostics-only derivatives-regime evidence-strengthening plan that targets sample sufficiency and train/test stability gaps while remaining non-executing and non-tradeable.
