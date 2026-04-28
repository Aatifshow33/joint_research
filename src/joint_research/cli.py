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


@ingest_app.command("crypto-derivatives")
def ingest_crypto_derivatives(
    symbols: str = typer.Option(
        "BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT",
        help="Comma-separated Binance symbols.",
    ),
    limit: int = typer.Option(24, help="Funding rows per symbol."),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Pull public/no-auth funding and perp-basis inputs into the warehouse."""

    from joint_research.ingest.crypto_derivatives import fetch_derivatives_rows  # noqa: PLC0415
    from joint_research.warehouse import CRYPTO_DERIVATIVES, ParquetWriter  # noqa: PLC0415

    paths = _resolve_paths(warehouse_root)
    symbol_list = tuple(s.strip().upper() for s in symbols.split(",") if s.strip())
    result = asyncio.run(fetch_derivatives_rows(symbols=symbol_list, limit=limit))
    if not result.rows:
        typer.echo(
            f"ingested=0 symbols={','.join(symbol_list)} errors={len(result.errors)}. "
            "nothing written."
        )
        for error in result.errors:
            typer.echo(f"  warning={error}")
        raise typer.Exit(code=0)
    shard = ParquetWriter(table=CRYPTO_DERIVATIVES, paths=paths).write(
        [row.to_warehouse_row() for row in result.rows]
    )
    typer.echo(
        f"ingested={len(result.rows)} symbols={','.join(symbol_list)} "
        f"errors={len(result.errors)} shard={shard}"
    )
    for error in result.errors:
        typer.echo(f"  warning={error}")


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
    output_dir: Path = typer.Option(
        Path("artifacts/research/lead_lag"),
        "--output-dir",
        "--out-path",
        help=(
            "Directory for lead_lag_summary.md, lead_lag_results.csv, "
            "and lead_lag_candidates.json."
        ),
    ),
    show_top: int = typer.Option(10, help="Print the top-N candidates by |t-stat|."),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Run the exploratory Polymarket→crypto lead-lag report."""

    from joint_research.research.lead_lag import (  # noqa: PLC0415
        rank_signal_candidates,
        run_lead_lag_study,
        write_lead_lag_report,
    )

    paths = _resolve_paths(warehouse_root)
    token_results, bucket_results = run_lead_lag_study(
        paths=paths,
        min_observations_per_token=min_observations,
        frequency=frequency,
    )

    report_paths = write_lead_lag_report(
        output_dir=output_dir.resolve(),
        token_results=token_results,
        bucket_results=bucket_results,
    )

    markets_tested = len({(r.asset, r.market_id, r.token_id) for r in token_results})
    typer.echo(
        "EXPLORATORY ONLY - NOT TRADEABLE\n"
        f"markets_tested={markets_tested} "
        f"hypothesis_rows={len(token_results)} "
        f"bucket_cells={len(bucket_results)}"
    )
    typer.echo(f"summary={report_paths.summary_md}")
    typer.echo(f"results_csv={report_paths.results_csv}")
    typer.echo(f"candidates_json={report_paths.candidates_json}")

    if not token_results:
        typer.echo("no tokens met the min_observations threshold. backfill more data.")
        raise typer.Exit(code=0)

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

    typer.echo(f"\ntop {show_top} exploratory candidates by |t|:")
    for c in rank_signal_candidates(token_results, limit=show_top):
        typer.echo(
            f"  rank={c.rank:>2} asset={c.asset:>4} lag={c.lag_hours:>2}h "
            f"r={c.correlation:+.3f} t={c.tstat:+.2f} p={c.pvalue_two_sided:.4f} "
            f"n={c.n} market={c.market_slug or c.market_id}"
        )


@research_app.command("robustness")
def research_robustness(
    min_observations: int = typer.Option(60, help="Minimum aligned bars per market/horizon."),
    min_nonzero_changes: int = typer.Option(
        20,
        help="Minimum non-zero Polymarket probability changes.",
    ),
    max_flat_fraction: float = typer.Option(
        0.90,
        help="Reject markets with a higher fraction of zero probability changes.",
    ),
    min_days_to_resolution: float = typer.Option(
        3.0,
        help="Reject markets whose last aligned sample is this close to resolution.",
    ),
    train_fraction: float = typer.Option(0.60, help="Earlier fraction used as train/discovery."),
    n_permutations: int = typer.Option(200, help="Deterministic shuffles per market/horizon."),
    output_dir: Path = typer.Option(
        Path("artifacts/research/robustness"),
        "--output-dir",
        "--out-path",
        help=(
            "Directory for robustness_summary.md, robustness_results.csv, "
            "and robustness_candidates.json."
        ),
    ),
    show_top: int = typer.Option(10, help="Print the top-N robustness candidates."),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Run paper-only robustness checks over Polymarket→crypto candidates."""

    from joint_research.research.robustness import (  # noqa: PLC0415
        CandidateGrade,
        run_robustness_study,
        write_robustness_report,
    )

    paths = _resolve_paths(warehouse_root)
    results = run_robustness_study(
        paths=paths,
        min_observations=min_observations,
        min_nonzero_changes=min_nonzero_changes,
        max_flat_fraction=max_flat_fraction,
        min_days_to_resolution=min_days_to_resolution,
        train_fraction=train_fraction,
        n_permutations=n_permutations,
    )
    report_paths = write_robustness_report(
        output_dir=output_dir.resolve(),
        results=results,
    )

    counts = {grade.value: sum(1 for r in results if r.grade is grade) for grade in CandidateGrade}
    typer.echo(
        "EXPLORATORY ONLY - NOT TRADEABLE\n"
        f"hypothesis_rows={len(results)} "
        f"promising={counts['PROMISING']} "
        f"watchlist={counts['WATCHLIST']} "
        f"weak={counts['WEAK']} "
        f"rejected={counts['REJECTED']}"
    )
    typer.echo(f"summary={report_paths.summary_md}")
    typer.echo(f"results_csv={report_paths.results_csv}")
    typer.echo(f"candidates_json={report_paths.candidates_json}")

    candidates = [r for r in results if r.grade is not CandidateGrade.REJECTED][:show_top]
    if not candidates:
        typer.echo("no robustness candidates survived beyond REJECTED.")
        raise typer.Exit(code=0)

    typer.echo(f"\ntop {show_top} robustness candidates:")
    for r in candidates:
        oos_match = (
            r.train_correlation * r.test_correlation > 0
            if not (math.isnan(r.train_correlation) or math.isnan(r.test_correlation))
            else False
        )
        typer.echo(
            f"  rank={r.rank:>2} grade={r.grade.value:<9} asset={r.asset:>4} "
            f"lag={r.lag_hours:>2}h oos_match={oos_match} "
            f"emp_p={r.empirical_pvalue:.4f} stability={r.rolling_stability:.2f} "
            f"n={r.n_observations} market={r.market_slug or r.market_id}"
        )


@research_app.command("composite-signal")
def research_composite_signal(
    min_train_samples: int = typer.Option(30, help="Minimum train samples per rule."),
    min_test_samples: int = typer.Option(20, help="Minimum test samples per rule."),
    output_dir: Path = typer.Option(
        Path("artifacts/research/composite_signal"),
        "--output-dir",
        "--out-path",
        help=(
            "Directory for composite_signal_summary.md, composite_signal_results.csv, "
            "and composite_signal_candidates.json."
        ),
    ),
    show_top: int = typer.Option(10, help="Print the top-N composite candidates."),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Run deterministic composite signal scans over warehouse features."""

    from joint_research.research.composite_signal import (  # noqa: PLC0415
        CompositeCandidateGrade,
        run_composite_signal_study,
        write_composite_signal_report,
    )

    paths = _resolve_paths(warehouse_root)
    results = run_composite_signal_study(
        paths=paths,
        min_train_samples=min_train_samples,
        min_test_samples=min_test_samples,
    )
    report_paths = write_composite_signal_report(
        output_dir=output_dir.resolve(),
        results=results,
    )
    counts = {
        grade.value: sum(1 for result in results if result.grade is grade)
        for grade in CompositeCandidateGrade
    }
    typer.echo(
        "EXPLORATORY ONLY - NOT TRADEABLE\n"
        f"rule_rows={len(results)} "
        f"simulation_ready={counts['SIMULATION_READY']} "
        f"watchlist={counts['WATCHLIST']} "
        f"weak={counts['WEAK']} "
        f"rejected={counts['REJECTED']}"
    )
    typer.echo(f"summary={report_paths.summary_md}")
    typer.echo(f"results_csv={report_paths.results_csv}")
    typer.echo(f"candidates_json={report_paths.candidates_json}")

    candidates = [
        result for result in results if result.grade is not CompositeCandidateGrade.REJECTED
    ][:show_top]
    if not candidates:
        typer.echo("no composite candidates survived beyond REJECTED.")
        raise typer.Exit(code=0)

    typer.echo(f"\ntop {show_top} composite candidates:")
    for result in candidates:
        typer.echo(
            f"  rank={result.rank:>2} grade={result.grade.value:<16} "
            f"asset={result.asset:>4} horizon={result.horizon_hours:>2}h "
            f"test_acc={result.test_accuracy:.2f} "
            f"test_avg={result.test_average_forward_return:+.5f} "
            f"rule={result.rule_family} market={result.market_slug or result.market_id}"
        )


@research_app.command("simulate")
def research_simulate(
    starting_capital: float = typer.Option(200.0, help="Paper bankroll in USD."),
    fixed_notional: float = typer.Option(10.0, help="Fixed paper notional per trade."),
    max_simultaneous_exposure: float = typer.Option(
        50.0,
        help="Maximum simultaneous simulated exposure in USD.",
    ),
    fee_bps: float = typer.Option(10.0, help="Per-side paper fee in basis points."),
    slippage_bps: float = typer.Option(10.0, help="Per-side paper slippage in basis points."),
    min_samples: int = typer.Option(20, help="Minimum simulation observations per candidate."),
    min_probability_move: float = typer.Option(
        0.001,
        help="Skip signals with smaller absolute probability movement.",
    ),
    output_dir: Path = typer.Option(
        Path("artifacts/research/simulation"),
        "--output-dir",
        "--out-path",
        help=(
            "Directory for simulation_summary.md, simulation_trades.csv, "
            "simulation_results.csv, and simulation_candidates.json."
        ),
    ),
    show_top: int = typer.Option(10, help="Print the top-N simulated candidates."),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Run paper-only walk-forward simulation for robust candidates."""

    from joint_research.research.simulation import (  # noqa: PLC0415
        SimulationGrade,
        run_simulation_study,
        write_simulation_report,
    )

    paths = _resolve_paths(warehouse_root)
    results = run_simulation_study(
        paths=paths,
        starting_capital=starting_capital,
        fixed_notional=fixed_notional,
        max_simultaneous_exposure=max_simultaneous_exposure,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        min_samples=min_samples,
        min_probability_move=min_probability_move,
    )
    report_paths = write_simulation_report(
        output_dir=output_dir.resolve(),
        results=results,
    )

    counts = {
        grade.value: sum(1 for result in results if result.simulation_grade is grade)
        for grade in SimulationGrade
    }
    total_pnl = sum(result.total_paper_pnl for result in results)
    total_trades = sum(result.trade_count for result in results)
    typer.echo(
        "EXPLORATORY ONLY - NOT TRADEABLE\n"
        f"candidates_simulated={len(results)} "
        f"trades={total_trades} "
        f"paper_pnl=${total_pnl:.2f} "
        f"paper_ready={counts['PAPER_READY']} "
        f"watchlist={counts['WATCHLIST']} "
        f"rejected={counts['REJECTED']}"
    )
    typer.echo(f"summary={report_paths.summary_md}")
    typer.echo(f"trades_csv={report_paths.trades_csv}")
    typer.echo(f"results_csv={report_paths.results_csv}")
    typer.echo(f"candidates_json={report_paths.candidates_json}")

    candidates = [
        result for result in results if result.simulation_grade is not SimulationGrade.REJECTED
    ][:show_top]
    if not candidates:
        typer.echo("no simulation candidates survived beyond REJECTED.")
        raise typer.Exit(code=0)

    typer.echo(f"\ntop {show_top} simulated candidates:")
    for result in candidates:
        typer.echo(
            f"  rank={result.rank:>2} grade={result.simulation_grade.value:<11} "
            f"asset={result.asset:>4} lag={result.lag_hours:>2}h "
            f"trades={result.trade_count} win={result.win_rate:.2f} "
            f"pnl=${result.total_paper_pnl:.2f} dd=${result.max_drawdown:.2f} "
            f"market={result.market_slug or result.market_id}"
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
