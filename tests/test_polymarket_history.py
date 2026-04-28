from __future__ import annotations

from datetime import datetime, timezone

import duckdb
import httpx
import pytest

from joint_research.ingest.binance_klines import project_binance_klines
from joint_research.ingest.clob_prices_history import (
    fetch_prices_history,
    project_history_samples,
)
from joint_research.ingest.gamma_crypto_markets import (
    fetch_crypto_markets,
    project_gamma_market_payload,
    project_gamma_market_payloads,
)
from joint_research.warehouse import (
    CRYPTO_OHLCV,
    POLYMARKET_CRYPTO_MARKETS,
    POLYMARKET_PRICE_HISTORY,
    ParquetWriter,
    WarehousePaths,
    register_views,
)


def _market_payload(
    *,
    market_id: str,
    question: str,
    yes: str,
    no: str,
    volume_1mo: float = 100000.0,
    asset_hint_in_question: bool = True,
) -> dict:
    return {
        "id": market_id,
        "conditionId": f"0x{market_id.zfill(64)}",
        "question": question,
        "slug": question.lower().replace(" ", "-").replace("?", ""),
        "active": True,
        "closed": False,
        "archived": False,
        "endDate": "2026-12-31T23:59:59Z",
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-04-20T18:30:00Z",
        "volume": volume_1mo * 5,
        "volume24hr": volume_1mo / 30,
        "volume1wk": volume_1mo / 4,
        "volume1mo": volume_1mo,
        "liquidity": 5000.0,
        "lastTradePrice": 0.42,
        "clobTokenIds": f'["{yes}", "{no}"]',
        "outcomes": '["Yes", "No"]',
        "events": [{"id": "evt-parent"}],
    }


def test_project_market_extracts_yes_no_tokens_and_asset_tag() -> None:
    payload = _market_payload(
        market_id="100",
        question="Will Bitcoin hit $100k in 2026?",
        yes="111",
        no="222",
    )
    fetched = datetime(2026, 4, 27, tzinfo=timezone.utc)

    row = project_gamma_market_payload(payload, fetched_at=fetched)

    assert row.market_id == "100"
    assert row.yes_token_id == "111"
    assert row.no_token_id == "222"
    assert row.event_id == "evt-parent"
    assert row.crypto_asset_tag == "BTC"
    assert row.volume_1mo_usd == pytest.approx(100000.0)
    # Uses updatedAt timestamp
    expected_ns = int(datetime(2026, 4, 20, 18, 30, tzinfo=timezone.utc).timestamp() * 1e9)
    assert row.event_time_ns == expected_ns


def test_project_market_handles_jsonless_clob_token_ids() -> None:
    payload = _market_payload(
        market_id="200",
        question="Will ETH hit $5k?",
        yes="333",
        no="444",
    )
    payload["clobTokenIds"] = ["333", "444"]  # already a list

    row = project_gamma_market_payload(payload, fetched_at=datetime.now(tz=timezone.utc))

    assert row.yes_token_id == "333"
    assert row.no_token_id == "444"
    assert row.crypto_asset_tag == "ETH"


def test_project_market_skips_payloads_without_id() -> None:
    rows = project_gamma_market_payloads(
        [
            {"slug": "no-id-here"},
            _market_payload(market_id="1", question="BTC q?", yes="a", no="b"),
        ],
        fetched_at=datetime.now(tz=timezone.utc),
    )
    assert len(rows) == 1
    assert rows[0].market_id == "1"


def test_history_projection_drops_malformed_samples() -> None:
    samples = [
        {"t": 1_700_000_000, "p": 0.4},
        {"t": "bad", "p": 0.5},  # malformed t
        {"p": 0.6},  # missing t
        {"t": 1_700_003_600, "p": 0.42},
    ]

    rows = project_history_samples(
        samples,
        token_id="tok-x",
        market_id="m1",
        outcome="Yes",
        interval_label="1m",
        fidelity_minutes=60,
    )

    assert len(rows) == 2
    assert rows[0].event_time_ns == 1_700_000_000 * 1_000_000_000
    assert rows[0].price == pytest.approx(0.4)
    # source label includes interval
    assert rows[0].to_warehouse_row()["source"] == "clob.prices_history.1m"


def test_history_payload_hash_distinguishes_same_token_different_time() -> None:
    a = project_history_samples(
        [{"t": 1, "p": 0.5}], token_id="tok"
    )[0]
    b = project_history_samples(
        [{"t": 2, "p": 0.5}], token_id="tok"
    )[0]
    assert a.payload_hash != b.payload_hash


