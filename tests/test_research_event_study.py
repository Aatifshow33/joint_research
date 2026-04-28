from __future__ import annotations

import math
import random
from datetime import datetime, timezone

import pytest

from joint_research.ingest.binance_klines import project_binance_klines
from joint_research.ingest.gamma_crypto_markets import project_gamma_market_payload
from joint_research.ingest.wallet_activity import project_wallet_activity_dump
from joint_research.research.event_study import (
    classify_trade_direction,
    run_event_study,
    write_event_study_catalog,
)
from joint_research.warehouse import (
    CRYPTO_OHLCV,
    POLYMARKET_CRYPTO_MARKETS,
    POLYMARKET_WALLET_ACTIVITY,
    ParquetWriter,
    WarehousePaths,
)


def test_classify_buy_yes_is_bullish() -> None:
    assert classify_trade_direction("BUY", "Yes") == "bullish"
    assert classify_trade_direction("buy", "yes") == "bullish"


def test_classify_buy_up_is_bullish() -> None:
    # Polymarket's "BTC up or down" 5m markets use Up/Down outcomes
    assert classify_trade_direction("BUY", "Up") == "bullish"
    assert classify_trade_direction("BUY", "Down") == "bearish"


def test_classify_buy_no_is_bearish() -> None:
    assert classify_trade_direction("BUY", "No") == "bearish"


def test_classify_sell_yes_is_bearish() -> None:
    assert classify_trade_direction("SELL", "Yes") == "bearish"


def test_classify_sell_no_is_bullish() -> None:
    assert classify_trade_direction("SELL", "No") == "bullish"


def test_classify_unknown_side_returns_none() -> None:
    assert classify_trade_direction("MERGE", "Yes") is None
    assert classify_trade_direction(None, "Yes") is None
    assert classify_trade_direction("BUY", None) is None


def test_project_wallet_activity_handles_normalized_dump() -> None:
    record = {
        "wallet_address": "0xABC123",
        "activity_at": "2026-04-20T12:00:00Z",
        "fetched_at": "2026-04-20T12:00:01Z",
        "activity_type": "BUY",
        "outcome": "Yes",
        "side": "Yes",
        "size": "100.5",
        "usdc_size": "1500.0",
        "price": "0.5",
        "condition_id": "0x456",
        "token_id": "tok-yes",
        "title": "Will BTC hit $100k?",
        "source_record_id": "rec-1",
    }
    row = project_wallet_activity_dump(record)
    assert row.wallet_address == "0xabc123"
    assert row.activity_type == "BUY"
    assert row.size_usdc == 1500.0
    assert row.condition_id == "0x456"
    expected_ns = int(datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc).timestamp() * 1e9)
    assert row.event_time_ns == expected_ns


def test_project_wallet_activity_rejects_missing_address() -> None:
    with pytest.raises(ValueError, match="missing_address"):
        project_wallet_activity_dump({"activity_at": "2026-04-20T12:00:00Z"})


