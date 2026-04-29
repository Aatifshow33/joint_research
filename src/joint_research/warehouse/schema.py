"""Warehouse table schemas.

Every row in every table carries the same five common columns plus
table-specific columns. Schemas are declared as ``pyarrow.Schema`` so
the writer can validate at write time and DuckDB picks up the types
without inference.
"""

from __future__ import annotations

from dataclasses import dataclass

import pyarrow as pa


def common_columns() -> list[pa.Field]:
    """Columns required on every warehouse table.

    - ``event_time_ns``: source clock (exchange/API). Use for joins.
    - ``ingest_time_ns``: our clock at write time. Use for ops/observability.
    - ``source``: stable identifier for the upstream client (e.g. ``gamma.events``).
    - ``payload_hash``: sha256 hex digest of the canonical JSON payload. Used
      for deduplication when the same row is ingested twice.
    - ``payload_json``: raw JSON of the source row as a UTF-8 string. The
      schema projection columns are derived; this is the authoritative copy.
    """

    return [
        pa.field("event_time_ns", pa.int64(), nullable=False),
        pa.field("ingest_time_ns", pa.int64(), nullable=False),
        pa.field("source", pa.string(), nullable=False),
        pa.field("payload_hash", pa.string(), nullable=False),
        pa.field("payload_json", pa.string(), nullable=False),
    ]


@dataclass(frozen=True)
class TableSchema:
    name: str
    schema: pa.Schema
    primary_key: tuple[str, ...]
    """Columns that uniquely identify a row for dedup. Always includes ``payload_hash``."""

    def validate_table(self, table: pa.Table) -> None:
        if table.schema != self.schema:
            expected = self.schema.to_string()
            actual = table.schema.to_string()
            raise ValueError(
                f"schema_mismatch:table={self.name}\nexpected:\n{expected}\nactual:\n{actual}"
            )


def _table(name: str, extra_fields: list[pa.Field], primary_key: tuple[str, ...]) -> TableSchema:
    schema = pa.schema(common_columns() + extra_fields)
    if "payload_hash" not in primary_key:
        primary_key = primary_key + ("payload_hash",)
    return TableSchema(name=name, schema=schema, primary_key=primary_key)


# ---------------------------------------------------------------------------
# Polymarket Gamma events
# ---------------------------------------------------------------------------

POLYMARKET_GAMMA_EVENTS = _table(
    name="polymarket_gamma_events",
    extra_fields=[
        pa.field("event_id", pa.string(), nullable=False),
        pa.field("slug", pa.string(), nullable=True),
        pa.field("title", pa.string(), nullable=True),
        pa.field("category", pa.string(), nullable=True),
        pa.field("active", pa.bool_(), nullable=True),
        pa.field("closed", pa.bool_(), nullable=True),
        pa.field("archived", pa.bool_(), nullable=True),
        pa.field("start_date_iso", pa.string(), nullable=True),
        pa.field("end_date_iso", pa.string(), nullable=True),
        pa.field("volume_usd", pa.float64(), nullable=True),
        pa.field("liquidity_usd", pa.float64(), nullable=True),
        pa.field("market_count", pa.int32(), nullable=True),
    ],
    primary_key=("event_id", "event_time_ns"),
)


# ---------------------------------------------------------------------------
# Crypto OHLCV (Binance klines, but venue-agnostic schema)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Polymarket crypto markets (one row per market snapshot — versioned by event_time_ns)
# ---------------------------------------------------------------------------

POLYMARKET_CRYPTO_MARKETS = _table(
    name="polymarket_crypto_markets",
    extra_fields=[
        pa.field("market_id", pa.string(), nullable=False),
        pa.field("condition_id", pa.string(), nullable=True),
        pa.field("question", pa.string(), nullable=True),
        pa.field("slug", pa.string(), nullable=True),
        pa.field("event_id", pa.string(), nullable=True),
        pa.field("yes_token_id", pa.string(), nullable=True),
        pa.field("no_token_id", pa.string(), nullable=True),
        pa.field("active", pa.bool_(), nullable=True),
        pa.field("closed", pa.bool_(), nullable=True),
        pa.field("archived", pa.bool_(), nullable=True),
        pa.field("end_date_iso", pa.string(), nullable=True),
        pa.field("volume_total_usd", pa.float64(), nullable=True),
        pa.field("volume_24h_usd", pa.float64(), nullable=True),
        pa.field("volume_1wk_usd", pa.float64(), nullable=True),
        pa.field("volume_1mo_usd", pa.float64(), nullable=True),
        pa.field("liquidity_usd", pa.float64(), nullable=True),
        pa.field("last_trade_price", pa.float64(), nullable=True),
        pa.field("crypto_asset_tag", pa.string(), nullable=True),
    ],
    primary_key=("market_id", "event_time_ns"),
)