@pytest.mark.asyncio
async def test_fetch_crypto_markets_passes_correct_filters() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json=[{"id": "1", "question": "q"}])

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        out = await fetch_crypto_markets(limit=42, active=True, closed=False, client=client)

    assert len(out) == 1
    url = str(captured["url"])
    assert "tag_id=21" in url
    assert "limit=42" in url
    assert "active=true" in url
    assert "closed=false" in url


@pytest.mark.asyncio
async def test_fetch_prices_history_rejects_conflicting_args() -> None:
    with pytest.raises(ValueError, match="must_pass_interval"):
        await fetch_prices_history(token_id="x", interval=None)
    with pytest.raises(ValueError, match="mutually_exclusive"):
        await fetch_prices_history(token_id="x", interval="1m", start_ts=1, end_ts=2)


@pytest.mark.asyncio
async def test_fetch_prices_history_round_trip() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"history": [{"t": 1700000000, "p": 0.5}, {"t": 1700003600, "p": 0.55}]},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        samples = await fetch_prices_history(
            token_id="tok", interval="1m", fidelity_minutes=60, client=client
        )

    assert len(samples) == 2
    assert samples[0]["p"] == 0.5


def test_aligned_view_joins_poly_prices_to_crypto_returns(tmp_path) -> None:
    paths = WarehousePaths(root=tmp_path)

    # Two crypto bars: hour 0 and hour 1, BTCUSDT. Pick an hour-aligned epoch
    # so the bucketing in polymarket_price_history_hourly produces the same
    # open_time_ns as Binance's kline open_time.
    h0 = 1_700_002_800_000  # 2023-11-14T22:20:00Z + alignment → exactly hour boundary
    # Make h0 a true hour boundary in ms (multiple of 3_600_000)
    h0 = (h0 // 3_600_000) * 3_600_000
    h1 = h0 + 3_600_000
    h2 = h1 + 3_600_000
    klines = project_binance_klines(
        [
            [h0, "30000", "30100", "29900", "30000", "1.0", h0 + 3_599_999, "30000", 10, "0.5", "15000", "0"],
            [h1, "30000", "30200", "29950", "30200", "1.0", h1 + 3_599_999, "30100", 10, "0.5", "15050", "0"],
            [h2, "30200", "30500", "30100", "30400", "1.0", h2 + 3_599_999, "30300", 10, "0.5", "15150", "0"],
        ],
        symbol="BTCUSDT",
        interval="1h",
    )
    ParquetWriter(table=CRYPTO_OHLCV, paths=paths).write(
        [r.to_warehouse_row() for r in klines]
    )

    # One BTC market with YES token "tok-btc"
    market = project_gamma_market_payload(
        _market_payload(market_id="m-btc", question="Will Bitcoin hit $100k?", yes="tok-btc", no="tok-no"),
        fetched_at=datetime(2026, 4, 27, tzinfo=timezone.utc),
    )
    ParquetWriter(table=POLYMARKET_CRYPTO_MARKETS, paths=paths).write(
        [market.to_warehouse_row()]
    )

    # Three prob samples at the same hours
    samples = [
        {"t": h0 // 1000, "p": 0.10},
        {"t": h1 // 1000, "p": 0.12},
        {"t": h2 // 1000, "p": 0.15},
    ]
    history_rows = project_history_samples(
        samples, token_id="tok-btc", market_id="m-btc", outcome="Yes", interval_label="1m", fidelity_minutes=60
    )
    ParquetWriter(table=POLYMARKET_PRICE_HISTORY, paths=paths).write(
        [r.to_warehouse_row() for r in history_rows]
    )

    con = duckdb.connect()
    register_views(con, paths)

    rows = con.execute(
        """
        SELECT asset, open_time_ns, poly_yes_price, poly_price_change,
               crypto_symbol, crypto_log_return, crypto_log_return_next_1h
        FROM crypto_polymarket_aligned
        ORDER BY open_time_ns
        """
    ).fetchall()

    assert len(rows) == 3
    assert rows[0][0] == "BTC"
    assert rows[0][2] == pytest.approx(0.10)
    assert rows[0][3] is None  # first row, no prior poly price
    assert rows[1][3] == pytest.approx(0.02)  # 0.12 - 0.10
    assert rows[1][4] == "BTCUSDT"
    # crypto_log_return_next_1h on row 1 should be the row-2 log_return
    assert rows[1][6] is not None
