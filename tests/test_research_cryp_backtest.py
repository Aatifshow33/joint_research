from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from crypto_agent.enums import Side
from crypto_agent.market_data.models import Candle
from crypto_agent.types import ExecutionConstraints, TradeProposal

from joint_research.research.cryp_backtest import (
    BacktestResult,
    BacktestTrade,
    _simulate_trade,
    run_backtest_on_candles,
    write_backtest_catalog,
)


def _candle(i: int, *, open: float, high: float, low: float, close: float, volume: float = 100.0) -> Candle:
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return Candle(
        venue="paper",
        symbol="BTCUSDT",
        interval="1h",
        open_time=base + timedelta(hours=i),
        close_time=base + timedelta(hours=i + 1) - timedelta(microseconds=1),
        open=open, high=high, low=low, close=close,
        volume=volume, closed=True,
    )


def test_simulate_long_take_profit_hits() -> None:
    candles = [
        _candle(0, open=100, high=101, low=99, close=100),  # signal candle
        _candle(1, open=100, high=110, low=99, close=105),  # next candle: enters at 100, TP at 110 hits
    ]
    proposal = TradeProposal(
        strategy_id="test", symbol="BTCUSDT", side=Side.BUY, confidence=0.8,
        thesis="t", entry_reference=100.0, stop_price=95.0, take_profit_price=110.0,
        expected_holding_period="2h", invalidation_reason="i",
        execution_constraints=ExecutionConstraints(max_slippage_bps=20, max_spread_bps=20),
    )
    trade = _simulate_trade(
        entry_index=0, candles=candles, proposal=proposal,
        max_holding_hours=24, cost_per_side=0.0007,
    )
    assert trade is not None
    assert trade.exit_reason == "take_profit"
    assert trade.exit_price == 110.0
    assert trade.gross_log_return == pytest.approx(math.log(110 / 100))


def test_simulate_long_stop_hits_first() -> None:
    candles = [
        _candle(0, open=100, high=101, low=99, close=100),
        _candle(1, open=100, high=101, low=94, close=95),  # stop at 95 hit
    ]
    proposal = TradeProposal(
        strategy_id="test", symbol="BTCUSDT", side=Side.BUY, confidence=0.8,
        thesis="t", entry_reference=100.0, stop_price=95.0, take_profit_price=110.0,
        expected_holding_period="2h", invalidation_reason="i",
        execution_constraints=ExecutionConstraints(max_slippage_bps=20, max_spread_bps=20),
    )
    trade = _simulate_trade(
        entry_index=0, candles=candles, proposal=proposal,
        max_holding_hours=24, cost_per_side=0.0007,
    )
    assert trade is not None
    assert trade.exit_reason == "stop"
    assert trade.exit_price == 95.0


def test_simulate_short_take_profit() -> None:
    candles = [
        _candle(0, open=100, high=101, low=99, close=100),
        _candle(1, open=100, high=101, low=89, close=90),
    ]
    proposal = TradeProposal(
        strategy_id="test", symbol="BTCUSDT", side=Side.SELL, confidence=0.8,
        thesis="t", entry_reference=100.0, stop_price=105.0, take_profit_price=90.0,
        expected_holding_period="2h", invalidation_reason="i",
        execution_constraints=ExecutionConstraints(max_slippage_bps=20, max_spread_bps=20),
    )
    trade = _simulate_trade(
        entry_index=0, candles=candles, proposal=proposal,
        max_holding_hours=24, cost_per_side=0.0007,
    )
    assert trade is not None
    assert trade.exit_reason == "take_profit"
    assert trade.exit_price == 90.0
    # Short profits when price drops
    assert trade.gross_log_return == pytest.approx(math.log(100 / 90))