def _seed_event_study_warehouse(tmp_path) -> WarehousePaths:
    paths = WarehousePaths(root=tmp_path)
    rng = random.Random(0)

    # 200 hourly BTC bars. Inject controlled returns we can verify against.
    h0 = 1_700_002_800_000
    h0 = (h0 // 3_600_000) * 3_600_000
    n_bars = 200
    klines_raw = []
    last_close = 30000.0
    bar_returns: list[float] = []
    for i in range(n_bars):
        ret = rng.gauss(0, 0.005)
        new_close = last_close * math.exp(ret)
        klines_raw.append([
            h0 + i * 3_600_000,
            f"{last_close:.2f}", f"{max(last_close, new_close) + 5:.2f}", f"{min(last_close, new_close) - 5:.2f}",
            f"{new_close:.2f}", "1.0", h0 + i * 3_600_000 + 3_599_999,
            f"{new_close:.2f}", 10, "0.5", f"{new_close / 2:.2f}", "0",
        ])
        bar_returns.append(ret)
        last_close = new_close
    klines = project_binance_klines(klines_raw, symbol="BTCUSDT", interval="1h")
    ParquetWriter(table=CRYPTO_OHLCV, paths=paths).write(
        [r.to_warehouse_row() for r in klines]
    )

    # One BTC market
    market = project_gamma_market_payload(
        {
            "id": "m-btc-1",
            "conditionId": "0xCRYPTO_BTC",
            "question": "Will BTC hit $50,000?",
            "slug": "btc-50k",
            "active": True, "closed": False, "archived": False,
            "endDate": "2026-12-31T23:59:59Z",
            "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-04-20T18:30:00Z",
            "volume": 1000000, "volume1mo": 500000,
            "clobTokenIds": '["yes-tok", "no-tok"]',
        },
        fetched_at=datetime.now(tz=timezone.utc),
    )
    ParquetWriter(table=POLYMARKET_CRYPTO_MARKETS, paths=paths).write([market.to_warehouse_row()])

    # Inject 30 BUY-YES (bullish) trades on bars where the next-1h return is
    # >0, and 30 BUY-NO (bearish) trades on bars where next-1h return is <0.
    # If the harness is sound, the bullish cell at lag=1h should show
    # significantly positive mean.
    activities: list[dict] = []
    bull_count = 0
    bear_count = 0
    rid = 0
    for i in range(n_bars - 24):
        next_ret = bar_returns[i + 1]
        bar_open_ns = (h0 + i * 3_600_000) * 1_000_000
        ts_iso = datetime.fromtimestamp(bar_open_ns / 1e9, tz=timezone.utc).isoformat()
        if next_ret > 0 and bull_count < 30:
            activities.append({
                "wallet_address": f"0xwhale{bull_count}",
                "activity_at": ts_iso, "fetched_at": ts_iso,
                "activity_type": "TRADE", "outcome": "Yes", "side": "BUY",
                "size": "10", "usdc_size": "5000", "price": "0.5",
                "condition_id": "0xCRYPTO_BTC", "token_id": "yes-tok",
                "title": "Will BTC hit $50,000?", "source_record_id": f"rec{rid}",
            })
            bull_count += 1; rid += 1
        elif next_ret < 0 and bear_count < 30:
            activities.append({
                "wallet_address": f"0xbearwhale{bear_count}",
                "activity_at": ts_iso, "fetched_at": ts_iso,
                "activity_type": "TRADE", "outcome": "No", "side": "BUY",
                "size": "10", "usdc_size": "5000", "price": "0.5",
                "condition_id": "0xCRYPTO_BTC", "token_id": "no-tok",
                "title": "Will BTC hit $50,000?", "source_record_id": f"rec{rid}",
            })
            bear_count += 1; rid += 1

    rows = [project_wallet_activity_dump(a) for a in activities]
    ParquetWriter(table=POLYMARKET_WALLET_ACTIVITY, paths=paths).write(
        [r.to_warehouse_row() for r in rows]
    )
    return paths


def test_event_study_recovers_planted_signal(tmp_path) -> None:
    paths = _seed_event_study_warehouse(tmp_path)
    result = run_event_study(paths=paths, min_trade_size_usdc=100.0)

    assert result.n_trades_total >= 50

    # Bullish cell at lag=1h must have significantly positive mean (we
    # constructed trades so that next-1h return is positive on bullish events).
    cell = next(
        (c for c in result.cells if c.asset == "BTC" and c.direction == "bullish" and c.lag_hours == 1),
        None,
    )
    assert cell is not None
    assert cell.mean_log_return > 0
    assert cell.pvalue_vs_zero < 0.001

    # Bearish cell at lag=1h must have significantly negative mean.
    bear = next(
        (c for c in result.cells if c.asset == "BTC" and c.direction == "bearish" and c.lag_hours == 1),
        None,
    )
    assert bear is not None
    assert bear.mean_log_return < 0
    assert bear.pvalue_vs_zero < 0.001


def test_event_study_catalog_writes_parquet(tmp_path) -> None:
    paths = _seed_event_study_warehouse(tmp_path)
    result = run_event_study(paths=paths, min_trade_size_usdc=100.0)
    out = tmp_path / "event_study.parquet"
    write_event_study_catalog(out_path=out, result=result)
    assert out.exists()

    import pyarrow.parquet as pq  # noqa: PLC0415
    t = pq.read_table(out)
    assert "mean_log_return" in t.schema.names
    assert "bh_significant_at_0_05" in t.schema.names
