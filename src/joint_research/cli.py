"""``joint-research`` CLI entrypoint."""

from __future__ import annotations

import asyncio
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import typer

from joint_research.warehouse import WarehousePaths

app = typer.Typer(no_args_is_help=True, add_completion=False)
ingest_app = typer.Typer(no_args_is_help=True, help="Ingest data into the warehouse.")
research_app = typer.Typer(no_args_is_help=True, help="Run research analyses against the warehouse.")
app.add_typer(ingest_app, name="ingest")
app.add_typer(research_app, name="research")


def _resolve_paths(warehouse_root: Path | None) -> WarehousePaths:
    if warehouse_root is not None:
        return WarehousePaths(root=warehouse_root.resolve())
    return WarehousePaths.from_env()


def _parse_iso_or_relative_days(value: str) -> datetime:
    """Accept an ISO-8601 datetime, an ISO date, or ``-Nd`` for "N days ago"."""

    if value.startswith("-") and value.endswith("d"):
        try:
            days = int(value[1:-1])
        except ValueError as exc:
            raise typer.BadParameter(f"invalid relative form: {value}") from exc
        return datetime.now(tz=timezone.utc) - timedelta(days=days)
    cleaned = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError as exc:
        raise typer.BadParameter(f"unparseable timestamp: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


@ingest_app.command("gamma-events")
def ingest_gamma_events(
    limit: int = typer.Option(500, help="Number of events to fetch in this run."),
    active: bool = typer.Option(True, help="Filter to currently-active events."),
    closed: bool = typer.Option(False, help="Include closed events."),
    archived: bool = typer.Option(False, help="Include archived events."),
    warehouse_root: Path = typer.Option(
        None,
        help="Override warehouse root. Defaults to $JOINT_RESEARCH_WAREHOUSE_ROOT or ./data/warehouse.",
    ),
) -> None:
    """Pull Polymarket /events from the Gamma API and append a Parquet shard."""

    from joint_research.ingest.polymarket_runner import ingest_gamma_events as run  # noqa: PLC0415

    paths = _resolve_paths(warehouse_root)
    result = asyncio.run(
        run(paths=paths, limit=limit, active=active, closed=closed, archived=archived)
    )
    if result.rows_written == 0:
        typer.echo("ingested=0 rows. nothing written.")
        raise typer.Exit(code=0)
    typer.echo(f"ingested={result.rows_written} shard={result.shard_path}")


@ingest_app.command("crypto-ohlcv")
def ingest_crypto_ohlcv(
    symbol: str = typer.Option(..., help="Binance symbol, e.g. BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT."),
    interval: str = typer.Option("1h", help="Kline interval: 1m/5m/15m/1h/4h/1d/etc."),
    start: str = typer.Option("-30d", help="Start time. ISO-8601 or '-Nd' for N days ago."),
    end: str = typer.Option(
        None,
        help="End time. ISO-8601 or '-Nd'. Defaults to 'now' (UTC).",
    ),
    warehouse_root: Path = typer.Option(
        None,
        help="Override warehouse root. Defaults to $JOINT_RESEARCH_WAREHOUSE_ROOT or ./data/warehouse.",
    ),
) -> None:
    """Pull Binance klines for [start, end) and append a Parquet shard."""

    from joint_research.ingest.crypto_runner import ingest_binance_ohlcv as run  # noqa: PLC0415

    paths = _resolve_paths(warehouse_root)
    start_dt = _parse_iso_or_relative_days(start)
    end_dt = (
        _parse_iso_or_relative_days(end)
        if end is not None
        else datetime.now(tz=timezone.utc)
    )

    result = asyncio.run(
        run(
            paths=paths,
            symbol=symbol,
            interval=interval,
            start=start_dt,
            end=end_dt,
        )
    )
    if result.rows_written == 0:
        typer.echo(
            f"ingested=0 symbol={result.symbol} interval={result.interval} "
            f"window={result.start_iso}..{result.end_iso}. nothing written."
        )
        raise typer.Exit(code=0)
    typer.echo(
        f"ingested={result.rows_written} symbol={result.symbol} interval={result.interval} "
        f"window={result.start_iso}..{result.end_iso} shard={result.shard_path}"
    )


@ingest_app.command("gamma-crypto-markets")
def ingest_gamma_crypto_markets(
    limit: int = typer.Option(500, help="Max markets to fetch from Gamma."),
    active: bool = typer.Option(True, help="Only currently-active markets."),
    closed: bool = typer.Option(False, help="Include closed markets."),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Pull crypto-tagged Polymarket markets (tag_id=21) into the warehouse."""

    from joint_research.ingest.polymarket_history_runner import (  # noqa: PLC0415
        ingest_gamma_crypto_markets as run,
    )

    paths = _resolve_paths(warehouse_root)
    result = asyncio.run(run(paths=paths, limit=limit, active=active, closed=closed))
    if result.rows_written == 0:
        typer.echo("ingested=0 markets. nothing written.")
        raise typer.Exit(code=0)
    typer.echo(f"ingested={result.rows_written} markets shard={result.shard_path}")


@ingest_app.command("polymarket-prices")
def ingest_polymarket_prices(
    top_n: int = typer.Option(10, help="Backfill the top-N crypto markets by 1mo volume."),
    interval: str = typer.Option("1m", help="Polymarket history interval: 1h/6h/1d/1w/1m/max."),
    fidelity_minutes: int = typer.Option(60, help="Bucket size in minutes (60 = hourly)."),
    include_closed: bool = typer.Option(
        False,
        "--include-closed/--active-only",
        help="Include closed/resolved markets — required for survivorship-bias-free analysis.",
    ),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Pull /prices-history for top-N crypto YES tokens already in the warehouse."""

    from joint_research.ingest.polymarket_history_runner import (  # noqa: PLC0415
        ingest_top_crypto_market_prices as run,
    )

    paths = _resolve_paths(warehouse_root)
    result = asyncio.run(
        run(
            paths=paths,
            top_n=top_n,
            interval=interval,
            fidelity_minutes=fidelity_minutes,
            include_closed=include_closed,
        )
    )
    typer.echo(
        f"tokens_attempted={result.tokens_attempted} "
        f"tokens_with_data={result.tokens_with_data} "
        f"rows_written={result.rows_written} "
        f"shard={result.shard_path or '(none)'}"
    )


@research_app.command("lead-lag")
def research_lead_lag(
    min_observations: int = typer.Option(30, help="Skip tokens with fewer aligned bars than this."),
    frequency: str = typer.Option(
        "hourly",
        help="Sampling frequency: 'hourly' (lags 0/1/4/24 h) or 'daily' (lags 0/1/3/7/14 d).",
    ),
    out_path: Path = typer.Option(
        Path("data/research/pattern_catalog"),
        help="Output prefix. Two files written: {prefix}.tokens.parquet and {prefix}.buckets.parquet.",
    ),
    show_top: int = typer.Option(10, help="Print the top-N bucket results by |t-stat|."),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Run the Polymarket→crypto lead-lag study and write a pattern catalog."""

    from joint_research.research.lead_lag import (  # noqa: PLC0415
        run_lead_lag_study,
        write_pattern_catalog,
    )

    paths = _resolve_paths(warehouse_root)
    token_results, bucket_results = run_lead_lag_study(
        paths=paths,
        min_observations_per_token=min_observations,
        frequency=frequency,
    )
    if not token_results:
        typer.echo("no tokens met the min_observations threshold. backfill more data.")
        raise typer.Exit(code=1)

    write_pattern_catalog(
        out_path=out_path.resolve(),
        token_results=token_results,
        bucket_results=bucket_results,
    )

    typer.echo(
        f"tokens_tested={len(set((r.token_id, r.lag_hours) for r in token_results))} "
        f"bucket_cells={len(bucket_results)}"
    )

    sig = [b for b in bucket_results if b.bh_significant_at_0_05]
    if sig:
        typer.echo(f"BH-significant bucket cells: {len(sig)}")
        for b in sig:
            typer.echo(
                f"  asset={b.asset} bucket={b.days_bucket} lag={b.lag_hours}h "
                f"r={b.pooled_correlation:+.3f} t={b.pooled_tstat:+.2f} "
                f"p={b.pooled_pvalue:.4f} n_obs={b.n_observations}"
            )
    else:
        typer.echo("no BH-significant bucket cells at alpha=0.05 (expected with limited data)")

    typer.echo(f"\ntop {show_top} bucket cells by |t|:")
    ordered = sorted(
        (b for b in bucket_results if not (math.isnan(b.pooled_tstat))),
        key=lambda b: -abs(b.pooled_tstat),
    )[:show_top]
    for b in ordered:
        typer.echo(
            f"  asset={b.asset:>4} bucket={b.days_bucket:>7} lag={b.lag_hours:>2}h "
            f"r={b.pooled_correlation:+.3f} t={b.pooled_tstat:+.2f} "
            f"p={b.pooled_pvalue:.4f} n_tokens={b.n_tokens} n_obs={b.n_observations}"
        )


@ingest_app.command("wallet-activity")
def ingest_wallet_activity(
    limit: int = typer.Option(50, help="Top-N wallets to discover and pull activity for."),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Pull whale wallet activity (top traders + market top-holders) via DataAPI."""

    from joint_research.ingest.wallet_runner import (  # noqa: PLC0415
        ingest_whale_wallet_activity as run,
    )

    paths = _resolve_paths(warehouse_root)
    result = asyncio.run(run(paths=paths, limit=limit))
    typer.echo(
        f"wallets_selected={result.wallets_selected} "
        f"activities_fetched={result.activities_fetched} "
        f"rows_written={result.rows_written} "
        f"shard={result.shard_path or '(none)'}"
    )


@research_app.command("event-study")
def research_event_study(
    min_trade_size_usdc: float = typer.Option(
        100.0, help="Skip trades smaller than this notional in USDC."
    ),
    out_path: Path = typer.Option(
        Path("data/research/event_study_catalog.parquet"),
        help="Output Parquet path for the event-study cells.",
    ),
    show_top: int = typer.Option(20, help="Print the top-N cells by |t-stat|."),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Run the whale-trade → crypto-return event study."""

    from joint_research.research.event_study import (  # noqa: PLC0415
        run_event_study,
        write_event_study_catalog,
    )

    paths = _resolve_paths(warehouse_root)
    result = run_event_study(
        paths=paths,
        min_trade_size_usdc=min_trade_size_usdc,
    )
    write_event_study_catalog(out_path=out_path.resolve(), result=result)

    typer.echo(
        f"trades_total={result.n_trades_total} "
        f"wallets={result.n_wallets} assets={result.n_assets} "
        f"cells={len(result.cells)}"
    )

    sig = [c for c in result.cells if c.bh_significant_at_0_05]
    if sig:
        typer.echo(f"BH-significant cells: {len(sig)}")
        for c in sig:
            typer.echo(
                f"  asset={c.asset} dir={c.direction} lag={c.lag_hours}h "
                f"mean={c.mean_log_return*1e4:+.2f}bps "
                f"t={c.tstat_vs_zero:+.2f} p={c.pvalue_vs_zero:.4f} n={c.n_trades}"
            )
    else:
        typer.echo("no BH-significant cells at alpha=0.05")

    typer.echo(f"\ntop {show_top} cells by |t|:")
    ordered = sorted(
        (c for c in result.cells if not math.isnan(c.tstat_vs_zero)),
        key=lambda c: -abs(c.tstat_vs_zero),
    )[:show_top]
    for c in ordered:
        typer.echo(
            f"  asset={c.asset:>4} dir={c.direction:>8} lag={c.lag_hours:>2}h "
            f"mean={c.mean_log_return*1e4:+7.2f}bps t={c.tstat_vs_zero:+.2f} "
            f"p={c.pvalue_vs_zero:.4f} n={c.n_trades}"
        )


@research_app.command("cryp-backtest")
def research_cryp_backtest(
    symbols: str = typer.Option(
        "BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT",
        help="Comma-separated symbol list to backtest.",
    ),
    feature_lookback: int = typer.Option(14, help="Hours of history fed to feature pipeline."),
    max_holding_hours: int = typer.Option(24, help="Max bars to hold a trade if neither stop nor TP hits."),
    round_trip_cost_bps: float = typer.Option(
        14.0,
        help="Combined entry+exit fee + slippage in bps. Bybit perp taker is ~11 bps round-trip; 14 leaves buffer.",
    ),
    out_path: Path = typer.Option(
        Path("data/research/cryp_backtest_trades.parquet"),
        help="Output Parquet path for the per-trade ledger.",
    ),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Backtest cryp's deterministic breakout/mean-reversion on warehouse OHLCV."""

    from joint_research.research.cryp_backtest import (  # noqa: PLC0415
        run_cryp_backtest,
        write_backtest_catalog,
    )

    paths = _resolve_paths(warehouse_root)
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    results = []
    for symbol in symbol_list:
        res = run_cryp_backtest(
            paths=paths,
            symbol=symbol,
            feature_lookback=feature_lookback,
            max_holding_hours=max_holding_hours,
            round_trip_cost_bps=round_trip_cost_bps,
        )
        results.append(res)
        s = res.summary()
        typer.echo(
            f"symbol={res.symbol:<10} candles={res.n_candles:>5} "
            f"breakout_props={res.n_proposals_breakout:>4} "
            f"mr_props={res.n_proposals_mean_reversion:>4} "
            f"trades={s['n_trades']:>4} "
            f"hit_rate={s['hit_rate']:.2f} "
            f"mean_bps={s['mean_net_bps']:+7.2f} "
            f"total_bps={s['total_net_bps']:+8.1f} "
            f"max_dd_bps={s['max_drawdown_bps']:7.1f} "
            f"sharpe={s['sharpe_per_trade']:+5.2f}"
        )

    write_backtest_catalog(out_path=out_path.resolve(), results=results)
    typer.echo(f"\ntrades catalog: {out_path.resolve()}")


if __name__ == "__main__":
    app()