# ---------------------------------------------------------------------------
# Polymarket price history (one row per (token_id, t) sample)
# ---------------------------------------------------------------------------

POLYMARKET_PRICE_HISTORY = _table(
    name="polymarket_price_history",
    extra_fields=[
        pa.field("token_id", pa.string(), nullable=False),
        pa.field("market_id", pa.string(), nullable=True),
        pa.field("outcome", pa.string(), nullable=True),
        pa.field("price", pa.float64(), nullable=False),
        pa.field("interval_label", pa.string(), nullable=True),
        pa.field("fidelity_minutes", pa.int32(), nullable=True),
    ],
    primary_key=("token_id", "event_time_ns"),
)


# ---------------------------------------------------------------------------
# Polymarket wallet activity (one row per whale trade event)
# ---------------------------------------------------------------------------

POLYMARKET_WALLET_ACTIVITY = _table(
    name="polymarket_wallet_activity",
    extra_fields=[
        pa.field("wallet_address", pa.string(), nullable=False),
        pa.field("activity_type", pa.string(), nullable=True),
        pa.field("transaction_hash", pa.string(), nullable=True),
        pa.field("condition_id", pa.string(), nullable=True),
        pa.field("market_slug", pa.string(), nullable=True),
        pa.field("event_slug", pa.string(), nullable=True),
        pa.field("title", pa.string(), nullable=True),
        pa.field("token_id", pa.string(), nullable=True),
        pa.field("side", pa.string(), nullable=True),
        pa.field("outcome", pa.string(), nullable=True),
        pa.field("outcome_index", pa.int32(), nullable=True),
        pa.field("size_base", pa.float64(), nullable=True),
        pa.field("size_usdc", pa.float64(), nullable=True),
        pa.field("price", pa.float64(), nullable=True),
        pa.field("source_record_id", pa.string(), nullable=True),
    ],
    primary_key=("wallet_address", "source_record_id"),
)

# ---------------------------------------------------------------------------
# Polymarket wallet/trader flow (trade + optional copy-flow evidence)
# ---------------------------------------------------------------------------

POLYMARKET_WALLET_FLOW = _table(
    name="polymarket_wallet_flow",
    extra_fields=[
        pa.field("record_type", pa.string(), nullable=False),
        pa.field("source_record_id", pa.string(), nullable=False),
        pa.field("wallet_address", pa.string(), nullable=True),
        pa.field("leader_wallet", pa.string(), nullable=True),
        pa.field("follower_wallet", pa.string(), nullable=True),
        pa.field("market_id", pa.string(), nullable=True),
        pa.field("condition_id", pa.string(), nullable=True),
        pa.field("token_id", pa.string(), nullable=True),
        pa.field("asset", pa.string(), nullable=True),
        pa.field("side", pa.string(), nullable=True),
        pa.field("action", pa.string(), nullable=True),
        pa.field("size_base", pa.float64(), nullable=True),
        pa.field("notional_usdc", pa.float64(), nullable=True),
        pa.field("price_probability", pa.float64(), nullable=True),
        pa.field("flow_sign", pa.int32(), nullable=True),
        pa.field("is_large_trade", pa.bool_(), nullable=True),
        pa.field("lag_seconds", pa.int32(), nullable=True),
        pa.field("relationship_confidence", pa.float64(), nullable=True),
        pa.field("relationship_status", pa.string(), nullable=True),
    ],
    primary_key=("record_type", "source_record_id", "event_time_ns"),
)


# ---------------------------------------------------------------------------
# Stock OHLCV (yfinance default; venue-agnostic schema)
# ---------------------------------------------------------------------------

