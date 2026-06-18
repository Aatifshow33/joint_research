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

Live (fetches both venues over the network):

```bash
predmarket-arb scan --live --bankroll 200 --min-profit 0.25
```

Live sourcing notes:
* **Kalshi** — the flat `/markets` feed is mostly auto-generated sports parlays,
  so the live fetch pages the `/events` endpoint with nested markets and keeps
  only two-sided binary markets with real asks (~28k usable markets).
* **Polymarket** — Gamma `/markets` ordered by liquidity; prices use top-of-book
  `bestAsk` (YES) and `1 - bestBid` (NO), falling back to `outcomePrices` marks.
  Gamma caps deep pagination with a 422, which the fetcher treats as end-of-list.

### First real result (2026-06-18)

A live scan over **~28,800 Kalshi × ~816 Polymarket** quotes matched 43 markets
(title-overlap ≥ 0.75) and found genuine, fee-survivable, $200-fillable arbs —
e.g. *"Will ChatGPT be Time Person of the Year in 2026?"* (verified 1.00 match):
~198 contracts, ~$191 capital, **~$6.89 modeled net profit (3.5% net edge)** in a
single snapshot. Most other real matches sat just under the fee threshold or were
depth-capped to a few contracts. Takeaways: the edge is real but **small in
dollar terms at $200**, **depth- and fee-constrained**, and only worth trading on
**resolution-verified** matches.

## Operating model (how this makes money)

1. **Scan continuously**, not once — these markets reprice all day; dislocations
   appear and close. Run on a schedule and alert on actionable rows.
2. **Verify before trading.** Promote each profitable auto-match into the trusted
   `--manual-map` only after confirming both venues resolve the *same* question by
   the same source, criteria, and date. Never trade a `token_overlap` row blind.
3. **Confirm real depth** on both books before sizing (see limits below).
4. **Execution stays manual / gated.** This layer never places orders; you (or a
   later, explicitly-gated execution module) place the paired legs near-simultaneously.
5. **Scale with capital.** Per-opportunity dollar profit scales ~linearly with
   bankroll until venue depth binds; $200 harvests dollars, not hundreds.

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
* **Resolution-criteria risk is the big one.** A 1.00 title match is not proof
  the two venues settle identically (source, cutoff, edge cases). This is what
  turns a "risk-free" pair into directional risk — verify per market.
