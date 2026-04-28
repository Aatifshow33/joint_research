# joint_research

Joint Polymarket × crypto research warehouse and pattern-discovery toolkit.

Sits between two paper-trading systems:

- [`polymarket-arb`](../polymarket-arb) — Polymarket scanner, copier detection, paper-trade simulator.
- [`cryp`](../cryp) — deterministic crypto signal/execution scaffold.

This package owns **what neither of them owns today**: time-aligned historical data, cross-system pattern mining, composite-signal construction, and an honest backtest harness. The output is a single `ReviewedPolymarketExternalConfirmationSignal` per (asset, timestamp) that flows through the existing handoff envelope — both upstream repos stay unchanged at their public contracts.

## Layout

```
src/joint_research/
├── warehouse/      # Parquet schema, append-only writer, DuckDB views
├── ingest/         # Per-source ingestors (Polymarket Gamma/CLOB/DataAPI/WS, crypto OHLCV/funding)
├── composite/      # Signal selection + aggregation + emitter (later phase)
└── backtest/       # Walk-forward harness + cost model (later phase)
```

Data lives under `data/warehouse/{table}/ingest_date=YYYY-MM-DD/*.parquet` and is gitignored.

## Quickstart

```bash
pip install -e .[dev]
pytest

# First ingestion (live API call, ~10s):
joint-research ingest gamma-events --limit 100
duckdb data/warehouse/manifest.duckdb -c "select count(*) from polymarket_gamma_events"
```

## Design rules

1. **Append-only.** Every ingestion writes a new Parquet file. Existing files are never mutated. Rerunning a backfill is a no-op against duplicate keys; query views deduplicate.
2. **Two timestamps on every row.** `event_time_ns` (source clock) for joins, `ingest_time_ns` (our clock) for ops. All analytics must join on `event_time_ns` to avoid look-ahead.
3. **Raw payload preserved.** Every row carries the full source JSON in a `payload_json` column. Schema columns are projections, not the source of truth.
4. **No DB.** DuckDB queries Parquet directly. No long-running processes, no migrations.