STOCK_OHLCV = _table(
    name="stock_ohlcv",
    extra_fields=[
        pa.field("venue", pa.string(), nullable=False),
        pa.field("symbol", pa.string(), nullable=False),
        pa.field("interval", pa.string(), nullable=False),
        pa.field("open_time_ns", pa.int64(), nullable=False),
        pa.field("close_time_ns", pa.int64(), nullable=False),
        pa.field("open", pa.float64(), nullable=False),
        pa.field("high", pa.float64(), nullable=False),
        pa.field("low", pa.float64(), nullable=False),
        pa.field("close", pa.float64(), nullable=False),
        pa.field("adj_close", pa.float64(), nullable=True),
        pa.field("volume", pa.float64(), nullable=False),
        pa.field("dividend", pa.float64(), nullable=True),
        pa.field("split_ratio", pa.float64(), nullable=True),
    ],
    primary_key=("venue", "symbol", "interval", "open_time_ns"),
)

# ---------------------------------------------------------------------------
# Macro time series (FRED default; one row per (series_id, observation date))
# ---------------------------------------------------------------------------

MACRO_SERIES = _table(
    name="macro_series",
    extra_fields=[
        pa.field("source_system", pa.string(), nullable=False),
        pa.field("series_id", pa.string(), nullable=False),
        pa.field("value", pa.float64(), nullable=True),
        pa.field("units", pa.string(), nullable=True),
        pa.field("frequency", pa.string(), nullable=True),
    ],
    primary_key=("source_system", "series_id", "event_time_ns"),
)


CRYPTO_OHLCV = _table(
    name="crypto_ohlcv",
    extra_fields=[
        pa.field("venue", pa.string(), nullable=False),
        pa.field("symbol", pa.string(), nullable=False),
        pa.field("interval", pa.string(), nullable=False),
        pa.field("open_time_ns", pa.int64(), nullable=False),
        pa.field("close_time_ns", pa.int64(), nullable=False),
        pa.field("open", pa.float64(), nullable=False),
        pa.field("high", pa.float64(), nullable=False),
        pa.field("low", pa.float64(), nullable=False),
        pa.field("close", pa.float64(), nullable=False),
        pa.field("volume_base", pa.float64(), nullable=False),
        pa.field("volume_quote", pa.float64(), nullable=False),
        pa.field("num_trades", pa.int64(), nullable=True),
        pa.field("taker_buy_volume_base", pa.float64(), nullable=True),
        pa.field("taker_buy_volume_quote", pa.float64(), nullable=True),
    ],
    primary_key=("venue", "symbol", "interval", "open_time_ns"),
)

CRYPTO_DERIVATIVES = _table(
    name="crypto_derivatives",
    extra_fields=[
        pa.field("venue", pa.string(), nullable=False),
        pa.field("record_type", pa.string(), nullable=False),
        pa.field("symbol", pa.string(), nullable=False),
        pa.field("funding_time_ns", pa.int64(), nullable=True),
        pa.field("funding_rate", pa.float64(), nullable=True),
        pa.field("mark_price", pa.float64(), nullable=True),
        pa.field("spot_price", pa.float64(), nullable=True),
        pa.field("basis_pct", pa.float64(), nullable=True),
    ],
    primary_key=("venue", "record_type", "symbol", "event_time_ns"),
)


ALL_TABLES: dict[str, TableSchema] = {
    POLYMARKET_GAMMA_EVENTS.name: POLYMARKET_GAMMA_EVENTS,
    POLYMARKET_CRYPTO_MARKETS.name: POLYMARKET_CRYPTO_MARKETS,
    POLYMARKET_PRICE_HISTORY.name: POLYMARKET_PRICE_HISTORY,
    POLYMARKET_WALLET_ACTIVITY.name: POLYMARKET_WALLET_ACTIVITY,
    POLYMARKET_WALLET_FLOW.name: POLYMARKET_WALLET_FLOW,
    STOCK_OHLCV.name: STOCK_OHLCV,
    MACRO_SERIES.name: MACRO_SERIES,
    CRYPTO_OHLCV.name: CRYPTO_OHLCV,
    CRYPTO_DERIVATIVES.name: CRYPTO_DERIVATIVES,
}
