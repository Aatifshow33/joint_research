from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone

import pytest

from joint_research.ingest.binance_klines import project_binance_klines
from joint_research.ingest.clob_prices_history import project_history_samples
from joint_research.ingest.gamma_crypto_markets import project_gamma_market_payload
from joint_research.research.lead_lag import (
    benjamini_hochberg_significant,
    pearson_correlation_with_tstat,
    run_lead_lag_study,
    write_pattern_catalog,
)
from joint_research.warehouse import (
    CRYPTO_OHLCV,
    POLYMARKET_CRYPTO_MARKETS,
    POLYMARKET_PRICE_HISTORY,
    ParquetWriter,
    WarehousePaths,
)


def test_correlation_perfect_positive() -> None:
    n, r, t, p = pearson_correlation_with_tstat([1.0, 2.0, 3.0, 4.0], [2.0, 4.0, 6.0, 8.0])
    assert n == 4
    assert r == pytest.approx(1.0)
    assert math.isinf(t)
    assert p == pytest.approx(0.0)


def test_correlation_no_relationship_returns_high_pvalue() -> None:
    rng = random.Random(0)
    xs = [rng.gauss(0, 1) for _ in range(200)]
    ys = [rng.gauss(0, 1) for _ in range(200)]
    n, r, t, p = pearson_correlation_with_tstat(xs, ys)
    assert n == 200
    # Two independent random series — correlation should be near zero,
    # p-value far from significant.
    assert abs(r) < 0.2
    assert p > 0.05


def test_correlation_strong_signal_passes_significance() -> None:
    rng = random.Random(0)
    n_obs = 200
    xs = [rng.gauss(0, 1) for _ in range(n_obs)]
    # y_i = 0.7 * x_i + noise — significant correlation expected
    ys = [0.7 * x + rng.gauss(0, 0.5) for x in xs]
    n, r, t, p = pearson_correlation_with_tstat(xs, ys)
    assert n == n_obs
    assert r > 0.5
    assert p < 0.001


def test_correlation_drops_nan_pairs() -> None:
    n, r, _t, _p = pearson_correlation_with_tstat(
        [1.0, 2.0, math.nan, 4.0],
        [2.0, 4.0, 0.0, 8.0],
    )
    assert n == 3
    assert r == pytest.approx(1.0)


def test_benjamini_hochberg_simple() -> None:
    # Sorted-rank thresholds at alpha=0.05, m=5: [0.010, 0.020, 0.030, 0.040, 0.050]
    pvals = [0.001, 0.01, 0.04, 0.5, 0.9]
    survivors = benjamini_hochberg_significant(pvals, alpha=0.05)
    # Largest rank where p <= threshold is rank=2 (0.01 <= 0.02). Rank-3
    # p=0.04 fails its 0.03 threshold so it does not survive.
    assert survivors == [True, True, False, False, False]


def test_benjamini_hochberg_recovers_lower_ranks_when_higher_passes() -> None:
    # If a high rank survives, all lower-p values do too even if their own
    # threshold is tight. Construct: rank-5 p=0.05 (exactly at threshold),
    # rank 1..4 are all small.
    pvals = [0.001, 0.001, 0.001, 0.001, 0.05]
    survivors = benjamini_hochberg_significant(pvals, alpha=0.05)
    assert all(survivors)


def test_benjamini_hochberg_handles_empty() -> None:
    assert benjamini_hochberg_significant([], alpha=0.05) == []


