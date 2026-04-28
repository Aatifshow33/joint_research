"""Backtest of cryp's deterministic strategies on the joint warehouse.

Reads ``crypto_ohlcv`` for one symbol, walks the candles forward, and at each
bar feeds the prior window through cryp's feature pipeline → regime
classifier → breakout/mean-reversion signal generators. Each emitted
``TradeProposal`` opens a simulated position; subsequent candle highs/lows
trigger the stop or take-profit; if neither hits within ``max_holding_hours``
the position closes at that candle's close.

Costs are modelled as a round-trip cost in basis points charged against
notional at exit (combined fee + slippage; default 14 bps round-trip
matching Bybit perp taker fees + ~2 bps each-way slippage).

This is a strategy backtest — it answers "do cryp's existing signals have
edge on real Binance data, before any execution layer is wired?". A null
result means we shouldn't deploy these strategies live regardless of how
clean the venue adapter is.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from crypto_agent.enums import Side
from crypto_agent.features.pipeline import build_feature_snapshot
from crypto_agent.market_data.models import Candle
from crypto_agent.regime.base import RegimeConfig
from crypto_agent.regime.rules import classify_regime
from crypto_agent.signals.base import BreakoutSignalConfig, MeanReversionSignalConfig
from crypto_agent.signals.breakout import generate_breakout_proposal
from crypto_agent.signals.mean_reversion import generate_mean_reversion_proposal
from crypto_agent.types import TradeProposal

from joint_research.warehouse.paths import WarehousePaths
from joint_research.warehouse.views import register_views


@dataclass(frozen=True)
class BacktestTrade:
    strategy_id: str
    symbol: str
    side: str  # "buy" | "sell"
    entry_time_ns: int
    entry_price: float
    exit_time_ns: int
    exit_price: float
    exit_reason: str  # "stop" | "take_profit" | "max_holding"
    gross_log_return: float
    net_log_return: float  # gross minus round-trip cost
    holding_hours: int


@dataclass
class BacktestResult:
    symbol: str
    n_candles: int
    n_proposals_breakout: int = 0
    n_proposals_mean_reversion: int = 0
    n_trades: int = 0
    trades: list[BacktestTrade] = field(default_factory=list)

    def summary(self) -> dict[str, float]:
        if not self.trades:
            return {
                "symbol_implicit": 0.0,  # placeholder; symbol carried separately
                "n_trades": 0,
                "hit_rate": 0.0,
                "mean_net_bps": 0.0,
                "stddev_net_bps": 0.0,
                "total_net_bps": 0.0,
                "max_drawdown_bps": 0.0,
                "sharpe_per_trade": 0.0,
            }
        nets = [t.net_log_return for t in self.trades]
        wins = sum(1 for r in nets if r > 0)
        mean_r = sum(nets) / len(nets)
        if len(nets) > 1:
            var_r = sum((r - mean_r) ** 2 for r in nets) / (len(nets) - 1)
            stddev_r = math.sqrt(var_r)
        else:
            stddev_r = 0.0
        cumulative = []
        running = 0.0
        for r in nets:
            running += r
            cumulative.append(running)
        peak = -math.inf
        max_dd = 0.0
        for c in cumulative:
            if c > peak:
                peak = c
            dd = peak - c
            if dd > max_dd:
                max_dd = dd
        sharpe = (mean_r / stddev_r) * math.sqrt(len(nets)) if stddev_r > 0 else 0.0
        return {
            "n_trades": len(nets),
            "hit_rate": wins / len(nets),
            "mean_net_bps": mean_r * 1e4,
            "stddev_net_bps": stddev_r * 1e4,
            "total_net_bps": sum(nets) * 1e4,
            "max_drawdown_bps": max_dd * 1e4,
            "sharpe_per_trade": sharpe,
        }


def load_candles_from_warehouse(
    *,
    paths: WarehousePaths,
    symbol: str,
    interval: str = "1h",
    venue: str = "paper",
) -> list[Candle]:
    """Read OHLCV from the warehouse and project to ``Candle`` objects."""

    con = duckdb.connect()
    register_views(con, paths)
    rows = con.execute(
        """
        SELECT open_time_ns, close_time_ns, open, high, low, close, volume_base
        FROM crypto_ohlcv
        WHERE symbol = ? AND interval = ?
        ORDER BY open_time_ns
        """,
        [symbol, interval],
    ).fetchall()

    candles: list[Candle] = []
    for open_ns, close_ns, o, h, low, c, vol in rows:
        # Pydantic Candle requires high >= max(open,close), low <= min(open,close).
        # Defensive clamp in case a malformed bar slipped through.
        h_safe = max(h, o, c)
        l_safe = min(low, o, c)
        candles.append(
            Candle(
                venue=venue,
                symbol=symbol,
                interval=interval,
                open_time=datetime.fromtimestamp(open_ns / 1e9, tz=timezone.utc),
                close_time=datetime.fromtimestamp(close_ns / 1e9, tz=timezone.utc),
                open=float(o),
                high=float(h_safe),
                low=float(l_safe),
                close=float(c),
                volume=float(vol),
                closed=True,
            )
        )
    return candles


def run_cryp_backtest(
    *,
    paths: WarehousePaths,
    symbol: str,
    feature_lookback: int = 14,
    max_holding_hours: int = 24,
    round_trip_cost_bps: float = 14.0,
    breakout_config: BreakoutSignalConfig | None = None,
    mean_reversion_config: MeanReversionSignalConfig | None = None,
    regime_config: RegimeConfig | None = None,
) -> BacktestResult:
    candles = load_candles_from_warehouse(paths=paths, symbol=symbol)
    return run_backtest_on_candles(
        candles,
        feature_lookback=feature_lookback,
        max_holding_hours=max_holding_hours,
        round_trip_cost_bps=round_trip_cost_bps,
        breakout_config=breakout_config,
        mean_reversion_config=mean_reversion_config,
        regime_config=regime_config,
    )


def run_backtest_on_candles(
    candles: Sequence[Candle],
    *,
    feature_lookback: int = 14,
    max_holding_hours: int = 24,
    round_trip_cost_bps: float = 14.0,
    breakout_config: BreakoutSignalConfig | None = None,
    mean_reversion_config: MeanReversionSignalConfig | None = None,
    regime_config: RegimeConfig | None = None,
) -> BacktestResult:
    breakout_cfg = breakout_config or BreakoutSignalConfig()
    mr_cfg = mean_reversion_config or MeanReversionSignalConfig()
    rg_cfg = regime_config or RegimeConfig()
    cost_per_side = round_trip_cost_bps / 2.0 / 1e4  # split fee+slippage entry/exit

    if not candles:
        return BacktestResult(symbol="", n_candles=0)

    result = BacktestResult(symbol=candles[0].symbol, n_candles=len(candles))

    # Need enough lookback to build features and reference windows.
    min_history = max(feature_lookback, breakout_cfg.lookback_candles + 1, mr_cfg.lookback_candles + 1)

    i = min_history
    while i < len(candles):
        window = list(candles[i - feature_lookback : i + 1])
        try:
            features = build_feature_snapshot(window, lookback_periods=feature_lookback)
        except ValueError:
            i += 1
            continue
        regime = classify_regime(features, rg_cfg)

        proposal: TradeProposal | None = None
        try:
            proposal = generate_breakout_proposal(
                window, features, regime, breakout_cfg
            )
        except ValueError:
            proposal = None
        if proposal is not None:
            result.n_proposals_breakout += 1
        else:
            try:
                proposal = generate_mean_reversion_proposal(
                    window, features, regime, mr_cfg
                )
            except ValueError:
                proposal = None
            if proposal is not None:
                result.n_proposals_mean_reversion += 1

        if proposal is None:
            i += 1
            continue

        trade = _simulate_trade(
            entry_index=i,
            candles=candles,
            proposal=proposal,
            max_holding_hours=max_holding_hours,
            cost_per_side=cost_per_side,
        )
        if trade is not None:
            result.trades.append(trade)
            result.n_trades += 1
            # Skip forward past the trade exit so we don't enter another
            # position while still holding (single-position-at-a-time policy).
            i = max(i + 1, _candle_index_at_or_after_ns(candles, trade.exit_time_ns))
        else:
            i += 1

    return result


def _simulate_trade(
    *,
    entry_index: int,
    candles: Sequence[Candle],
    proposal: TradeProposal,
    max_holding_hours: int,
    cost_per_side: float,
) -> BacktestTrade | None:
    if entry_index + 1 >= len(candles):
        return None
    # Enter on the next candle's open (realistic — we can only act after the
    # signal candle has closed).
    entry_candle = candles[entry_index + 1]
    entry_price = entry_candle.open
    is_long = proposal.side is Side.BUY
    stop = float(proposal.stop_price)
    tp = float(proposal.take_profit_price) if proposal.take_profit_price is not None else None

    exit_index = min(entry_index + 1 + max_holding_hours, len(candles) - 1)
    exit_reason = "max_holding"
    exit_price = candles[exit_index].close
    exit_time_ns = int(candles[exit_index].close_time.timestamp() * 1e9)

    for j in range(entry_index + 1, exit_index + 1):
        bar = candles[j]
        if is_long:
            hit_stop = bar.low <= stop
            hit_tp = tp is not None and bar.high >= tp
        else:
            hit_stop = bar.high >= stop
            hit_tp = tp is not None and bar.low <= tp
        if hit_stop and hit_tp:
            # Conservative: assume stop hits first if both touched in the bar.
            exit_reason = "stop"
            exit_price = stop
            exit_time_ns = int(bar.close_time.timestamp() * 1e9)
            break
        if hit_stop:
            exit_reason = "stop"
            exit_price = stop
            exit_time_ns = int(bar.close_time.timestamp() * 1e9)
            break
        if hit_tp:
            exit_reason = "take_profit"
            exit_price = tp  # type: ignore[assignment]
            exit_time_ns = int(bar.close_time.timestamp() * 1e9)
            break

    if entry_price <= 0 or exit_price <= 0:
        return None

    if is_long:
        gross = math.log(exit_price / entry_price)
    else:
        gross = math.log(entry_price / exit_price)
    net = gross - 2 * cost_per_side  # entry + exit cost

    holding_hours = max(1, exit_index - entry_index)

    return BacktestTrade(
        strategy_id=proposal.strategy_id,
        symbol=proposal.symbol,
        side="buy" if is_long else "sell",
        entry_time_ns=int(entry_candle.open_time.timestamp() * 1e9),
        entry_price=entry_price,
        exit_time_ns=exit_time_ns,
        exit_price=exit_price,
        exit_reason=exit_reason,
        gross_log_return=gross,
        net_log_return=net,
        holding_hours=holding_hours,
    )


def _candle_index_at_or_after_ns(candles: Sequence[Candle], ns: int) -> int:
    for i, c in enumerate(candles):
        if int(c.open_time.timestamp() * 1e9) >= ns:
            return i
    return len(candles)


def write_backtest_catalog(
    *,
    out_path: Path,
    results: Iterable[BacktestResult],
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for res in results:
        for t in res.trades:
            rows.append(
                {
                    "symbol": res.symbol,
                    "strategy_id": t.strategy_id,
                    "side": t.side,
                    "entry_time_ns": t.entry_time_ns,
                    "entry_price": t.entry_price,
                    "exit_time_ns": t.exit_time_ns,
                    "exit_price": t.exit_price,
                    "exit_reason": t.exit_reason,
                    "gross_log_return": t.gross_log_return,
                    "net_log_return": t.net_log_return,
                    "holding_hours": t.holding_hours,
                }
            )
    if not rows:
        cols = [
            "symbol", "strategy_id", "side", "entry_time_ns", "entry_price",
            "exit_time_ns", "exit_price", "exit_reason", "gross_log_return",
            "net_log_return", "holding_hours",
        ]
        pq.write_table(pa.table({c: [] for c in cols}), out_path)
        return
    cols = list(rows[0].keys())
    table = pa.table({c: [r[c] for r in rows] for c in cols})
    pq.write_table(table, out_path)
