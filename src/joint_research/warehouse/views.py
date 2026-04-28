"""DuckDB view registration over the Parquet warehouse.

Notebooks and analytics call ``register_views(con, paths)`` to get a stable
set of named relations. The views deduplicate via ``payload_hash`` so
repeating an ingestion is safe — the latest row per key wins.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from joint_research.warehouse.paths import WarehousePaths
from joint_research.warehouse.schema import ALL_TABLES


def register_views(con: duckdb.DuckDBPyConnection, paths: WarehousePaths) -> None:
    """Create or replace one base view per registered table, plus analytic views."""

    registered: set[str] = set()
    for table in ALL_TABLES.values():
        table_dir = paths.table_dir(table.name)
        if not _has_parquet_files(table_dir):
            # Register an empty stub so downstream queries see the relation.
            _register_empty_stub(con, table)
            continue
        glob = _table_glob(paths.root, table.name)
        pk_cols = ", ".join(table.primary_key)
        con.execute(
            f"""
            CREATE OR REPLACE VIEW {table.name} AS
            WITH src AS (
              SELECT *
              FROM read_parquet('{glob}', hive_partitioning=true)
            ),
            ranked AS (
              SELECT *,
                ROW_NUMBER() OVER (
                  PARTITION BY {pk_cols}
                  ORDER BY ingest_time_ns DESC
                ) AS _rn
              FROM src
            )
            SELECT * EXCLUDE (_rn) FROM ranked WHERE _rn = 1
            """
        )
        registered.add(table.name)

    _register_analytic_views(con)


def _has_parquet_files(table_dir: Path) -> bool:
    if not table_dir.exists():
        return False
    return any(table_dir.rglob("*.parquet"))


def _register_empty_stub(con: duckdb.DuckDBPyConnection, table) -> None:
    """Register an empty relation so downstream views can compile."""

    column_exprs: list[str] = []
    for field in table.schema:
        # NULL casts so the empty relation has the right column types.
        type_sql = _arrow_type_to_duckdb(field.type)
        column_exprs.append(f"CAST(NULL AS {type_sql}) AS {field.name}")
    # Hive partition columns appear on read; mirror them so analytic views
    # that reference base columns don't break.
    column_exprs.append("CAST(NULL AS VARCHAR) AS ingest_date")
    select = ", ".join(column_exprs)
    con.execute(
        f"CREATE OR REPLACE VIEW {table.name} AS SELECT {select} WHERE 1=0"
    )


def _arrow_type_to_duckdb(arrow_type) -> str:
    """Map the small set of pyarrow types we actually use to DuckDB SQL types."""

    s = str(arrow_type)
    if s in {"string", "utf8"}:
        return "VARCHAR"
    if s == "bool":
        return "BOOLEAN"
    if s == "int32":
        return "INTEGER"
    if s == "int64":
        return "BIGINT"
    if s == "double":
        return "DOUBLE"
    return "VARCHAR"


def _register_analytic_views(con: duckdb.DuckDBPyConnection) -> None:
    """Project the base tables into the shapes analytics actually needs."""

    # Crypto OHLCV with simple log-returns. Joins downstream key on
    # (symbol, interval, open_time_ns).
    con.execute(
        """
        CREATE OR REPLACE VIEW crypto_returns AS
        SELECT
          venue,
          symbol,
          interval,
          open_time_ns,
          close_time_ns,
          open,
          high,
          low,
          close,
          volume_base,
          volume_quote,
          ln(close / NULLIF(LAG(close) OVER w, 0)) AS log_return,
          (close - LAG(close) OVER w) / NULLIF(LAG(close) OVER w, 0) AS simple_return,
          ln(high / NULLIF(low, 0)) AS log_range
        FROM crypto_ohlcv
        WINDOW w AS (PARTITION BY venue, symbol, interval ORDER BY open_time_ns)
        """
    )

    # Crypto-relevant Polymarket events. We pick by category and by keywords
    # in title/slug — defensive because Gamma's "category" field is often null.
    con.execute(
        """
        CREATE OR REPLACE VIEW polymarket_crypto_events AS
        SELECT *
        FROM polymarket_gamma_events
        WHERE
          lower(coalesce(category, '')) IN ('crypto', 'cryptocurrency')
          OR regexp_matches(lower(coalesce(title, '')),
              '\\b(bitcoin|btc|ethereum|eth|solana|sol|xrp|crypto|stablecoin|sec|etf)\\b')
          OR regexp_matches(lower(coalesce(slug, '')),
              '\\b(bitcoin|btc|ethereum|eth|solana|sol|xrp|crypto|stablecoin|sec|etf)\\b')
        """
    )

    # Hourly bucketing of Polymarket price history (last sample within the
    # hour wins). Joins to crypto returns at the same timestamp so we can
    # compute Δprob lead-lag against future crypto returns.
    con.execute(
        """
        CREATE OR REPLACE VIEW polymarket_price_history_hourly AS
        WITH bucketed AS (
          SELECT
            token_id,
            market_id,
            -- Floor to the UTC hour. Subtract modulo instead of divide-then-
            -- multiply: BIGINT/BIGINT in DuckDB returns DOUBLE for values
            -- this large, which silently drops the rounding.
            event_time_ns - (event_time_ns % 3600000000000) AS bucket_open_time_ns,
            price,
            ROW_NUMBER() OVER (
              PARTITION BY token_id, event_time_ns - (event_time_ns % 3600000000000)
              ORDER BY event_time_ns DESC
            ) AS rn
          FROM polymarket_price_history
        )
        SELECT
          token_id,
          market_id,
          bucket_open_time_ns AS open_time_ns,
          price
        FROM bucketed
        WHERE rn = 1
        """
    )

    # ----- Stocks (daily) -----

    # Daily log returns per stock symbol. Joins downstream key on
    # (venue, symbol, open_time_ns).
    con.execute(
        """
        CREATE OR REPLACE VIEW stock_returns_daily AS
        SELECT
          venue,
          symbol,
          interval,
          open_time_ns,
          open,
          high,
          low,
          close,
          adj_close,
          volume,
          ln(close / NULLIF(LAG(close) OVER w, 0)) AS log_return,
          (close - LAG(close) OVER w) / NULLIF(LAG(close) OVER w, 0) AS simple_return,
          ln(NULLIF(adj_close, 0) / NULLIF(LAG(adj_close) OVER w, 0)) AS adj_log_return
        FROM stock_ohlcv
        WHERE interval = '1d'
        WINDOW w AS (PARTITION BY venue, symbol, interval ORDER BY open_time_ns)
        """
    )

    # ----- Macro state (the economist's daily snapshot) -----

    # For each macro series, compute its rolling percentile vs its own history
    # (1y = 252 trading days, 5y = 1260) — non-stationary series are the norm
    # so we use percentile rank against trailing window, not against a fixed
    # historical mean.
    con.execute(
        """
        CREATE OR REPLACE VIEW macro_series_with_percentiles AS
        SELECT
          source_system,
          series_id,
          event_time_ns,
          value,
          units,
          frequency,
          PERCENT_RANK() OVER w_1y AS pct_rank_1y,
          PERCENT_RANK() OVER w_5y AS pct_rank_5y,
          AVG(value) OVER w_1y AS mean_1y,
          STDDEV(value) OVER w_1y AS stddev_1y,
          (value - LAG(value, 1)  OVER w_all) AS change_1d,
          (value - LAG(value, 5)  OVER w_all) AS change_5d,
          (value - LAG(value, 21) OVER w_all) AS change_1m
        FROM macro_series
        WHERE value IS NOT NULL
        WINDOW
          w_all AS (PARTITION BY source_system, series_id ORDER BY event_time_ns),
          w_1y  AS (PARTITION BY source_system, series_id ORDER BY event_time_ns
                    ROWS BETWEEN 251 PRECEDING AND CURRENT ROW),
          w_5y  AS (PARTITION BY source_system, series_id ORDER BY event_time_ns
                    ROWS BETWEEN 1259 PRECEDING AND CURRENT ROW)
        """
    )

    # Pivot the latest values for the key macro series into a single per-day
    # row. The agent crew (Researcher) consumes this view directly.
    con.execute(
        """
        CREATE OR REPLACE VIEW macro_state_daily AS
        WITH latest AS (
          SELECT
            event_time_ns,
            event_time_ns - (event_time_ns % 86400000000000) AS day_open_time_ns,
            series_id,
            value,
            pct_rank_1y,
            pct_rank_5y,
            change_1d,
            change_5d
          FROM macro_series_with_percentiles
        ),
        pivoted AS (
          SELECT
            day_open_time_ns AS open_time_ns,
            MAX(CASE WHEN series_id = 'DFF'      THEN value END) AS fed_funds,
            MAX(CASE WHEN series_id = 'DGS2'     THEN value END) AS yield_2y,
            MAX(CASE WHEN series_id = 'DGS10'    THEN value END) AS yield_10y,
            MAX(CASE WHEN series_id = 'DGS30'    THEN value END) AS yield_30y,
            MAX(CASE WHEN series_id = 'T10YIE'   THEN value END) AS breakeven_10y,
            MAX(CASE WHEN series_id = 'DTWEXBGS' THEN value END) AS dxy_broad,
            MAX(CASE WHEN series_id = 'VIXCLS'   THEN value END) AS vix,
            MAX(CASE WHEN series_id = 'VIXCLS'   THEN pct_rank_1y END) AS vix_pct_1y,
            MAX(CASE WHEN series_id = 'NFCI'     THEN value END) AS nfci,
            MAX(CASE WHEN series_id = 'NFCI'     THEN pct_rank_1y END) AS nfci_pct_1y,
            MAX(CASE WHEN series_id = 'UNRATE'   THEN value END) AS unrate,
            MAX(CASE WHEN series_id = 'CPIAUCSL' THEN change_1m END) AS cpi_change_1m
          FROM latest
          GROUP BY day_open_time_ns
        )
        SELECT
          open_time_ns,
          fed_funds,
          yield_2y,
          yield_10y,
          yield_30y,
          breakeven_10y,
          (yield_10y - yield_2y) AS curve_2s10s,
          (yield_30y - yield_10y) AS curve_10s30s,
          (yield_10y - breakeven_10y) AS real_10y,
          dxy_broad,
          vix,
          vix_pct_1y,
          nfci,
          nfci_pct_1y,
          unrate,
          cpi_change_1m,
          -- Regime label: a defensible 4-state classification grounded in
          -- standard macro-economist heuristics. Curve inversion + high VIX
          -- = recession risk; loose conditions + steep curve = goldilocks.
          CASE
            WHEN nfci_pct_1y IS NULL OR vix_pct_1y IS NULL THEN 'unknown'
            WHEN nfci_pct_1y >= 0.80 AND vix_pct_1y >= 0.80 THEN 'risk_off'
            WHEN (yield_10y - yield_2y) < 0 AND vix_pct_1y >= 0.60 THEN 'recession_risk'
            WHEN nfci_pct_1y <= 0.30 AND vix_pct_1y <= 0.40 THEN 'goldilocks'
            ELSE 'neutral'
          END AS regime
        FROM pivoted
        ORDER BY open_time_ns
        """
    )

    # ----- Whale wallet activity on crypto markets -----

    # Filter wallet activity to crypto-relevant markets and pick out the
    # YES side of each trade. We keep BUY and SELL as a directional column.
    # Joins to the matching crypto bar at trade time so the event study
    # already has the underlying close + forward returns.
    con.execute(
        """
        CREATE OR REPLACE VIEW whale_crypto_trades AS
        WITH crypto_market_keys AS (
          SELECT DISTINCT
            condition_id,
            crypto_asset_tag AS asset,
            yes_token_id,
            no_token_id,
            question,
            volume_total_usd
          FROM polymarket_crypto_markets
          WHERE condition_id IS NOT NULL
            AND crypto_asset_tag IS NOT NULL
        ),
        crypto_with_forwards AS (
          -- Compute forward returns once on the crypto returns time series,
          -- so a hot hour with many whale trades doesn't corrupt the LEAD.
          SELECT
            symbol,
            interval,
            open_time_ns,
            close,
            log_return,
            LEAD(log_return, 1)  OVER (PARTITION BY symbol, interval ORDER BY open_time_ns) AS log_return_next_1h,
            LEAD(log_return, 4)  OVER (PARTITION BY symbol, interval ORDER BY open_time_ns) AS log_return_next_4h,
            LEAD(log_return, 24) OVER (PARTITION BY symbol, interval ORDER BY open_time_ns) AS log_return_next_24h
          FROM crypto_returns
          WHERE interval = '1h'
        ),
        joined AS (
          SELECT
            a.wallet_address,
            a.event_time_ns AS trade_time_ns,
            a.activity_type,
            a.side,
            a.outcome,
            a.size_base,
            a.size_usdc,
            a.price AS poly_trade_price,
            m.asset,
            m.condition_id,
            m.yes_token_id,
            m.question,
            m.volume_total_usd AS market_volume_total_usd,
            a.event_time_ns - (a.event_time_ns % 3600000000000) AS trade_hour_ns
          FROM polymarket_wallet_activity a
          JOIN crypto_market_keys m ON m.condition_id = a.condition_id
        )
        SELECT
          j.wallet_address,
          j.asset,
          j.condition_id,
          j.yes_token_id,
          j.question,
          j.activity_type,
          j.side,
          j.outcome,
          j.poly_trade_price,
          j.size_base,
          j.size_usdc,
          j.trade_time_ns,
          j.trade_hour_ns,
          r.symbol AS crypto_symbol,
          r.close AS crypto_close_at_trade,
          r.log_return AS crypto_log_return_at_trade,
          r.log_return_next_1h AS crypto_log_return_next_1h_at_trade,
          r.log_return_next_4h AS crypto_log_return_next_4h_at_trade,
          r.log_return_next_24h AS crypto_log_return_next_24h_at_trade
        FROM joined j
        LEFT JOIN crypto_with_forwards r
          ON r.symbol = j.asset || 'USDT'
         AND r.open_time_ns = j.trade_hour_ns
        """
    )

    # ----- Daily aggregations -----

    # Daily crypto returns: bucket hourly bars to UTC days, take last close as
    # the day's close, then compute daily log returns from prior-day close.
    con.execute(
        """
        CREATE OR REPLACE VIEW crypto_returns_daily AS
        WITH hourly AS (
          SELECT
            venue,
            symbol,
            interval,
            open_time_ns,
            close,
            volume_base,
            volume_quote,
            -- Floor to UTC day (1d = 86_400_000_000_000 ns)
            open_time_ns - (open_time_ns % 86400000000000) AS day_open_time_ns,
            ROW_NUMBER() OVER (
              PARTITION BY venue, symbol, interval,
                          open_time_ns - (open_time_ns % 86400000000000)
              ORDER BY open_time_ns DESC
            ) AS rn_last_in_day,
            ROW_NUMBER() OVER (
              PARTITION BY venue, symbol, interval,
                          open_time_ns - (open_time_ns % 86400000000000)
              ORDER BY open_time_ns ASC
            ) AS rn_first_in_day
          FROM crypto_ohlcv
          WHERE interval = '1h'
        ),
        daily_close AS (
          SELECT venue, symbol, day_open_time_ns AS open_time_ns, close AS day_close
          FROM hourly WHERE rn_last_in_day = 1
        ),
        daily_open AS (
          SELECT venue, symbol, day_open_time_ns AS open_time_ns, close AS day_open
          FROM hourly WHERE rn_first_in_day = 1
        ),
        daily_vol AS (
          SELECT venue, symbol,
                 day_open_time_ns AS open_time_ns,
                 sum(volume_base) AS volume_base_day,
                 sum(volume_quote) AS volume_quote_day
          FROM hourly
          GROUP BY venue, symbol, day_open_time_ns
        )
        SELECT
          c.venue,
          c.symbol,
          c.open_time_ns,
          o.day_open AS open,
          c.day_close AS close,
          v.volume_base_day AS volume_base,
          v.volume_quote_day AS volume_quote,
          ln(c.day_close / NULLIF(LAG(c.day_close) OVER w, 0)) AS log_return,
          (c.day_close - LAG(c.day_close) OVER w) / NULLIF(LAG(c.day_close) OVER w, 0) AS simple_return
        FROM daily_close c
        JOIN daily_open o USING (venue, symbol, open_time_ns)
        JOIN daily_vol v USING (venue, symbol, open_time_ns)
        WINDOW w AS (PARTITION BY c.venue, c.symbol ORDER BY c.open_time_ns)
        """
    )

    # Daily Polymarket price: last sample within each UTC day per token.
    con.execute(
        """
        CREATE OR REPLACE VIEW polymarket_price_history_daily AS
        WITH bucketed AS (
          SELECT
            token_id,
            market_id,
            event_time_ns - (event_time_ns % 86400000000000) AS bucket_open_time_ns,
            price,
            ROW_NUMBER() OVER (
              PARTITION BY token_id,
                          event_time_ns - (event_time_ns % 86400000000000)
              ORDER BY event_time_ns DESC
            ) AS rn
          FROM polymarket_price_history
        )
        SELECT
          token_id,
          market_id,
          bucket_open_time_ns AS open_time_ns,
          price
        FROM bucketed
        WHERE rn = 1
        """
    )

    # Daily per-token alignment view: one row per (token_id, day) with daily
    # crypto returns at multiple forward lags (1d, 3d, 7d, 14d).
    con.execute(
        """
        CREATE OR REPLACE VIEW polymarket_token_returns_aligned_daily AS
        WITH market_meta AS (
          SELECT
            yes_token_id,
            market_id,
            question,
            crypto_asset_tag AS asset,
            end_date_iso,
            volume_1mo_usd,
            volume_total_usd
          FROM polymarket_crypto_markets
          WHERE yes_token_id IS NOT NULL
            AND crypto_asset_tag IS NOT NULL
        ),
        poly_daily AS (
          SELECT p.token_id, p.market_id, p.open_time_ns, p.price,
                 m.asset, m.question, m.end_date_iso,
                 m.volume_1mo_usd, m.volume_total_usd
          FROM polymarket_price_history_daily p
          JOIN market_meta m ON p.token_id = m.yes_token_id
        )
        SELECT
          p.asset,
          p.token_id,
          p.market_id,
          p.question,
          p.end_date_iso,
          p.volume_1mo_usd,
          p.open_time_ns,
          p.price AS poly_yes_price,
          p.price - LAG(p.price) OVER w AS poly_price_change,
          r.symbol AS crypto_symbol,
          r.close AS crypto_close,
          r.log_return AS crypto_log_return,
          LEAD(r.log_return, 1) OVER w AS crypto_log_return_next_1d,
          LEAD(r.log_return, 3) OVER w AS crypto_log_return_next_3d,
          LEAD(r.log_return, 7) OVER w AS crypto_log_return_next_7d,
          LEAD(r.log_return, 14) OVER w AS crypto_log_return_next_14d
        FROM poly_daily p
        LEFT JOIN crypto_returns_daily r
          ON r.symbol = p.asset || 'USDT'
         AND r.open_time_ns = p.open_time_ns
        WINDOW w AS (PARTITION BY p.token_id ORDER BY p.open_time_ns)
        """
    )

    # ----- Hourly aggregations (existing) -----

    # Per-token alignment view: one row per (token_id, hour) joined to the
    # matching crypto bar with forward returns at multiple lags. This is the
    # research-grade view that downstream lead-lag analysis runs against.
    # The single-top-token alignment view further down stays as a convenience
    # for quick spot checks.
    con.execute(
        """
        CREATE OR REPLACE VIEW polymarket_token_returns_aligned AS
        WITH market_meta AS (
          SELECT
            yes_token_id,
            market_id,
            question,
            crypto_asset_tag AS asset,
            end_date_iso,
            volume_1mo_usd,
            volume_total_usd
          FROM polymarket_crypto_markets
          WHERE yes_token_id IS NOT NULL
            AND crypto_asset_tag IS NOT NULL
        ),
        poly_hourly AS (
          SELECT p.token_id, p.market_id, p.open_time_ns, p.price,
                 m.asset, m.question, m.end_date_iso,
                 m.volume_1mo_usd, m.volume_total_usd
          FROM polymarket_price_history_hourly p
          JOIN market_meta m ON p.token_id = m.yes_token_id
        )
        SELECT
          p.asset,
          p.token_id,
          p.market_id,
          p.question,
          p.end_date_iso,
          p.volume_1mo_usd,
          p.open_time_ns,
          p.price AS poly_yes_price,
          p.price - LAG(p.price) OVER w AS poly_price_change,
          r.symbol AS crypto_symbol,
          r.close AS crypto_close,
          r.log_return AS crypto_log_return,
          LEAD(r.log_return, 1) OVER w AS crypto_log_return_next_1h,
          LEAD(r.log_return, 4) OVER w AS crypto_log_return_next_4h,
          LEAD(r.log_return, 24) OVER w AS crypto_log_return_next_24h,
          LAG(r.log_return, 1) OVER w AS crypto_log_return_prev_1h,
          LAG(r.log_return, 4) OVER w AS crypto_log_return_prev_4h
        FROM poly_hourly p
        LEFT JOIN crypto_returns r
          ON r.symbol = p.asset || 'USDT'
         AND r.interval = '1h'
         AND r.open_time_ns = p.open_time_ns
        WINDOW w AS (PARTITION BY p.token_id ORDER BY p.open_time_ns)
        """
    )

    # Joint alignment view: per (asset, hour) row carrying the dominant
    # Polymarket YES-price for that asset alongside the matching crypto bar
    # and forward returns for lead-lag analysis. We pick the highest-volume
    # YES token per asset to avoid double-counting markets.
    con.execute(
        """
        CREATE OR REPLACE VIEW crypto_polymarket_aligned AS
        WITH ranked_markets AS (
          SELECT
            crypto_asset_tag AS asset,
            yes_token_id,
            market_id,
            question,
            ROW_NUMBER() OVER (
              PARTITION BY crypto_asset_tag
              ORDER BY coalesce(volume_1mo_usd, volume_total_usd, 0.0) DESC
            ) AS asset_rank
          FROM polymarket_crypto_markets
          WHERE yes_token_id IS NOT NULL
            AND crypto_asset_tag IS NOT NULL
            AND coalesce(active, true)
        ),
        primary_token_per_asset AS (
          SELECT asset, yes_token_id, market_id, question
          FROM ranked_markets
          WHERE asset_rank = 1
        ),
        poly_hourly AS (
          SELECT p.token_id, p.market_id, p.open_time_ns, p.price,
                 m.asset, m.question
          FROM polymarket_price_history_hourly p
          JOIN primary_token_per_asset m ON p.token_id = m.yes_token_id
        ),
        joined AS (
          SELECT
            p.asset,
            p.open_time_ns,
            p.price AS poly_yes_price,
            p.question AS poly_question,
            r.symbol AS crypto_symbol,
            r.close AS crypto_close,
            r.log_return AS crypto_log_return
          FROM poly_hourly p
          LEFT JOIN crypto_returns r
            ON r.symbol = p.asset || 'USDT'
           AND r.interval = '1h'
           AND r.open_time_ns = p.open_time_ns
        )
        SELECT
          asset,
          open_time_ns,
          poly_yes_price,
          poly_yes_price - LAG(poly_yes_price) OVER w AS poly_price_change,
          poly_question,
          crypto_symbol,
          crypto_close,
          crypto_log_return,
          LEAD(crypto_log_return, 1) OVER w AS crypto_log_return_next_1h,
          LEAD(crypto_log_return, 4) OVER w AS crypto_log_return_next_4h,
          LEAD(crypto_log_return, 24) OVER w AS crypto_log_return_next_24h
        FROM joined
        WINDOW w AS (PARTITION BY asset ORDER BY open_time_ns)
        """
    )


def _table_glob(root: Path, table_name: str) -> str:
    return str(root / table_name / "**" / "*.parquet")