def _seed_known_signal_warehouse(tmp_path) -> WarehousePaths:
    paths = WarehousePaths(root=tmp_path)
    rng = random.Random(0)

    # 50 hours of BTC bars with controlled returns.
    h0 = 1_700_002_800_000
    h0 = (h0 // 3_600_000) * 3_600_000  # align
    n_bars = 50
    klines_raw = []
    btc_returns: list[float] = []
    last_close = 30000.0
    for i in range(n_bars):
        ret = rng.gauss(0, 0.005)  # ~50 bps hourly vol
        new_close = last_close * math.exp(ret)
        klines_raw.append(
            [
                h0 + i * 3_600_000,
                f"{last_close:.2f}",
                f"{max(last_close, new_close) + 10:.2f}",
                f"{min(last_close, new_close) - 10:.2f}",
                f"{new_close:.2f}",
                "1.0",
                h0 + i * 3_600_000 + 3_599_999,
                f"{new_close:.2f}",
                10,
                "0.5",
                f"{new_close / 2:.2f}",
                "0",
            ]
        )
        btc_returns.append(ret)
        last_close = new_close

    klines = project_binance_klines(klines_raw, symbol="BTCUSDT", interval="1h")
    ParquetWriter(table=CRYPTO_OHLCV, paths=paths).write(
        [r.to_warehouse_row() for r in klines]
    )

    # Polymarket BTC YES token whose Δprob LEADS BTC returns by 1 hour with
    # strong signal. price[i] = clip(0.5 + 0.5 * sum_of_returns_through_i + noise)
    end_iso = (datetime.now(tz=timezone.utc) + timedelta(days=14)).isoformat()
    market_payload = {
        "id": "m-leading",
        "conditionId": "0xabc",
        "question": "Will Bitcoin hit $35,000 in 2 weeks?",
        "slug": "btc-35k",
        "active": True,
        "closed": False,
        "archived": False,
        "endDate": end_iso,
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-04-20T00:00:00Z",
        "volume": 100000.0,
        "volume1mo": 50000.0,
        "lastTradePrice": 0.5,
        "clobTokenIds": '["leading-yes-tok", "leading-no-tok"]',
    }
    market = project_gamma_market_payload(
        market_payload, fetched_at=datetime.now(tz=timezone.utc)
    )
    ParquetWriter(table=POLYMARKET_CRYPTO_MARKETS, paths=paths).write(
        [market.to_warehouse_row()]
    )

    # Build the leading prob series: price at hour i moves AHEAD of return at i+1
    samples: list[dict] = []
    base_price = 0.5
    for i in range(n_bars - 1):
        # Inject the next-hour return into this hour's price change
        leading_signal = btc_returns[i + 1] * 30.0  # large coefficient -> strong corr
        noise = rng.gauss(0, 0.005)
        new_price = max(0.001, min(0.999, base_price + leading_signal + noise))
        samples.append({"t": (h0 + i * 3_600_000) // 1000, "p": new_price})
        base_price = new_price
    history_rows = project_history_samples(
        samples,
        token_id="leading-yes-tok",
        market_id="m-leading",
        outcome="Yes",
        interval_label="1m",
        fidelity_minutes=60,
    )
    ParquetWriter(table=POLYMARKET_PRICE_HISTORY, paths=paths).write(
        [r.to_warehouse_row() for r in history_rows]
    )
    return paths


def test_run_lead_lag_finds_known_leading_signal(tmp_path) -> None:
    paths = _seed_known_signal_warehouse(tmp_path)

    token_results, bucket_results = run_lead_lag_study(
        paths=paths, min_observations_per_token=10
    )

    # We expect rows for token "leading-yes-tok" at lags 0, 1, 4, 24
    by_lag = {tr.lag_hours: tr for tr in token_results if tr.token_id == "leading-yes-tok"}
    assert set(by_lag.keys()) == {0, 1, 4, 24}

    # Lag 1 should have the strongest correlation by construction
    assert by_lag[1].correlation > 0.5
    assert by_lag[1].pvalue_two_sided < 0.001
    # Days-to-resolution bucket should be 7-30d
    assert by_lag[1].days_bucket == "7-30d"

    # Bucket aggregator must produce at least one cell that's BH-significant
    sig_cells = [b for b in bucket_results if b.bh_significant_at_0_05]
    assert any(b.lag_hours == 1 and b.asset == "BTC" for b in sig_cells)


def test_run_lead_lag_daily_mode_uses_daily_view(tmp_path) -> None:
    paths = _seed_known_signal_warehouse(tmp_path)

    # The seed fixture only has 50 hourly bars (~2 days) so daily mode will
    # have very few observations; we just verify the call dispatches to the
    # daily view without error and produces lag horizons in the daily set.
    token_results, _ = run_lead_lag_study(
        paths=paths, min_observations_per_token=1, frequency="daily"
    )

    if token_results:
        # Daily lag_hours emitted as multiples of 24 — must include at least one
        lags = {tr.lag_hours for tr in token_results}
        assert any(lag in {0, 24, 72, 168, 336} for lag in lags)


def test_run_lead_lag_rejects_unknown_frequency(tmp_path) -> None:
    paths = WarehousePaths(root=tmp_path)
    with pytest.raises(ValueError, match="unsupported_frequency"):
        run_lead_lag_study(paths=paths, frequency="weekly")


def test_pattern_catalog_writes_two_parquet_files(tmp_path) -> None:
    paths = _seed_known_signal_warehouse(tmp_path)
    token_results, bucket_results = run_lead_lag_study(
        paths=paths, min_observations_per_token=10
    )

    out_prefix = tmp_path / "pattern_catalog"
    write_pattern_catalog(
        out_path=out_prefix,
        token_results=token_results,
        bucket_results=bucket_results,
    )

    tokens_path = out_prefix.with_suffix(".tokens.parquet")
    buckets_path = out_prefix.with_suffix(".buckets.parquet")
    assert tokens_path.exists()
    assert buckets_path.exists()

    import pyarrow.parquet as pq  # noqa: PLC0415
    t = pq.read_table(tokens_path)
    assert "correlation" in t.schema.names
    b = pq.read_table(buckets_path)
    assert "pooled_correlation" in b.schema.names
