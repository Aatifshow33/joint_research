# Cross-Venue Prediction-Market Arbitrage (Detection Layer)

A **research / detection** layer for cross-venue prediction-market arbitrage
(Polymarket × Kalshi). It does **not** place orders. Its job is to answer the
question that decides whether this strategy is worth wiring to live capital:

> How often do cross-venue prediction-market spreads clear realistic,
> **fee-aware** thresholds at sizes a small ($200) account can actually fill?

## Why this is the edge worth measuring

Buying one YES and one NO on the *same* event guarantees a $1 payout regardless
of outcome. If the pair can be acquired across two venues for less than $1
*after fees*, the difference is locked-in profit that does not depend on
predicting direction — unlike the breakout/mean-reversion and lead-lag work,
which did not survive fees / multiple-testing correction. The whole game is
fees and matching, so this layer models both explicitly.

## Package layout

`src/joint_research/predmarket_arb/`

| Module | Responsibility | Network? |
| --- | --- | --- |
| `fees.py` | Venue fee models (Kalshi non-linear, ceil-to-cent; Polymarket flat) | no |
| `types.py` | `BinaryMarketQuote` value type | no |
| `detector.py` | Fee-aware, bankroll-aware evaluation of a matched pair | no |
| `matcher.py` | Cross-venue market matching (manual map + title overlap) | no |
| `kalshi_client.py` | Kalshi payload projection (pure) + thin live fetch | fetch only |
| `polymarket_quotes.py` | Polymarket Gamma payload projection (pure) | no |
| `scan.py` | Orchestrates a pass; writes JSON/CSV/MD artifacts | no |
| `cli.py` | `predmarket-arb scan` entrypoint | optional |

The economics are pure and deterministic; only the thin fetchers touch the
network, so the strategy logic is fully unit-tested offline.

## Running a scan

Offline (fixtures, the default research/CI path):

```bash
predmarket-arb scan \
  --fixtures-dir tests/fixtures/predmarket_arb \
  --bankroll 200 \
  --min-edge 0.02
# or, without installing the console script:
python -m joint_research.predmarket_arb.cli scan --fixtures-dir tests/fixtures/predmarket_arb
```

Live (Kalshi fetch; Polymarket left to the warehouse ingest path):

```bash
predmarket-arb scan --live --bankroll 200
```

Artifacts are written to `artifacts/research/predmarket_arb/`:
`predmarket_arb_scan.json`, `predmarket_arb_scan.csv`, `predmarket_arb_summary.md`.

## Reason-code contract (frozen)

Every matched pair is evaluated and retained, actionable or not, so the
artifacts measure near-misses too:

| reason_code | meaning |
| --- | --- |
| `actionable` | net edge ≥ `--min-edge` **and** net profit ≥ `--min-profit` |
| `negative_gross_edge` | cheaper direction still costs ≥ $1 before fees |
| `edge_below_fee_threshold` | positive gross edge, but fees push net edge under the bar |
| `profit_below_minimum` | edge clears the bar but sized profit is under `--min-profit` |
| `bankroll_too_small` | cannot afford even one fee-inclusive pair |
| `zero_available_size` | no quoted depth on at least one leg |

## Fee model

* **Kalshi** general trading fee: `ceil_to_cent(0.07 · C · P · (1 − P))` per
  fill — large and non-linear, peaking at the 50¢ midpoint. Rate is
  configurable for the lower-fee index markets.
* **Polymarket**: no taker trading fee today; a configurable flat per-order
  cost absorbs gas/relayer assumptions.

## Known limits (before any live capital)

* **Order-book depth is not modeled for Polymarket.** The Gamma `/markets`
  payload carries marks, not book depth, so available size defaults to an
  assumed constant (`available_size` can be injected from a CLOB snapshot).
  Real fillable size must come from the CLOB book before sizing is trusted.
* **Matching is conservative but not verified.** A wrong match is directional
  risk masquerading as arb. Use `--manual-map` (a trusted, human-reviewed
  `{kalshi_key: polymarket_key}` JSON) for anything that would see capital.
* **Single snapshot, no execution / leg-risk model.** Spreads can close between
  the two fills; this layer measures opportunity frequency, not realized fills.
* **Kalshi-only live fetch.** The live Polymarket side is intentionally routed
  through the warehouse ingest path rather than a guessed endpoint shape.
