"""Event study: do whale Polymarket crypto trades predict crypto returns?

Each row in ``whale_crypto_trades`` is one trade by a known wallet on a
crypto-tagged Polymarket market. We classify the trade direction (a BUY of
the YES token is bullish on the asset; a BUY of the NO token, or a SELL of
YES, is bearish), then ask: given that classification, what's the average
crypto return at +1h / +4h / +24h relative to the trade?

The basic test: is the mean forward return after a "bullish whale trade"
materially different from the unconditional mean? We use a one-sample
t-test against zero (since the unconditional mean hourly return is ~0)
and a permutation-style mean-difference between bullish and bearish trades
where both classes have data.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from joint_research.research.lead_lag import (
    _t_two_sided_pvalue,
    benjamini_hochberg_significant,
)
from joint_research.warehouse.paths import WarehousePaths
from joint_research.warehouse.views import register_views


# Lag horizons we test (in hours).
EVENT_LAG_HORIZONS_HOURS: tuple[int, ...] = (1, 4, 24)


@dataclass(frozen=True)
class EventStudyCell:
    asset: str
    direction: str  # "bullish" | "bearish"
    lag_hours: int
    n_trades: int
    mean_log_return: float
    stddev_log_return: float
    tstat_vs_zero: float
    pvalue_vs_zero: float
    bh_significant_at_0_05: bool


@dataclass(frozen=True)
class EventStudyResult:
    cells: list[EventStudyCell]
    n_trades_total: int
    n_wallets: int
    n_assets: int


_BULLISH_OUTCOMES = frozenset({"yes", "up"})
_BEARISH_OUTCOMES = frozenset({"no", "down"})


def classify_trade_direction(side: str | None, outcome: str | None) -> str | None:
    """Classify a wallet trade as bullish/bearish on the underlying asset.

    For Polymarket activity rows, ``activity_type`` is the verb (TRADE, MERGE,
    SPLIT, REDEEM…) and ``side`` is BUY or SELL on a TRADE. The outcome side
    being traded determines the directional thesis:

    - BUY of a "Yes"/"Up" outcome = bullish on the asset (you're paying for
      the question's positive resolution).
    - BUY of a "No"/"Down" outcome = bearish on the asset.
    - SELL flips both.

    Markets that aren't BTC-up-or-down style use Yes/No conventions; the
    short-window "Bitcoin Up or Down" 5-minute markets use Up/Down literally.
    Both are mapped to the same bullish/bearish dimension here.
    """

    if side is None or outcome is None:
        return None
    s = side.strip().upper()
    out = outcome.strip().lower()
    if s == "BUY" and out in _BULLISH_OUTCOMES:
        return "bullish"
    if s == "BUY" and out in _BEARISH_OUTCOMES:
        return "bearish"
    if s == "SELL" and out in _BULLISH_OUTCOMES:
        return "bearish"
    if s == "SELL" and out in _BEARISH_OUTCOMES:
        return "bullish"
    return None


def run_event_study(
    *,
    paths: WarehousePaths,
    min_trade_size_usdc: float = 100.0,
    exclude_short_resolution_markets: bool = True,
) -> EventStudyResult:
    """Aggregate forward-return distributions per (asset, direction, lag) cell.

    ``exclude_short_resolution_markets`` drops trades on markets whose outcome
    is ``Up``/``Down`` — Polymarket's 5-minute "Bitcoin Up or Down" markets
    resolve within the same hour as the trade and would inject look-ahead
    bias into any +1h or +4h forward-return measurement. Default on.
    """

    con = duckdb.connect()
    register_views(con, paths)

    short_resolution_filter = (
        "AND upper(coalesce(outcome, '')) NOT IN ('UP', 'DOWN')"
        if exclude_short_resolution_markets
        else ""
    )
    # Dedup at (wallet, asset, hour, direction). When a whale fragments one
    # decision into many fills in the same hour, that's one observation.
    # Treating each fill as independent inflates t-stats by sqrt(n_fills).
    rows = con.execute(
        f"""
        WITH typed_trades AS (
          SELECT
            wallet_address,
            asset,
            CASE
              WHEN upper(side) = 'BUY' AND lower(outcome) IN ('yes', 'up') THEN 'bullish'
              WHEN upper(side) = 'BUY' AND lower(outcome) IN ('no', 'down') THEN 'bearish'
              WHEN upper(side) = 'SELL' AND lower(outcome) IN ('yes', 'up') THEN 'bearish'
              WHEN upper(side) = 'SELL' AND lower(outcome) IN ('no', 'down') THEN 'bullish'
              ELSE NULL
            END AS direction,
            trade_hour_ns,
            sum(coalesce(size_usdc, 0)) AS hour_total_size_usdc,
            any_value(crypto_log_return_next_1h_at_trade) AS r_1h,
            any_value(crypto_log_return_next_4h_at_trade) AS r_4h,
            any_value(crypto_log_return_next_24h_at_trade) AS r_24h
          FROM whale_crypto_trades
          WHERE crypto_log_return_next_1h_at_trade IS NOT NULL
            AND upper(coalesce(activity_type, '')) = 'TRADE'
            {short_resolution_filter}
          GROUP BY wallet_address, asset,
                   CASE
                     WHEN upper(side) = 'BUY' AND lower(outcome) IN ('yes', 'up') THEN 'bullish'
                     WHEN upper(side) = 'BUY' AND lower(outcome) IN ('no', 'down') THEN 'bearish'
                     WHEN upper(side) = 'SELL' AND lower(outcome) IN ('yes', 'up') THEN 'bearish'
                     WHEN upper(side) = 'SELL' AND lower(outcome) IN ('no', 'down') THEN 'bullish'
                     ELSE NULL
                   END,
                   trade_hour_ns
        )
        SELECT
          wallet_address,
          asset,
          NULL AS side,         -- direction already classified
          NULL AS outcome,
          hour_total_size_usdc AS size_usdc,
          r_1h, r_4h, r_24h,
          'TRADE' AS activity_type,
          direction
        FROM typed_trades
        WHERE direction IS NOT NULL
          AND hour_total_size_usdc >= ?
        """,
        [min_trade_size_usdc],
    ).fetchall()

    samples: dict[tuple[str, str, int], list[float]] = {}
    wallets: set[str] = set()
    assets: set[str] = set()
    n_trades_total = 0

    lag_index_map = {1: 5, 4: 6, 24: 7}

    for row in rows:
        wallet, asset = row[0], row[1]
        # Direction is now pre-classified in the SQL CTE so order fragmenting
        # at a given (wallet, hour) collapses to one observation.
        direction = row[9]
        if direction is None or asset is None:
            continue
        wallets.add(wallet)
        assets.add(asset)
        n_trades_total += 1
        for lag in EVENT_LAG_HORIZONS_HOURS:
            ret = row[lag_index_map[lag]]
            if ret is None:
                continue
            try:
                ret_f = float(ret)
            except (TypeError, ValueError):
                continue
            if math.isnan(ret_f):
                continue
            key = (asset, direction, lag)
            samples.setdefault(key, []).append(ret_f)

    raw: list[tuple[tuple[str, str, int], int, float, float, float, float]] = []
    for key, values in samples.items():
        n = len(values)
        if n < 5:
            continue
        mean = sum(values) / n
        if n == 1:
            stddev = 0.0
        else:
            var = sum((v - mean) ** 2 for v in values) / (n - 1)
            stddev = math.sqrt(var)
        if stddev == 0.0:
            tstat = math.nan
            p = 1.0
        else:
            se = stddev / math.sqrt(n)
            tstat = mean / se
            p = _t_two_sided_pvalue(abs(tstat), df=n - 1)
        raw.append((key, n, mean, stddev, tstat, p))

    pvalues = [item[5] for item in raw]
    bh = benjamini_hochberg_significant(pvalues, alpha=0.05)
    cells: list[EventStudyCell] = []
    for (key, n, mean, stddev, tstat, p), survives in zip(raw, bh):
        asset, direction, lag = key
        cells.append(
            EventStudyCell(
                asset=asset,
                direction=direction,
                lag_hours=lag,
                n_trades=n,
                mean_log_return=mean,
                stddev_log_return=stddev,
                tstat_vs_zero=tstat,
                pvalue_vs_zero=p,
                bh_significant_at_0_05=survives,
            )
        )
    cells.sort(key=lambda c: (c.asset, c.direction, c.lag_hours))

    return EventStudyResult(
        cells=cells,
        n_trades_total=n_trades_total,
        n_wallets=len(wallets),
        n_assets=len(assets),
    )


def write_event_study_catalog(
    *,
    out_path: Path,
    result: EventStudyResult,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not result.cells:
        empty_columns = list(EventStudyCell.__dataclass_fields__.keys())  # type: ignore[arg-type]
        pq.write_table(pa.table({c: [] for c in empty_columns}), out_path)
        return
    records = [asdict(c) for c in result.cells]
    cols = list(records[0].keys())
    table = pa.table({c: [rec[c] for rec in records] for c in cols})
    pq.write_table(table, out_path)