def test_simulate_max_holding_close() -> None:
    # No stop, no TP touched — exit at max-holding bar's close.
    candles = [_candle(0, open=100, high=101, low=99, close=100)] + [
        _candle(i, open=100, high=100.5, low=99.5, close=100.0) for i in range(1, 30)
    ]
    proposal = TradeProposal(
        strategy_id="test", symbol="BTCUSDT", side=Side.BUY, confidence=0.8,
        thesis="t", entry_reference=100.0, stop_price=90.0, take_profit_price=120.0,
        expected_holding_period="24h", invalidation_reason="i",
        execution_constraints=ExecutionConstraints(max_slippage_bps=20, max_spread_bps=20),
    )
    trade = _simulate_trade(
        entry_index=0, candles=candles, proposal=proposal,
        max_holding_hours=24, cost_per_side=0.0007,
    )
    assert trade is not None
    assert trade.exit_reason == "max_holding"


def test_summary_zero_trades_returns_zero_metrics() -> None:
    res = BacktestResult(symbol="X", n_candles=0)
    s = res.summary()
    assert s["n_trades"] == 0
    assert s["sharpe_per_trade"] == 0.0


def test_summary_correct_drawdown() -> None:
    res = BacktestResult(symbol="X", n_candles=0)
    # Trade returns: +50bps, -100bps, -50bps, +200bps
    # Cumulative: +50, -50, -100, +100
    # Peak: 50 → DD at -50 is 100bps; peak resets to 100, DD ends at 0
    # Max DD = 200bps (peak 50 to trough -100)... wait let me recheck
    # Actually cumulative path: 0 → 50 → -50 → -100 → 100
    # Running peak: 0, 50, 50, 50, 100
    # DD: 0, 0, 100, 150, 0 → max = 150bps
    for r_bps in [50, -100, -50, 200]:
        res.trades.append(BacktestTrade(
            strategy_id="s", symbol="X", side="buy",
            entry_time_ns=0, entry_price=100, exit_time_ns=0, exit_price=100,
            exit_reason="max_holding",
            gross_log_return=r_bps / 1e4, net_log_return=r_bps / 1e4,
            holding_hours=1,
        ))
    s = res.summary()
    assert s["n_trades"] == 4
    assert s["max_drawdown_bps"] == pytest.approx(150.0, abs=0.01)
    assert s["total_net_bps"] == pytest.approx(100.0, abs=0.01)


def test_run_backtest_on_candles_smoke() -> None:
    # Random-walk-ish series: not expected to produce significant edge,
    # just verify the pipeline runs without raising.
    import random  # noqa: PLC0415
    rng = random.Random(0)
    candles = []
    last_close = 30000.0
    for i in range(300):
        ret = rng.gauss(0, 0.005)
        new_close = last_close * math.exp(ret)
        candles.append(_candle(
            i,
            open=last_close,
            high=max(last_close, new_close) + 5,
            low=min(last_close, new_close) - 5,
            close=new_close,
            volume=200.0,  # ample $-volume at $30k
        ))
        last_close = new_close

    result = run_backtest_on_candles(candles, feature_lookback=14)
    assert result.n_candles == 300
    # Pipeline completes, n_proposals_* are non-negative ints
    assert result.n_proposals_breakout >= 0
    assert result.n_proposals_mean_reversion >= 0


def test_write_backtest_catalog(tmp_path) -> None:
    res = BacktestResult(symbol="BTCUSDT", n_candles=10)
    res.trades.append(BacktestTrade(
        strategy_id="breakout_v1", symbol="BTCUSDT", side="buy",
        entry_time_ns=1, entry_price=100, exit_time_ns=2, exit_price=110,
        exit_reason="take_profit",
        gross_log_return=math.log(1.1), net_log_return=math.log(1.1) - 0.0014,
        holding_hours=1,
    ))
    out = tmp_path / "trades.parquet"
    write_backtest_catalog(out_path=out, results=[res])
    assert out.exists()
    import pyarrow.parquet as pq  # noqa: PLC0415
    t = pq.read_table(out)
    assert t.num_rows == 1
    assert "net_log_return" in t.schema.names
